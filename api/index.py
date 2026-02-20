"""
Vercel Serverless Function Entry Point
Exports the Flask app for Vercel's Python runtime
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import from server.py and src/
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Import the Flask app from server.py
from server import app

# Export app for Vercel
# Vercel will use this as the WSGI application
__all__ = ['app']
