"""Windows Service wrapper for the RMM Agent.

Usage:
  python service.py install    — Install the service
  python service.py start      — Start the service
  python service.py stop       — Stop the service
  python service.py remove     — Uninstall the service
  python service.py restart    — Restart the service

Prerequisites:
  pip install pywin32 psutil
"""

import sys
import os
import logging

# Add agent directory to path
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENT_DIR)

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
except ImportError:
    print("Error: pywin32 is required. Install with: pip install pywin32")
    print("After installing, run: python -m pywin32_postinstall -install")
    sys.exit(1)

import agent
import config


class RMMAgentService(win32serviceutil.ServiceFramework):
    """Windows Service for the RMM Agent."""

    _svc_name_ = "RMMAgent"
    _svc_display_name_ = "RMM Monitoring Agent"
    _svc_description_ = (
        "Remote Monitoring and Management agent. Collects system information "
        "and executes management commands from the RMM server."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        """Called when the service is asked to stop."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False

    def SvcDoRun(self):
        """Called when the service starts."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        config.ensure_dirs()
        log_file = os.path.join(config.LOG_DIR, "agent.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(log_file)],
        )

        logger = logging.getLogger("rmm-agent")
        logger.info("RMM Agent service started")

        try:
            self._run_agent(logger)
        except Exception as e:
            logger.error(f"Agent crashed: {e}", exc_info=True)

        logger.info("RMM Agent service stopped")

    def _run_agent(self, logger):
        """Run the agent loop, checking for stop signals."""
        import time

        if not config.is_registered():
            logger.error("Agent not registered. Register first using agent.py --register")
            return

        cfg = config.load_config()
        checkin_interval = cfg.get("checkin_interval", 300)
        sysinfo_interval = cfg.get("sysinfo_interval", 900)

        logger.info(f"Device ID: {cfg.get('device_id')}")
        logger.info(f"API URL: {cfg.get('api_url')}")

        last_checkin = 0
        last_sysinfo = 0

        while self.running:
            now = time.time()

            try:
                if now - last_checkin >= checkin_interval:
                    agent.checkin(cfg)
                    last_checkin = now

                if now - last_sysinfo >= sysinfo_interval:
                    agent.report_sysinfo(cfg)
                    last_sysinfo = now

            except Exception as e:
                logger.error(f"Error in agent loop: {e}", exc_info=True)

            # Check for stop signal every 5 seconds
            rc = win32event.WaitForSingleObject(self.stop_event, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(RMMAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(RMMAgentService)
