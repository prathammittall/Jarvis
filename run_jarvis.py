#!/usr/bin/env python3
"""Launch JARVIS desktop assistant."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="JARVIS Local Desktop Assistant")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--cli", action="store_true", help="Run in CLI text mode")
    parser.add_argument("--no-ui", action="store_true", help="Run without UI (headless)")
    args = parser.parse_args()

    from app.main import main as app_main
    sys.exit(app_main(debug=args.debug, cli=args.cli, no_ui=args.no_ui))


if __name__ == "__main__":
    main()
