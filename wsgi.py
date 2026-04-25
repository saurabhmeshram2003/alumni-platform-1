"""
wsgi.py
────────────────────────────────────────────────────────────────────
Production entry point for gunicorn.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

Railway / Render reads this via Procfile or nixpacks.toml start command.
────────────────────────────────────────────────────────────────────
"""
from app import create_app

app = create_app()
