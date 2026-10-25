"""Compatibility entry point for the complete game start/input audit."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.audit_games import main

if __name__ == '__main__':
    if '--base' not in sys.argv:
        sys.argv += ['--base', os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8187')]
    if '--profiles' not in sys.argv:
        sys.argv += ['--profiles', 'preferred,desktop']
    asyncio.run(main())
