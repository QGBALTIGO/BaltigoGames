"""Compatibility entry point for the complete portal browser matrix."""
import asyncio
from e2e_portal import main

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
