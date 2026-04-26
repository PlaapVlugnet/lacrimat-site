# Lacrimat site — setup guide

## Repo layout

```
lacrimat-site/
├── index.html                              # the site (serves as GitHub Pages root)
├── style.css
├── SETUP.md                                # this file
├── .github/workflows/update-playlists.yml  # weekly Spotify sync
└── scripts/
    ├── update_playlists.py                 # run by the weekly Action
    └── get_refresh_token.py                # run ONCE locally to get the
                                            # SPOTIFY_REFRESH_TOKEN secret
```

---

## Step 1 — Put the site on GitHub Pages

1. Create a new **public** repo on GitHub. Two naming options:
   - `lacrimat-site`  →  site URL will be `https://mattzwager.github.io/lacrimat-site`
   - `mattzwager.github.io`  →  site URL will be `https://mattzwager.github.io`
2. Drag the contents of this folder (everything inside `website/`) into the GitHub web UI's "upload files" flow on the default branch, or push via GitHub Desktop. (Note: macOS Finder hides the `.github/` folder by default. Toggle it visible with **Cmd+Shift+.**, or use GitHub's "Create new file" with the path `.github/workflows/update-playlists.yml` to create the file directly in the web UI.)
3. In the repo: **Settings → Pages**. Set *Source* to **Deploy from a branch**, branch `main`, folder `/ (root)`. Click Save.
4. Wait ~30 seconds; Pages will show the live URL at the top of that same settings page.

---

## Step 2 — Create a Spotify developer app (one-time)

1. Go to <https://developer.spotify.com/dashboard> and log in with your Spotify account.
2. Click **Create app**.
   - Name: anything (e.g. `lacrimat-site`)
   - Description: anything
   - Website: your Pages URL (optional)
   - Redirect URI: must be exactly `http://127.0.0.1:8888/callback` (Spotify no longer accepts `localhost` — use the IP).
   - Which API/SDKs: **Web API** is enough
3. After creation, open the app's **Settings** page and note:
   - **Client ID**
   - **Client secret** (click "View client secret")

Why we need user auth (not just Client Credentials): as of late 2024, Spotify blocks app-only tokens from hitting `/v1/users/{id}/playlists`. Using a refresh token lets the script call `/v1/me/playlists` instead, which still works in Development Mode.

---

## Step 3 — Get a refresh token (one-time, local)

Run this on your own machine, in this folder:

```bash
export SPOTIFY_CLIENT_ID=<your client id>
export SPOTIFY_CLIENT_SECRET=<your client secret>
python scripts/get_refresh_token.py
```

It will:
- Open your browser to Spotify's authorize page (scope: `playlist-read-private`).
- Catch the redirect at `http://127.0.0.1:8888/callback`.
- Print three values to copy into GitHub repo secrets.

If the browser doesn't auto-open, the script prints a URL — paste it manually. After you click **Agree** on Spotify, the terminal will show:

```
SPOTIFY_CLIENT_ID     = ...
SPOTIFY_CLIENT_SECRET = ...
SPOTIFY_REFRESH_TOKEN = ...
```

The refresh token is long-lived; you only do this once.

---

## Step 4 — Add the three secrets to the repo

On GitHub:

1. Repo **Settings → Secrets and variables → Actions → New repository secret**
2. Add each of these (names must match exactly):
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`

---

## Step 5 — Trigger the workflow once to verify

1. Repo **Actions** tab → pick **Update IB playlist archive** in the left sidebar → **Run workflow** → branch `main` → **Run workflow**.
2. The run should finish in under a minute.
3. Open the logs for the "Run playlist sync" step. One of two outcomes is expected:
   - `IBNNN already in index.html; no change.`  → everything works; there's just nothing new to add yet.
   - `Wrote index.html.` followed by a commit pushed to `main` by `github-actions[bot]`. Check the Pages URL — the new card should appear within ~1 minute after the Pages build completes.

From then on, the Action runs automatically every Tuesday at 16:00 UTC (≈10 AM MT).

---

## How the playlist naming is parsed

The script scans every playlist you own and looks for names matching:

```
IB<number>[ <optional subtitle>]
```

- `IB001`, `IB076`, `IB077` → canonical episode, subtitle blank.
- `IB060 Winter Solstice` → canonical episode, subtitle `Winter Solstice` (rendered as `IB060 — Winter Solstice`).
- `IB061 pool`, `IB057 alts`, `IB056 _?` → ignored as non-canonical (see `SUFFIX_DENYLIST` in `update_playlists.py`).
- Anything not starting with `IB<digits>` → ignored.

The highest canonical number wins. If that number is already in `index.html`, nothing is committed.

---

## Local testing

```bash
# Dry-run against the checked-in HTML (no file write):
export SPOTIFY_CLIENT_ID=...
export SPOTIFY_CLIENT_SECRET=...
export SPOTIFY_REFRESH_TOKEN=...
python scripts/update_playlists.py --dry-run

# Run against a different file (e.g. a scratch copy):
python scripts/update_playlists.py --html /tmp/index.copy.html
```

---

## Things to fill in later

- Lacrimat logo, SoundCloud/Bandcamp/Spotify embeds on page 1
- Real URLs for the Bandcamp / Spotify / SoundCloud / Subvert badges
- Three to five project names + descriptions + SoundCloud embeds on page 3
- SPL logo and Facebook-sourced gallery images on page 4
