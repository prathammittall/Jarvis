# JARVIS

A local-first, voice-activated desktop AI assistant for Windows. JARVIS listens for a wake word, transcribes your commands locally, routes them through a local Ollama LLM with a tool-calling architecture, and speaks responses back using offline TTS.

## Features

- **Wake word detection** — openWakeWord (`hey_jarvis` model, swappable)
- **Local speech-to-text** — faster-whisper (configurable model size)
- **Local LLM** — Ollama with structured tool-calling agent
- **Local TTS** — Piper with Windows SAPI fallback
- **20+ tools** — apps, filesystem, browser, terminal, system info, memory
- **Safety layer** — risk classification, confirmation for destructive actions
- **Developer mode** — project shortcuts via `config/projects.json`
- **Long-term memory** — SQLite-backed preferences and facts
- **Desktop UI** — compact PySide6 window + system tray
- **State machine** — explicit lifecycle preventing race conditions

## Architecture

```
Wake Word → STT → Ollama Agent → Tool Registry → Execution → TTS
                      ↑                                    ↓
                 Memory (SQLite)                    UI / Tray
```

## Requirements

- Windows 10/11
- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- Microphone and speakers
- ~4 GB free disk (for models)

### Recommended Hardware

- 8+ GB RAM
- NVIDIA GPU (optional, accelerates Whisper)

## Installation

```bash
git clone <repo-url>
cd Jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py
python scripts/check_system.py
```

Or use the setup script:

```bash
python scripts/setup.py
```

## Ollama Setup

1. Download and install Ollama from https://ollama.com/download
2. Start Ollama (it runs in the system tray)
3. Pull a model:

```bash
ollama pull qwen3:4b
```

4. Set in `.env` (optional):

```env
OLLAMA_MODEL=qwen3:4b
```

Recommended models by hardware:
- **8 GB RAM / no GPU**: `qwen3:4b`, `gemma2:2b`
- **16 GB RAM / GPU**: `qwen3:4b`, `llama3.2:3b`, `mistral:7b`

## Model Selection

| Component | Default | Lightweight Alternative |
|-----------|---------|------------------------|
| LLM | qwen3:4b | gemma2:2b |
| Whisper | small | base or tiny |
| Wake word | hey_jarvis | whisper engine |
| TTS | en_US-lessac-medium | (auto fallback to SAPI) |

## Running JARVIS

```bash
# Full UI mode
python run_jarvis.py

# Debug mode (shows [WAKEWORD] [STT] [OLLAMA] [TOOL] [TTS] logs)
python run_jarvis.py --debug

# CLI text mode (no microphone needed)
python run_jarvis.py --cli

# Headless (no UI, voice only)
python run_jarvis.py --no-ui
```

## Available Commands

| Command | Example |
|---------|---------|
| Time | "What time is it?" |
| Open app | "Open Chrome / VS Code / File Explorer" |
| Web | "Open YouTube", "Search Google for React tutorials" |
| Files | "Create a folder called Test on my desktop" |
| System | "What's my CPU usage?", "Take a screenshot" |
| Projects | "Open my UniEvent project", "Check git status" |
| Memory | "Remember that my project is at D:\Projects\UniEvent" |
| Control | "Volume up", "Lock computer", "Stop talking" |

## Developer Commands

Configure projects in `config/projects.json`:

```json
{
  "unievent": "D:\\Projects\\UniEvent"
}
```

Then say:
- "Open my UniEvent project"
- "Check git status for UniEvent"
- "Start the backend for UniEvent"

## Configuration

Copy `.env.example` to `.env`:

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
WHISPER_MODEL=small
WAKE_WORD_ENABLED=true
TTS_ENABLED=true
CONFIRM_DANGEROUS_ACTIONS=true
LOG_LEVEL=INFO
```

## Testing

```bash
# Automated tests
pytest tests/

# Manual component tests
python scripts/test_microphone.py
python scripts/test_tts.py
python scripts/test_ollama.py
python scripts/test_wakeword.py
python scripts/check_system.py
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Ollama not running | Start Ollama from Start menu |
| No models | `ollama pull qwen3:4b` |
| Microphone not found | Check Windows sound settings, set `MICROPHONE_INDEX` in `.env` |
| Wake word not detecting | Try saying "Hey Jarvis", lower threshold in `.env` |
| TTS not working | Run `python scripts/download_models.py` |
| High CPU usage | Switch to `WHISPER_MODEL=base` |

## Security

- LLM never executes arbitrary code
- All actions go through the tool registry with validation
- Destructive operations require explicit confirmation
- Terminal commands are screened for dangerous patterns
- No API keys or cloud services required

## Adding New Tools

1. Create a function in `app/tools/`
2. Register it with `ToolDefinition` in the module's `register()` function
3. Import the module in `app/tools/registry.py` `_register_all()`

```python
registry.register(ToolDefinition(
    name="my_tool",
    description="Does something useful",
    parameters={"param": {"type": "string"}},
    required=["param"],
    risk_level=RiskLevel.SAFE,
    execute=my_function,
))
```

## Creating Custom Wake Word

1. Train a model with [openWakeWord](https://github.com/dscripka/openWakeWord)
2. Place the `.onnx` model in `models/`
3. Set in `.env`:

```env
WAKE_WORD_MODEL=my_custom_model
```

Or use the whisper engine for keyword detection:

```env
WAKE_WORD_ENGINE=whisper
```

## Packaging as EXE

```bash
pip install pyinstaller
pyinstaller --name JARVIS --windowed --onedir run_jarvis.py
```

Models are NOT bundled. Place them in `models/` next to the executable.

Output: `dist/JARVIS/JARVIS.exe`

## Windows Startup

To start JARVIS with Windows, create a shortcut to `run_jarvis.py` in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

Or use Task Scheduler for more control.

## License

MIT
