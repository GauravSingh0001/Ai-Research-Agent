"""
Vercel Serverless Function Entry Point
Exports the Flask app as a WSGI application for Vercel

Vercel will automatically call this module and use the 'app' object
as the WSGI handler for all incoming requests.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import from server.py and src/
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Ensure VERCEL environment variable is set
if not os.environ.get("VERCEL"):
    os.environ["VERCEL"] = "1"

# Import the Flask app from server.py
# This will create the app instance with all routes configured
from server import app

# Vercel will use this 'app' object as the WSGI application handler
# No need to call app.run() — Vercel handles that automatically

__all__ = ['app']

