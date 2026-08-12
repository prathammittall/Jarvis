# JARVIS

A local-first, voice-activated desktop AI assistant for Windows. JARVIS listens for a wake word, transcribes your commands locally, routes common actions instantly through a fast command router, and uses **Grok (xAI)** for complex reasoning — with **Ollama** as an offline fallback.

## Features

- **Wake word detection** — openWakeWord (`hey_jarvis` model, swappable)
- **Local speech-to-text** — faster-whisper (configurable model size)
- **Fast command router** — instant local tools (no LLM) for open/volume/media/etc.
- **Primary LLM** — xAI Grok API (configurable model)
- **Offline fallback** — Ollama (`qwen3:4b` or your choice)
- **Local TTS** — Piper with Windows SAPI fallback
- **20+ tools** — apps, filesystem, browser, terminal, system info, memory
- **Safety layer** — risk classification, confirmation for destructive actions
- **Multilingual** — English / Hindi / Punjabi / Hinglish via STT + router + Grok
- **Desktop UI** — compact PySide6 window + system tray

## Architecture

```
Wake Word → STT → FastCommandRouter
                      │
              ┌───────┴────────┐
           MATCH            NO MATCH
              │                 │
         Local Tool           Grok
              │                 │
              │            (fail → Ollama)
              │                 │
              └────────┬────────┘
                       ▼
                    Result → TTS
```

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone and speakers
- Optional: [Grok API key](https://console.x.ai) for fast cloud reasoning
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

## Grok Setup (primary LLM)

1. Create an API key at [console.x.ai](https://console.x.ai)
2. Put it in `.env` (never commit this file):

```env
GROK_ENABLED=true
GROK_API_KEY=xai-your-key-here
GROK_MODEL=grok-3-mini
GROK_BASE_URL=https://api.x.ai/v1
GROK_TIMEOUT=10
```

`XAI_API_KEY` is also accepted as an alias if `GROK_API_KEY` is empty.

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

To run **without Grok** (local only):

```env
GROK_ENABLED=false
```

## Provider Fallback

1. **Fast commands** — never call an LLM  
2. **Grok** — if enabled, keyed, and healthy  
3. **Ollama** — if Grok fails/times out/unavailable  
4. Friendly error if both LLMs are down (fast commands still work)

## Fast Commands

Edit `config/commands.json` to add phrases (English / Hindi / Punjabi) without changing Python.

Examples that stay local (no Grok):

- open Chrome / Chrome kholo  
- open VS Code  
- volume up / mute  
- pause music  
- take screenshot  
- lock my PC  

## Languages

Jarvis accepts English, Hindi, Punjabi, and mixed speech. The fast router matches configured phrases; Grok understands code-switching for complex requests. No manual language switch is required.

## Running JARVIS

```bash
python run_jarvis.py
python run_jarvis.py --debug
python run_jarvis.py --cli
```

## Configuration

See `.env.example` for all variables including `GROK_*`, `OLLAMA_*`, Whisper, wake word, and UI.

## Security

- LLM never executes arbitrary code — only registered tools  
- Dangerous ops require confirmation  
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
| LLM (cloud) | grok-3-mini | grok-2-latest / your console model |
| LLM (local) | qwen3:4b | gemma2:2b |
| Whisper | small | base or tiny |
| Wake word | hey_jarvis | whisper engine |
| TTS | en_US-lessac-medium | (auto fallback to SAPI) |

## CLI Modes

```bash
python run_jarvis.py
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

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Grok unavailable | Set `GROK_API_KEY` or rely on Ollama / fast commands |
| Ollama not running | Start Ollama; fast commands still work |
| No models | `ollama pull qwen3:4b` |
| Microphone not found | Check Windows sound settings, set `MICROPHONE_INDEX` |
| Wake word not detecting | Say "Jarvis", or use Click to Talk / Space |
| TTS not working | `python scripts/download_models.py` |

## Adding New Tools

Register a `ToolDefinition` in `app/tools/` and import it from `registry.py`.

## Packaging as EXE

```bash
pyinstaller jarvis.spec
```

Models stay external. Output: `dist/JARVIS/JARVIS.exe`

## License

MIT
