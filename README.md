# JARVIS

A local-first, voice-activated desktop AI assistant for Windows. JARVIS listens for a wake word, transcribes your commands locally, routes common actions instantly through a fast command router, and uses **Gemini (Google AI)** for complex reasoning — with **Ollama** as an offline fallback.

## Features

- **Wake word detection** — openWakeWord (`hey_jarvis` model, swappable)
- **Local speech-to-text** — faster-whisper (configurable model size)
- **Fast command router** — instant local tools (no LLM) for open/volume/media/etc.
- **Primary LLM** — Google Gemini API (configurable model)
- **Offline fallback** — Ollama (`qwen3:4b` or your choice)
- **Local TTS** — Piper with Windows SAPI fallback
- **20+ tools** — apps, filesystem, browser, terminal, system info, memory
- **Safety layer** — risk classification, confirmation for destructive actions
- **Multilingual** — English / Hindi / Punjabi / Hinglish via STT + router + Gemini
- **Desktop UI** — compact PySide6 window + system tray

## Architecture

```
Windows (background)
   │
   ▼
Jarvis tray runtime
   │
   ├── Wake word (local)  "Jarvis"
   ├── Global hotkey      Ctrl+Space
   ├── Speech → text      (faster-whisper)
   ├── Command router
   │       ├── Local/system commands  (no LLM)
   │       └── AI commands
   │               ├── Gemini PRIMARY
   │               └── Ollama FALLBACK
   ├── Action executor    (registered tools only)
   └── Text → speech
```

