"""
Vercel Python serverless entry. Exposes the Flask WSGI `app` so Vercel routes
/api/* here. The repo root is added to sys.path so the app's modules (server,
auth, store, …) import correctly from inside the api/ function directory.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app  # noqa: E402  (Vercel detects this WSGI `app`)
