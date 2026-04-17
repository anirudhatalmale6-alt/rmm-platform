"""Agent configuration management."""

import os
import json

# Default config file location
CONFIG_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "RMMAgent")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_DIR = os.path.join(CONFIG_DIR, "logs")
DATA_DIR = os.path.join(CONFIG_DIR, "data")

# Default settings
DEFAULTS = {
    "api_url": "",
    "api_key": "",
    "device_id": "",
    "customer_id": "",
    "checkin_interval": 300,       # 5 minutes
    "sysinfo_interval": 900,       # 15 minutes
    "log_level": "INFO",
}


def ensure_dirs():
    """Create config, log, and data directories if they don't exist."""
    for d in [CONFIG_DIR, LOG_DIR, DATA_DIR]:
        os.makedirs(d, exist_ok=True)


def load_config():
    """Load config from file, falling back to defaults."""
    ensure_dirs()
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            stored = json.load(f)
            config.update(stored)
    return config


def save_config(config):
    """Save config to file."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_registered():
    """Check if the agent has been registered (has an API key)."""
    config = load_config()
    return bool(config.get("api_key"))
