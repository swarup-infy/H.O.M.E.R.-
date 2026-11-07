"""Lightweight, read-only system telemetry for HOMER."""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Any


def system_status() -> dict[str, Any]:
    """Return basic resource and battery status without persisting telemetry."""
    result: dict[str, Any] = {
        "ok": True,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_percent": None,
        "memory_total_mb": None,
        "memory_available_mb": None,
        "memory_percent": None,
        "battery_percent": None,
        "battery_plugged_in": None,
        "disk_free_gb": None,
    }
    try:
        import psutil
        memory = psutil.virtual_memory()
        result.update({
            "cpu_percent": psutil.cpu_percent(interval=0.15),
            "memory_total_mb": round(memory.total / 1024 / 1024),
            "memory_available_mb": round(memory.available / 1024 / 1024),
            "memory_percent": memory.percent,
            "disk_free_gb": round(psutil.disk_usage(str(Path.home())).free / 1024**3, 1),
        })
        battery = psutil.sensors_battery()
        if battery is not None:
            result["battery_percent"] = round(battery.percent)
            result["battery_plugged_in"] = battery.power_plugged
    except ImportError:
        result["warning"] = "Install psutil to enable CPU, RAM, disk and battery telemetry."
    except Exception as exc:
        result["warning"] = f"Some telemetry is unavailable ({type(exc).__name__})."
    return result
