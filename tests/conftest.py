"""Pytest configuration."""
import sys
import os

# Ensure UTF-8 encoding for pytest on Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'