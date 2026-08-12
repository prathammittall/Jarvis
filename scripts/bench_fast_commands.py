"""Benchmark fast router vs noting Ollama would be needed."""

from __future__ import annotations

import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from app.brain.agent import Agent
    from app.brain.fast_commands import get_fast_router
    from app.config import get_settings

    settings = get_settings()
    settings.ensure_directories()

    router = get_fast_router()
    agent = Agent()

    print("JARVIS PERFORMANCE CHECK")
    print("=" * 40)
    print(f"Fast commands enabled: {settings.fast_commands_enabled}")
    print(f"Ollama keep_alive: {settings.ollama_keep_alive}")
    print(f"Ollama warmup: {settings.ollama_warmup_enabled}")
    print()

    fast_phrases = [
        "open chrome",
        "chrome kholo",
        "open vscode",
        "volume up",
        "mute",
        "pause music",
        "take a screenshot",
    ]

    print("Fast router matches:")
    for phrase in fast_phrases:
        t0 = time.perf_counter()
        matched = router.match(phrase)
        dt = time.perf_counter() - t0
        status = f"{matched.action}" if matched else "NO MATCH"
        print(f"  [{dt*1000:6.2f} ms] {phrase!r:30s} -> {status}")

    print()
    print("Agent path (fast commands — should NOT call Ollama):")
    for phrase in ("mute", "what time is it"):
        t0 = time.perf_counter()
        result = agent.process_command(phrase)
        dt = time.perf_counter() - t0
        print(
            f"  [{dt*1000:6.1f} ms] {phrase!r}"
            f" source={result.get('source')} tool={result.get('tool')}"
            f" ok={result.get('success')}"
        )

    print()
    complex_cmd = "analyze my project and tell me which files need refactoring"
    print(f"Complex (should use Ollama if running): {complex_cmd!r}")
    t0 = time.perf_counter()
    # Only match check — don't wait for full Ollama unless available
    matched = router.match(complex_cmd)
    print(f"  Fast match: {matched}")
    if agent.ollama.is_running():
        result = agent.process_command(complex_cmd)
        dt = time.perf_counter() - t0
        print(f"  [{dt:.2f} s] source={result.get('source')} success={result.get('success')}")
        print(f"  response: {result.get('response', '')[:120]}")
    else:
        print("  Ollama not running — skipped live LLM call")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
