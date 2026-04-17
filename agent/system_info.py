"""System information collection for Windows."""

import platform
import socket
import subprocess
import json


def collect():
    """Collect comprehensive system information. Returns a dict."""
    info = {
        "hostname": _get_hostname(),
        "ip": _get_ip(),
        "os_version": _get_os_version(),
        "cpu_usage": _get_cpu_usage(),
        "ram_total": 0,
        "ram_used": 0,
        "ram_usage": 0,
        "disk_total": 0,
        "disk_used": 0,
        "disk_usage": 0,
        "installed_software": [],
        "windows_updates": [],
    }

    # These require psutil — handle gracefully if not available
    try:
        import psutil

        # RAM
        mem = psutil.virtual_memory()
        info["ram_total"] = round(mem.total / (1024 ** 3), 2)  # GB
        info["ram_used"] = round(mem.used / (1024 ** 3), 2)
        info["ram_usage"] = round(mem.percent, 1)

        # Disk (C: drive)
        disk = psutil.disk_usage("C:\\")
        info["disk_total"] = round(disk.total / (1024 ** 3), 2)
        info["disk_used"] = round(disk.used / (1024 ** 3), 2)
        info["disk_usage"] = round(disk.percent, 1)

        # CPU
        info["cpu_usage"] = psutil.cpu_percent(interval=1)

    except ImportError:
        pass

    # Installed software (from registry via PowerShell)
    info["installed_software"] = _get_installed_software()

    # Windows updates (last 10)
    info["windows_updates"] = _get_windows_updates()

    return info


def _get_hostname():
    return socket.gethostname()


def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def _get_os_version():
    return f"{platform.system()} {platform.version()} ({platform.architecture()[0]})"


def _get_cpu_usage():
    """Fallback CPU usage via wmic if psutil not available."""
    try:
        result = subprocess.run(
            ["wmic", "cpu", "get", "loadpercentage", "/value"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().split("\n"):
            if "LoadPercentage=" in line:
                return float(line.split("=")[1].strip())
    except Exception:
        pass
    return 0.0


def _get_installed_software():
    """Get installed software list from Windows registry via PowerShell."""
    try:
        ps_cmd = (
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
            "| Where-Object { $_.DisplayName } "
            "| Select-Object DisplayName, DisplayVersion, Publisher "
            "| ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=30,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return [
                {
                    "name": item.get("DisplayName", ""),
                    "version": item.get("DisplayVersion", ""),
                    "publisher": item.get("Publisher", ""),
                }
                for item in data[:200]  # Limit to 200 entries
            ]
    except Exception:
        pass
    return []


def _get_windows_updates():
    """Get recent Windows updates via PowerShell."""
    try:
        ps_cmd = (
            "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 10 "
            "| Select-Object HotFixID, Description, InstalledOn "
            "| ConvertTo-Json -Compress"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=30,
        )
        if result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return [
                {
                    "id": item.get("HotFixID", ""),
                    "description": item.get("Description", ""),
                    "installed_on": str(item.get("InstalledOn", "")),
                }
                for item in data
            ]
    except Exception:
        pass
    return []
