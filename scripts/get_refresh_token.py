#!/usr/bin/env python3
"""
One-time helper to obtain a Spotify refresh token for the Actions workflow.

Run this ONCE on your own machine:

    export SPOTIFY_CLIENT_ID=...
    export SPOTIFY_CLIENT_SECRET=...
    python scripts/get_refresh_token.py

It will:
  1. Open your browser to the Spotify authorize URL with the correct scope.
  2. Spin up a tiny local server on http://localhost:8888/callback.
  3. Catch the redirect, exchange the code for a refresh_token.
  4. Print the three values you need to paste into GitHub repo secrets:
        SPOTIFY_CLIENT_ID
        SPOTIFY_CLIENT_SECRET
        SPOTIFY_REFRESH_TOKEN

Prerequisites (set up once in the Spotify developer dashboard):
  - App created at https://developer.spotify.com/dashboard
  - Redirect URI set to exactly:  http://localhost:8888/callback
  - Client ID + Secret exported as env vars before running this script.

This file does not need to live in the repo; you can delete it after use.
It uses only the Python stdlib plus `requests`.
"""

from __future__ import annotations

import base64
import http.server
import os
import secrets
import sys
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-public"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105

_auth_code: str | None = None
_state_sent: str = secrets.token_urlsafe(16)


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802  (stdlib API)
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        if params.get("state", [None])[0] != _state_sent:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch. Aborting.")
            return
        if "error" in params:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Spotify error: {params['error'][0]}".encode())
            return
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Got it. You can close this tab.\n")

    def log_message(self, *_args, **_kwargs) -> None:  # quiet the console
        pass


def main() -> int:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.stderr.write(
            "ERROR: set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars "
            "before running this script.\n"
        )
        return 1

    # Build the authorize URL and launch the browser.
    q = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": _state_sent,
        "scope": SCOPE,
    })
    url = f"{AUTHORIZE_URL}?{q}"
    print("Opening browser for Spotify authorization...")
    print(f"If it doesn't open, visit this URL manually:\n\n{url}\n")
    webbrowser.open(url)

    # Listen for exactly one callback, then shut down.
    server = http.server.HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    print("Waiting for callback on http://127.0.0.1:8888/callback ...")
    while _auth_code is None:
        server.handle_request()

    # Exchange the auth code for tokens.
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {basic}"},
        data={
            "grant_type": "authorization_code",
            "code": _auth_code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        sys.stderr.write(f"No refresh_token in response: {tokens}\n")
        return 1

    print("\n========  COPY THESE INTO GITHUB REPO SECRETS  ========\n")
    print(f"SPOTIFY_CLIENT_ID     = {client_id}")
    print(f"SPOTIFY_CLIENT_SECRET = {client_secret}")
    print(f"SPOTIFY_REFRESH_TOKEN = {refresh_token}")
    print("\nRepo  ->  Settings  ->  Secrets and variables  ->  Actions")
    print("=======================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
