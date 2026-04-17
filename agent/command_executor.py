"""Command executor — handles commands received from the RMM server."""

import os
import subprocess
import urllib.request
import json
import logging

from config import DATA_DIR

logger = logging.getLogger("rmm-agent")


def execute(command):
    """Execute a command and return the result.

    Command types:
      - run_script: Execute a script/command on the system
      - download_and_install: Download a file and run it (silent install)
      - upload_config: Download a config file and place it at a path
      - restart_service: Restart a Windows service
      - custom: Run arbitrary PowerShell
    """
    cmd_type = command.get("type", "")
    payload = command.get("payload", {})
    command_id = command.get("command_id", "unknown")

    logger.info(f"Executing command {command_id} (type: {cmd_type})")

    try:
        if cmd_type == "run_script":
            return _run_script(payload)
        elif cmd_type == "download_and_install":
            return _download_and_install(payload)
        elif cmd_type == "upload_config":
            return _upload_config(payload)
        elif cmd_type == "restart_service":
            return _restart_service(payload)
        elif cmd_type == "custom":
            return _run_powershell(payload)
        else:
            return {
                "status": "failed",
                "stderr": f"Unknown command type: {cmd_type}",
                "exit_code": -1,
            }
    except Exception as e:
        logger.error(f"Command {command_id} failed: {e}")
        return {
            "status": "failed",
            "stderr": str(e),
            "exit_code": -1,
        }


def _run_script(payload):
    """Run a script or command."""
    script = payload.get("script", "")
    shell = payload.get("shell", "powershell")
    timeout = payload.get("timeout", 300)

    if shell == "powershell":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    elif shell == "cmd":
        cmd = ["cmd", "/c", script]
    else:
        return {"status": "failed", "stderr": f"Unknown shell: {shell}", "exit_code": -1}

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "stdout": result.stdout[:10000],  # Limit output size
        "stderr": result.stderr[:10000],
        "exit_code": result.returncode,
    }


def _download_and_install(payload):
    """Download a file and execute it for silent installation."""
    url = payload.get("url", "")
    filename = payload.get("filename", "installer.exe")
    install_args = payload.get("args", "/S")  # Default: silent install
    timeout = payload.get("timeout", 600)

    if not url:
        return {"status": "failed", "stderr": "No download URL provided", "exit_code": -1}

    # Download to temp location
    download_path = os.path.join(DATA_DIR, filename)
    logger.info(f"Downloading {url} to {download_path}")

    urllib.request.urlretrieve(url, download_path)

    # Execute installer
    logger.info(f"Running installer: {download_path} {install_args}")
    cmd = f'"{download_path}" {install_args}'
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, shell=True,
    )

    # Clean up installer
    try:
        os.remove(download_path)
    except OSError:
        pass

    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "stdout": result.stdout[:10000],
        "stderr": result.stderr[:10000],
        "exit_code": result.returncode,
    }


def _upload_config(payload):
    """Download a config file and place it at the specified path."""
    url = payload.get("url", "")
    content = payload.get("content", "")
    dest_path = payload.get("destination", "")

    if not dest_path:
        return {"status": "failed", "stderr": "No destination path provided", "exit_code": -1}

    # Ensure destination directory exists
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    if url:
        # Download from URL
        logger.info(f"Downloading config from {url} to {dest_path}")
        urllib.request.urlretrieve(url, dest_path)
    elif content:
        # Write content directly
        logger.info(f"Writing config to {dest_path}")
        with open(dest_path, "w") as f:
            f.write(content)
    else:
        return {"status": "failed", "stderr": "No url or content provided", "exit_code": -1}

    return {
        "status": "completed",
        "stdout": f"Config file written to {dest_path}",
        "stderr": "",
        "exit_code": 0,
    }


def _restart_service(payload):
    """Restart a Windows service."""
    service_name = payload.get("service_name", "")
    if not service_name:
        return {"status": "failed", "stderr": "No service_name provided", "exit_code": -1}

    logger.info(f"Restarting service: {service_name}")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Restart-Service -Name '{service_name}' -Force"],
        capture_output=True, text=True, timeout=120,
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "stdout": result.stdout[:10000],
        "stderr": result.stderr[:10000],
        "exit_code": result.returncode,
    }


def _run_powershell(payload):
    """Run arbitrary PowerShell command."""
    script = payload.get("script", "")
    timeout = payload.get("timeout", 300)

    if not script:
        return {"status": "failed", "stderr": "No script provided", "exit_code": -1}

    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    return {
        "status": "completed" if result.returncode == 0 else "failed",
        "stdout": result.stdout[:10000],
        "stderr": result.stderr[:10000],
        "exit_code": result.returncode,
    }
