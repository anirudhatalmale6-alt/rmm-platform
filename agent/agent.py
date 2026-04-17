"""RMM Agent — main entry point.

This is the core agent that runs as a Windows service. It:
  1. Registers with the server (first run only)
  2. Checks in every 5 minutes to pick up pending commands
  3. Reports system info every 15 minutes
  4. Executes commands and reports results back

Usage:
  Register:  python agent.py --register --token <reg-token> --api-url <url>
  Run:       python agent.py
  Service:   python service.py install / start / stop / remove
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

import config
import system_info
import command_executor

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

config.ensure_dirs()
LOG_FILE = os.path.join(config.LOG_DIR, "agent.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("rmm-agent")


# ---------------------------------------------------------------------------
# API communication
# ---------------------------------------------------------------------------

def api_request(cfg, endpoint, data=None, method="POST"):
    """Make an API request to the RMM server."""
    url = f"{cfg['api_url'].rstrip('/')}{endpoint}"
    headers = {"Content-Type": "application/json"}

    if cfg.get("api_key"):
        headers["X-Api-Key"] = cfg["api_key"]

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        logger.error(f"API error {e.code}: {error_body}")
        return None
    except Exception as e:
        logger.error(f"API request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(api_url, token):
    """Register this device with the RMM server."""
    logger.info("Registering device...")

    # Collect basic system info for registration
    info = system_info.collect()

    cfg = {"api_url": api_url, "api_key": ""}
    result = api_request(cfg, "/agent/register", {
        "registration_token": token,
        "hostname": info["hostname"],
        "os": info["os_version"],
        "ip": info["ip"],
    })

    if not result or "api_key" not in result:
        logger.error(f"Registration failed: {result}")
        return False

    # Save configuration
    new_cfg = {
        "api_url": api_url,
        "api_key": result["api_key"],
        "device_id": result["device_id"],
        "customer_id": result["customer_id"],
        "checkin_interval": 300,
        "sysinfo_interval": 900,
    }
    config.save_config(new_cfg)

    logger.info(f"Registration successful! Device ID: {result['device_id']}")
    return True


# ---------------------------------------------------------------------------
# Check-in (heartbeat + command fetch)
# ---------------------------------------------------------------------------

def checkin(cfg):
    """Check in with the server and process any pending commands."""
    logger.debug("Checking in...")
    result = api_request(cfg, "/agent/checkin")

    if not result:
        logger.warning("Check-in failed — will retry next interval")
        return

    commands = result.get("commands", [])
    if commands:
        logger.info(f"Received {len(commands)} command(s)")
        for cmd in commands:
            process_command(cfg, cmd)
    else:
        logger.debug("No pending commands")


def process_command(cfg, command):
    """Execute a command and report the result."""
    command_id = command.get("command_id", "unknown")
    logger.info(f"Processing command: {command_id} (type: {command.get('type')})")

    result = command_executor.execute(command)

    # Report result back to server
    report = {
        "command_id": command_id,
        "status": result.get("status", "failed"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "exit_code": result.get("exit_code", -1),
    }
    api_request(cfg, "/agent/command-result", report)
    logger.info(f"Command {command_id}: {result.get('status')}")


# ---------------------------------------------------------------------------
# System info reporting
# ---------------------------------------------------------------------------

def report_sysinfo(cfg):
    """Collect and upload system information."""
    logger.info("Collecting system info...")
    info = system_info.collect()
    result = api_request(cfg, "/agent/sysinfo", info)
    if result:
        logger.info("System info reported successfully")
    else:
        logger.warning("Failed to report system info — will retry next interval")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run():
    """Main agent loop — runs forever (called by the service or directly)."""
    if not config.is_registered():
        logger.error(
            "Agent not registered. Run with --register --token <token> --api-url <url> first."
        )
        return

    cfg = config.load_config()
    checkin_interval = cfg.get("checkin_interval", 300)
    sysinfo_interval = cfg.get("sysinfo_interval", 900)

    logger.info(f"RMM Agent started. Device ID: {cfg.get('device_id')}")
    logger.info(f"API URL: {cfg.get('api_url')}")
    logger.info(f"Check-in interval: {checkin_interval}s, Sysinfo interval: {sysinfo_interval}s")

    last_checkin = 0
    last_sysinfo = 0

    while True:
        now = time.time()

        try:
            # Check-in (every 5 min)
            if now - last_checkin >= checkin_interval:
                checkin(cfg)
                last_checkin = now

            # System info (every 15 min)
            if now - last_sysinfo >= sysinfo_interval:
                report_sysinfo(cfg)
                last_sysinfo = now

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)

        # Sleep 30 seconds between iterations
        time.sleep(30)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RMM Agent")
    parser.add_argument("--register", action="store_true", help="Register this device")
    parser.add_argument("--token", help="Registration token")
    parser.add_argument("--api-url", help="API Gateway URL")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    args = parser.parse_args()

    if args.register:
        if not args.token or not args.api_url:
            print("Error: --token and --api-url are required for registration")
            sys.exit(1)
        success = register(args.api_url, args.token)
        sys.exit(0 if success else 1)

    elif args.status:
        cfg = config.load_config()
        if config.is_registered():
            print(f"Registered: Yes")
            print(f"Device ID:  {cfg.get('device_id')}")
            print(f"API URL:    {cfg.get('api_url')}")
            print(f"Customer:   {cfg.get('customer_id')}")
        else:
            print("Registered: No")
            print("Run with --register --token <token> --api-url <url>")
        sys.exit(0)

    else:
        run()


if __name__ == "__main__":
    main()
