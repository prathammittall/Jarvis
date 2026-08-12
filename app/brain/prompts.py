"""System prompts for the JARVIS agent."""

SYSTEM_PROMPT = """You are the reasoning engine for Jarvis, a local Windows desktop assistant.

The user may speak English, Hindi, Punjabi, Hinglish, or mixed code-switching.
Understand naturally. Preserve app names, paths, URLs, project names, and technical terms.
Do not unnecessarily translate the user's words.

Your job: select exactly one tool (or respond) for the command.
Keep spoken "response" to one short sentence in the user's style.
Never invent tools. Never claim an action succeeded unless a tool ran.
Never emit shell code. Prefer structured tool calls when available.

If using JSON (no native tool call), return ONLY:
{"action":"<tool|respond>","arguments":{},"response":"<short>","needs_confirmation":false}
"""

TOOL_SELECTION_TEMPLATE = """Command: {command}

Context (recent, limited):
{context}

Memories (limited):
{memories}

Available tools:
{tools}

Select one tool or respond. Be concise."""

CONFIRMATION_PROMPT = """The user was asked to confirm this action: {action_description}
User response: {user_response}

Did the user confirm? Respond with JSON:
{{"confirmed": true/false, "response": "<what to say>"}}"""

# Keyword → tool names used for prompt filtering
TOOL_FILTER_KEYWORDS: dict[str, list[str]] = {
    "open_application": ["open", "launch", "start", "close", "app", "chrome", "vscode", "spotify", "discord", "notepad", "calculator", "explorer", "terminal", "edge", "firefox", "kholo", "chala", "khol", "खोलो", "खोल"],
    "close_application": ["close", "quit", "exit", "kill", "band", "बंद"],
    "open_project": ["project", "unievent", "repo", "repository", "workspace"],
    "open_url": ["url", "website", "http", "www", "site"],
    "google_search": ["google", "search google", "search for", "गूगल", "dhoondo", "search karo"],
    "youtube_search": ["youtube", "yt", "यूट्यूब"],
    "open_youtube": ["youtube", "यूट्यूब"],
    "web_search": ["search", "google", "web", "internet", "weather", "मौसम"],
    "create_folder": ["folder", "directory", "mkdir", "create folder", "folder banao", "फोल्डर"],
    "create_file": ["create file", "write file", "new file", "notes.txt"],
    "read_file": ["read file", "open file", "show file"],
    "list_directory": ["list", "show files", "downloads", "desktop", "documents"],
    "delete_path": ["delete", "remove", "erase"],
    "rename_path": ["rename"],
    "move_path": ["move"],
    "copy_path": ["copy"],
    "open_folder": ["open folder", "open directory"],
    "run_terminal_command": ["npm", "git", "python", "terminal", "command", "shell", "gradle", "build"],
    "git_status": ["git status", "git"],
    "start_project": ["start backend", "npm run", "start project", "dev server"],
    "volume_control": ["volume", "mute", "unmute", "awaz", "वॉल्यूम", "आवाज़", "badha", "kam"],
    "lock_computer": ["lock"],
    "system_power": ["shutdown", "restart", "reboot", "sleep", "band karo"],
    "get_time": ["time", "clock", "date", "batao"],
    "get_system_info": ["cpu", "ram", "memory", "disk", "battery", "system"],
    "take_screenshot": ["screenshot", "capture screen"],
    "media_control": ["play", "pause", "music", "song", "track", "next", "previous", "gaana", "chalao"],
    "remember": ["remember", "yaad"],
    "forget": ["forget"],
    "recall": ["what do you remember", "recall"],
    "stop": ["stop talking", "be quiet", "shut up"],
}
