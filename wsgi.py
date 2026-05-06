"""
wsgi.py
────────────────────────────────────────────────────────────────────
Production entry point for gunicorn.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

Railway / Render reads this via Procfile or nixpacks.toml start command.
────────────────────────────────────────────────────────────────────
"""
# Import the module-level app (already initialized in app.py)
from app import app  # noqa: F401