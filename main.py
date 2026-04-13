# AI-assisted (Claude Code, claude.ai) — https://claude.ai
"""
Entry point: serve the Civic Lenses app locally.

Usage:
    python main.py
"""

import http.server
import os
import webbrowser


PORT = 8000
APP_DIR = os.path.join(os.path.dirname(__file__), "app")


if __name__ == "__main__":
    os.chdir(APP_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("", PORT), handler)
    url = f"http://localhost:{PORT}"
    print(f"Serving Civic Lenses at {url}")
    webbrowser.open(url)
    server.serve_forever()
