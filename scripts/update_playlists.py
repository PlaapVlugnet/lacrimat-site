#!/usr/bin/env python3
"""
Weekly Intentionally Blank playlist archive sync.

Fetches Matt's public Spotify playlists, finds the highest-numbered IB episode
(e.g. IB077), and if that episode isn't already in index.html, inserts a new
playlist-card before the trailing "New episode added each Monday" card.

Auth: Spotify Client Credentials flow (app-level token, no user consent).
That's enough because /users/{id}/playlists returns public playlists.

Run from the repo root:
    SPOTIFY_CLIENT_ID=...
    SPOTIFY_CLIENT_SECRET=...
    python scripts/update_playlists.py

Flags:
    --dry-run     Print what would change; do not write the file.
    --html PATH   Path to index.html (default: ./index.html).
    --user USER   Spotify user ID to read playlists from (default: mattzwager).

Exit codes:
    0  Success (file may or may not have been modified).
    1  Fatal error (auth failure, HTML anchor missing, Spotify error, etc.).
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import sys
from typing import Optional

import requests

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Playlist-name prefix that marks a canonical episode.
# Examples matched:    "IB076", "IB060 Winter Solstice", "IB077 Something"
# Examples ignored:    "IB061 pool", "IB057 alts", "IB056 _?"
EPISODE_RE = re.compile(r"^IB(\d+)(?:\s+(.+?))?\s*$")

# Suffixes (after the number) that mean "not the canonical episode".
SUFFIX_DENYLIST = {
    "pool",
    "alts",
    "alt",
    "?",
    "_?",
    "draft",
    "drafts",
    "wip",
    "test",
    "backup",
}

# The trailer "New episode added each Monday" card. We insert before this.
# Use a stable, unique substring (the inline style is unique in the file).
TRAILER_ANCHOR = (
    '<div class="playlist-card" '
    'style="background:var(--ash);display:flex;align-items:center;'
    'justify-content:center;">'
)


# ----------------------------------------------------------------------------
# Spotify auth + fetch
# ----------------------------------------------------------------------------

def get_app_access_token(client_id: str, client_secret: str) -> str:
    """Get an app-level access token via the Client Credentials flow.

    This is all we need to read *public* playlists owned by any user. No
    user consent and no refresh token required; the token lasts ~1 hour,
    which is fine for a single Action run.
    """
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        headers={"Authorization": f"Basic {basic}"},
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_all_playlists(access_token: str, user_id: str) -> list[dict]:
    """Return every public playlist owned by `user_id`, paginated."""
    playlists: list[dict] = []
    url: Optional[str] = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists?limit=50"
    headers = {"Authorization": f"Bearer {access_token}"}
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items") or []:
            # Only include playlists owned by this user (not followed).
            owner = (item.get("owner") or {}).get("id")
            if owner == user_id:
                playlists.append(item)
        url = data.get("next")
    return playlists


# ----------------------------------------------------------------------------
# Episode selection
# ----------------------------------------------------------------------------

def parse_episode(name: str) -> Optional[tuple[int, Optional[str]]]:
    """Return (episode_number, subtitle) or None if name isn't a canonical ep.

    >>> parse_episode("IB076")
    (76, None)
    >>> parse_episode("IB060 Winter Solstice")
    (60, 'Winter Solstice')
    >>> parse_episode("IB061 pool") is None
    True
    >>> parse_episode("IB057 alts") is None
    True
    >>> parse_episode("iB77") is None  # case-sensitive
    True
    >>> parse_episode("Random name") is None
    True
    """
    m = EPISODE_RE.match(name.strip())
    if not m:
        return None
    number = int(m.group(1))
    suffix = (m.group(2) or "").strip()
    if suffix and suffix.lower() in SUFFIX_DENYLIST:
        return None
    return number, (suffix or None)


def pick_latest_episode(playlists: list[dict]) -> Optional[dict]:
    """Return the playlist dict for the highest canonical IB number."""
    best: Optional[tuple[int, dict, Optional[str]]] = None
    for p in playlists:
        name = p.get("name") or ""
        parsed = parse_episode(name)
        if parsed is None:
            continue
        number, subtitle = parsed
        if best is None or number > best[0]:
            best = (number, p, subtitle)
    if best is None:
        return None
    number, playlist, subtitle = best
    return {
        "number": number,
        "subtitle": subtitle,
        "id": playlist.get("id"),
        "url": ((playlist.get("external_urls") or {}).get("spotify")
                or f"https://open.spotify.com/playlist/{playlist.get('id')}"),
        "name": playlist.get("name"),
    }


# ----------------------------------------------------------------------------
# HTML mutation
# ----------------------------------------------------------------------------

def format_episode_label(number: int, subtitle: Optional[str]) -> str:
    pad = f"IB{number:03d}"
    return f"{pad} &mdash; {subtitle}" if subtitle else pad


def render_card(number: int, subtitle: Optional[str], url: str) -> str:
    """Render a playlist-card matching the existing format exactly."""
    label = format_episode_label(number, subtitle)
    # Six-space indent matches the surrounding cards.
    return (
        '      <div class="playlist-card">\n'
        f'        <div class="ep-num">{label}</div>\n'
        '        <div class="ep-title">Intentionally Blank</div>\n'
        f'        <a href="{url}" class="ep-link" target="_blank" '
        'rel="noopener">Open on Spotify &#8599;</a>\n'
        '      </div>\n'
        '\n'
    )


def already_present(html: str, number: int) -> bool:
    """Check whether `IB{number}` is already in the archive.

    Matches the `<div class="ep-num">IBNNN` prefix (with optional subtitle),
    ignoring any later unrelated uses of the string.
    """
    pattern = re.compile(
        r'<div class="ep-num">IB0*' + str(number) + r'(?:\b|[^0-9])'
    )
    return bool(pattern.search(html))


def insert_card(html: str, new_card: str) -> str:
    """Insert `new_card` immediately before the trailer anchor.

    Raises RuntimeError if the anchor isn't found or isn't unique.
    """
    count = html.count(TRAILER_ANCHOR)
    if count == 0:
        raise RuntimeError(
            "Trailer anchor not found in HTML; cannot locate insertion point."
        )
    if count > 1:
        raise RuntimeError(
            f"Trailer anchor appears {count} times; expected exactly 1."
        )
    # Match the 6-space indent the trailer sits at, so the inserted card lines
    # up with it.
    indented_anchor = "      " + TRAILER_ANCHOR
    if indented_anchor in html:
        return html.replace(indented_anchor, new_card + indented_anchor, 1)
    # Fall back to plain anchor replacement (preserves whatever indent exists).
    return html.replace(TRAILER_ANCHOR, new_card.lstrip() + TRAILER_ANCHOR, 1)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.stderr.write(f"ERROR: missing required env var {name}\n")
        sys.exit(1)
    return val


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't write the file; just print what would change.")
    ap.add_argument("--html", default="index.html",
                    help="Path to index.html (default: ./index.html).")
    ap.add_argument("--user", default="mattzwager",
                    help="Spotify user ID (default: mattzwager).")
    args = ap.parse_args()

    client_id = env("SPOTIFY_CLIENT_ID")
    client_secret = env("SPOTIFY_CLIENT_SECRET")

    print(f"Fetching playlists for user '{args.user}'...", flush=True)
    access_token = get_app_access_token(client_id, client_secret)
    playlists = fetch_all_playlists(access_token, args.user)
    print(f"  fetched {len(playlists)} owned playlists", flush=True)

    latest = pick_latest_episode(playlists)
    if latest is None:
        print("No canonical IB playlists found; nothing to do.")
        return 0
    print(f"  latest canonical episode: IB{latest['number']:03d}"
          + (f" - {latest['subtitle']}" if latest['subtitle'] else "")
          + f"  ({latest['url']})", flush=True)

    with open(args.html, encoding="utf-8") as f:
        html = f.read()

    if already_present(html, latest["number"]):
        print(f"IB{latest['number']:03d} already in {args.html}; no change.")
        return 0

    new_card = render_card(latest["number"], latest["subtitle"], latest["url"])
    print(f"Inserting new card for IB{latest['number']:03d}.")
    updated = insert_card(html, new_card)

    if args.dry_run:
        print("--- dry run: not writing file. Card would be: ---")
        print(new_card)
        return 0

    with open(args.html, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"Wrote {args.html}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
