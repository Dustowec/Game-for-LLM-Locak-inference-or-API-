"""burt/__main__.py — entry point for `python -m burt`."""
import asyncio
import sys

from main import main


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))