"""System information tools."""

from __future__ import annotations

from typing import Any

from app.tools.registry import RiskLevel, ToolDefinition


def _get_system_info(args: dict[str, Any]) -> dict[str, Any]:
    import platform
    import psutil

    info_type = args.get("type", "all").lower()
    results = {}

    if info_type in ("cpu", "all"):
        results["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        results["cpu_count"] = psutil.cpu_count()
        results["cpu_name"] = platform.processor()

    if info_type in ("ram", "memory", "all"):
        mem = psutil.virtual_memory()
        results["ram_total_gb"] = round(mem.total / (1024**3), 1)
        results["ram_used_gb"] = round(mem.used / (1024**3), 1)
        results["ram_percent"] = mem.percent

    if info_type in ("disk", "all"):
        disk = psutil.disk_usage("C:")
        results["disk_total_gb"] = round(disk.total / (1024**3), 1)
        results["disk_free_gb"] = round(disk.free / (1024**3), 1)
        results["disk_percent"] = disk.percent

    if info_type in ("battery", "all"):
        battery = psutil.sensors_battery()
        if battery:
            results["battery_percent"] = battery.percent
            results["battery_plugged"] = battery.power_plugged

    messages = []
    if "cpu_percent" in results:
        messages.append(f"CPU usage is {results['cpu_percent']}%")
    if "ram_percent" in results:
        messages.append(f"RAM usage is {results['ram_percent']}% ({results['ram_used_gb']} of {results['ram_total_gb']} GB)")
    if "disk_percent" in results:
        messages.append(f"Disk usage is {results['disk_percent']}% ({results['disk_free_gb']} GB free)")
    if "battery_percent" in results:
        status = "plugged in" if results.get("battery_plugged") else "on battery"
        messages.append(f"Battery at {results['battery_percent']}% ({status})")

    return {"success": True, "data": results, "message": ". ".join(messages) + "."}


def _take_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime
    from app.config import get_settings

    settings = get_settings()
    settings.screenshots_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = settings.screenshots_path / f"screenshot_{timestamp}.png"

    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(path))
        return {"success": True, "message": "Screenshot saved.", "path": str(path)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(registry) -> None:
    registry.register(ToolDefinition(
        name="get_system_info",
        description="Get system information (CPU, RAM, disk, battery usage)",
        parameters={"type": {"type": "string", "description": "cpu, ram, disk, battery, or all"}},
        required=[], risk_level=RiskLevel.SAFE, execute=_get_system_info,
    ))
    registry.register(ToolDefinition(
        name="take_screenshot", description="Take a screenshot of the screen",
        parameters={}, required=[], risk_level=RiskLevel.SAFE, execute=_take_screenshot,
    ))
