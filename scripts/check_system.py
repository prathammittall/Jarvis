"""System diagnostic script for JARVIS."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def check_os() -> dict:
    return {
        "name": platform.system(),
        "version": platform.version(),
        "release": platform.release(),
        "machine": platform.machine(),
    }


def check_python() -> dict:
    return {
        "version": platform.python_version(),
        "executable": sys.executable,
        "in_path": shutil.which("python") is not None,
    }


def check_ram() -> float | None:
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024**3), 1)
    except ImportError:
        return None


def check_cpu() -> dict:
    info = {"name": platform.processor(), "cores": os.cpu_count()}
    try:
        import psutil
        info["physical_cores"] = psutil.cpu_count(logical=False)
        info["logical_cores"] = psutil.cpu_count(logical=True)
    except ImportError:
        pass
    return info


def check_gpu() -> list[str]:
    gpus = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                gpus.append(line.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not gpus:
        try:
            import wmi  # type: ignore
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                if gpu.Name:
                    gpus.append(gpu.Name)
        except ImportError:
            pass
        except Exception:
            pass

    return gpus or ["None detected"]


def check_disk() -> dict:
    try:
        usage = shutil.disk_usage("C:")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
        }
    except Exception:
        return {"total_gb": None, "free_gb": None}


def find_ollama() -> str | None:
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]
    path = shutil.which("ollama")
    if path:
        return path
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def check_ollama() -> dict:
    result = {"installed": False, "path": None, "running": False, "models": [], "error": None}
    path = find_ollama()
    if path:
        result["installed"] = True
        result["path"] = path

    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            result["running"] = True
            result["models"] = [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        if result["installed"]:
            result["error"] = "Installed but server not running. Start Ollama from the Start menu."
        else:
            result["error"] = str(e) if not result["installed"] else result.get("error")

    return result


def check_microphone() -> dict:
    result = {"available": False, "devices": [], "default": None, "error": None}
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                inputs.append({"index": i, "name": d["name"]})
        result["devices"] = inputs
        result["available"] = len(inputs) > 0
        try:
            default = sd.query_devices(kind="input")
            result["default"] = default.get("name", "Unknown")
        except Exception:
            pass
    except ImportError:
        result["error"] = "sounddevice not installed. Run: pip install sounddevice"
    except Exception as e:
        result["error"] = str(e)
    return result


def check_speaker() -> dict:
    result = {"available": False, "devices": [], "default": None, "error": None}
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        outputs = []
        for i, d in enumerate(devices):
            if d["max_output_channels"] > 0:
                outputs.append({"index": i, "name": d["name"]})
        result["devices"] = outputs
        result["available"] = len(outputs) > 0
        try:
            default = sd.query_devices(kind="output")
            result["default"] = default.get("name", "Unknown")
        except Exception:
            pass
    except ImportError:
        result["error"] = "sounddevice not installed. Run: pip install sounddevice"
    except Exception as e:
        result["error"] = str(e)
    return result


def check_packages() -> dict[str, bool]:
    packages = [
        "faster_whisper", "sounddevice", "openwakeword", "onnxruntime",
        "PySide6", "playwright", "piper", "psutil", "requests",
    ]
    result = {}
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_").split(".")[0])
            result[pkg] = True
        except ImportError:
            result[pkg] = False
    return result


def main() -> int:
    print("JARVIS SYSTEM CHECK")
    print("=" * 40)

    os_info = check_os()
    py_info = check_python()
    ram = check_ram()
    cpu = check_cpu()
    gpus = check_gpu()
    disk = check_disk()
    ollama = check_ollama()
    mic = check_microphone()
    speaker = check_speaker()
    packages = check_packages()

    _section("System")
    print(f"OS: {os_info['name']} {os_info['release']} ({os_info['version'][:40]})")
    print(f"Python: {py_info['version']} ({py_info['executable']})")
    if ram:
        print(f"RAM: {ram} GB")
    print(f"CPU: {cpu.get('name', 'Unknown')} ({cpu.get('logical_cores', cpu.get('cores', '?'))} threads)")
    print(f"GPU: {', '.join(gpus)}")
    if disk["total_gb"]:
        print(f"Disk (C:): {disk['free_gb']} GB free / {disk['total_gb']} GB total")

    _section("Ollama")
    if ollama["installed"]:
        print(f"Ollama: Installed ({ollama['path']})")
    else:
        print("Ollama: NOT INSTALLED")
        print("  Download from: https://ollama.com/download")
        print("  After install, run: ollama pull qwen3:4b")

    if ollama["running"]:
        print("Ollama Server: Running")
        if ollama["models"]:
            print(f"Models: {', '.join(ollama['models'])}")
        else:
            print("Models: None installed")
            print("  Run: ollama pull qwen3:4b")
    else:
        print("Ollama Server: NOT RUNNING")
        if ollama.get("error"):
            print(f"  {ollama['error']}")

    _section("Audio")
    if mic["available"]:
        print(f"Microphone: Available ({mic['default']})")
        for d in mic["devices"][:3]:
            print(f"  [{d['index']}] {d['name']}")
    else:
        print(f"Microphone: NOT AVAILABLE")
        if mic.get("error"):
            print(f"  {mic['error']}")

    if speaker["available"]:
        print(f"Speaker: Available ({speaker['default']})")
    else:
        print(f"Speaker: NOT AVAILABLE")
        if speaker.get("error"):
            print(f"  {speaker['error']}")

    _section("Python Packages")
    missing = [k for k, v in packages.items() if not v]
    installed = [k for k, v in packages.items() if v]
    if installed:
        print(f"Installed: {', '.join(installed)}")
    if missing:
        print(f"Missing: {', '.join(missing)}")
        print("  Run: pip install -r requirements.txt")

    _section("Overall Status")
    issues = []
    if not ollama["installed"]:
        issues.append("Install Ollama")
    elif not ollama["running"]:
        issues.append("Start Ollama server")
    elif not ollama["models"]:
        issues.append("Pull an Ollama model (ollama pull qwen3:4b)")
    if not mic["available"] and not mic.get("error", "").startswith("sounddevice not"):
        issues.append("Connect a microphone")
    if missing:
        issues.append("Install Python dependencies")

    if not issues:
        print("READY - All systems go!")
        return 0
    else:
        print("NOT READY")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