Jarvis stays in the **system tray** while you use Chrome, VS Code, Spotify, Discord, games, or File Explorer. You do not need a terminal or VS Code open.

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone and speakers
- Optional: [Gemini API key](https://aistudio.google.com/apikey) for fast cloud reasoning
- Optional: [Ollama](https://ollama.com/download) for offline LLM fallback

## Installation

```bash
git clone <repo-url>
cd Jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py
copy .env.example .env
python scripts/check_system.py
```

## Gemini Setup (primary LLM)

1. Create an API key at [Google AI Studio](https://aistudio.google.com/apikey)
2. Put it in `.env` (never commit this file):

```env
GEMINI_ENABLED=true
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
GEMINI_TIMEOUT=10
```

`GOOGLE_API_KEY` / `GOOGLE_AI_API_KEY` are also accepted if `GEMINI_API_KEY` is empty.

Without a key, Jarvis still runs: fast commands work locally, and Ollama is used if available.

## Ollama Setup (offline fallback)

1. Install Ollama from https://ollama.com/download
2. `ollama pull qwen3:4b`
3. In `.env`:

```env
OLLAMA_MODEL=qwen3:4b
OLLAMA_KEEP_ALIVE=-1
OLLAMA_WARMUP_ENABLED=true
```

To run **without Gemini** (local only):

```env
GEMINI_ENABLED=false
```

## Provider Fallback

1. **Fast commands** — never call an LLM  
2. **Gemini** — if enabled, keyed, and healthy  
3. **Ollama** — if Gemini fails/times out/unavailable  
4. Friendly error if both LLMs are down (fast commands still work)

## Fast Commands

Edit `config/commands.json` to add phrases (English / Hindi / Punjabi) without changing Python.

Examples that stay local (no Gemini):

- open Chrome / Chrome kholo  
- open VS Code  
- volume up / mute  
- pause music  
- take screenshot  
- lock my PC  

## Languages

Jarvis accepts English, Hindi (Devanagari), and Hinglish without a language mode switch.

Pipeline: **STT (auto en/hi)** → **language detect** → **verb/intent normalize** → **fast router** → tool → **TTS in matching language**.

Examples that stay local (no LLM):

| You say | Intent |
|---------|--------|
| Open Chrome | OPEN_APP |
| Chrome kholo / Chrome open karo | OPEN_APP |
| क्रोम खोलो | OPEN_APP |
| Volume badha do | INCREASE_VOLUME |
| Google pe Python search karo | SEARCH_WEB |

Config: `DEFAULT_LANGUAGE=en`, `WHISPER_LANGUAGE=auto`. Hindi TTS uses Windows SAPI when a `hi-IN` voice is installed; otherwise falls back gracefully.

Enable multilingual debug with `DEBUG_MODE=true` or `python run_jarvis.py --debug`.

## Running JARVIS

```bash
python run_jarvis.py
python run_jarvis.py --window
python run_jarvis.py --debug
python run_jarvis.py --cli
```

`python run_jarvis.py` starts in the **system tray** (no dashboard window). Say **Jarvis** or press **Ctrl+Space** to talk.

Tray menu: Enable / Pause Listening, Test Microphone, Settings, Restart, Exit.

To show the compact dashboard: `python run_jarvis.py --window`.

To start with Windows (no console): tray → **Settings** → *Start Jarvis when Windows starts*. That creates a Startup shortcut using `pythonw.exe`.

## Configuration

See `.env.example` for all variables. Important desktop settings:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GEMINI_API_KEY` | (empty) | Primary cloud LLM key — never commit |
| `OLLAMA_ENABLED` | true | Offline fallback when Gemini fails |
| `WAKE_WORD` | jarvis | Local wake phrase |
| `LISTENING_ENABLED` | true | Start with wake-word listening on |
| `GLOBAL_HOTKEY` | ctrl+space | Push-to-talk from any app |
| `UI_START_MINIMIZED` | true | Tray-only until you open the dashboard |
| `START_WITH_WINDOWS` | false | Also toggled from tray Settings |
| `TRUSTED_COMMANDS` | (empty) | Skip confirm for e.g. `shutdown,restart` |
| `ALLOW_LLM_SHELL` | false | Gemini cannot run arbitrary shell commands |
| `APPS_CONFIG` | config/apps.json | Configurable apps / sites / folders |

## Security

- LLM never executes arbitrary shell — only registered tools (`ALLOW_LLM_SHELL=false` by default)  
- Dangerous ops require confirmation unless listed in `TRUSTED_COMMANDS`  
- API keys stay in `.env` (gitignored)  
- No second LLM call just to say "Done" after simple tools  

## Testing

```bash
pytest tests/ -v
python scripts/bench_fast_commands.py
```

## Model Selection

| Component | Default | Lightweight Alternative |
|-----------|---------|------------------------|
| LLM (cloud) | gemini-2.0-flash | gemini-2.5-flash / gemini-1.5-flash |
| LLM (local) | qwen3:4b | gemma2:2b |
| Whisper | small | base or tiny |
| Wake word | hey_jarvis | whisper engine |
| TTS | en_US-lessac-medium | (auto fallback to SAPI) |

## CLI Modes

```bash
python run_jarvis.py
python run_jarvis.py --window
python run_jarvis.py --debug
python run_jarvis.py --cli
python run_jarvis.py --no-ui
```

## Available Commands

| Command | Example |
|---------|---------|
| Time | "What time is it?" |
| Open app | "Open Chrome / VS Code / File Explorer" |
| Web | "Open YouTube", "Search Google for React tutorials" |
| WhatsApp | "Open WhatsApp", "Send a message to Mom on WhatsApp saying I'll be late" |
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

Optional WhatsApp numbers in `config/contacts.json` (country code, no `+`). If a name is missing, Jarvis searches the chat in WhatsApp Web instead:

```json
{
  "mom": "9198XXXXXXXX",
  "rahul": "9198XXXXXXXX"
}
```

Log in to [WhatsApp Web](https://web.whatsapp.com) in Chrome once so the session is saved.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Gemini unavailable | Set `GEMINI_API_KEY` or rely on Ollama / fast commands |
| Ollama not running | Start Ollama; fast commands still work |
| No models | `ollama pull qwen3:4b` |
| Microphone not found | Check Windows sound settings, set `MICROPHONE_INDEX` |
| WhatsApp didn't send | Log in at web.whatsapp.com in Chrome; add the contact number in `config/contacts.json` |
| Wake word not detecting | Say "Jarvis", or press Ctrl+Space, or use tray → Test Microphone |
| TTS not working | `python scripts/download_models.py` |
| Want it at login | Tray → Settings → Start Jarvis when Windows starts |

## Adding New Tools

Register a `ToolDefinition` in `app/tools/` and import it from `registry.py`.

## Packaging as EXE

Development runtime first (`python run_jarvis.py`). When that is stable:

```bash
pyinstaller jarvis.spec
```

`console=False` so there is no terminal window. Output: `dist/JARVIS/JARVIS.exe`

Place a `.env` next to the exe (never bake keys into the build). Models stay external under `models/`. Enable Windows startup from the tray after the first launch.

## License

MIT
