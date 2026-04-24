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
    └── get_refresh_token.py                # NOT NEEDED for this workflow
                                            # (only if you ever switch to
                                            # reading private playlists)
```

---

## Step 1 — Put the site on GitHub Pages

1. Create a new **public** repo on GitHub. Two naming options:
   - `lacrimat-site`  →  site URL will be `https://mattzwager.github.io/lacrimat-site`
   - `mattzwager.github.io`  →  site URL will be `https://mattzwager.github.io`
2. Drag the contents of this folder (everything inside `website/`) into the GitHub web UI's "upload files" flow on the default branch, or push via GitHub Desktop.
3. In the repo: **Settings → Pages**. Set *Source* to **Deploy from a branch**, branch `main`, folder `/ (root)`. Click Save.
4. Wait ~30 seconds; Pages will show the live URL at the top of that same settings page.

---

## Step 2 — Create a Spotify developer app (one-time)

1. Go to <https://developer.spotify.com/dashboard> and log in with your Spotify account.
2. Click **Create app**.
   - Name: anything (e.g. `lacrimat-site`)
   - Description: anything
   - Website: your Pages URL (optional)
   - Redirect URI: can be anything; we don't use it. `http://127.0.0.1/` is fine.
   - Which API/SDKs: **Web API** is enough
3. After creation, open the app's **Settings** page and note:
   - **Client ID**
   - **Client secret** (click "View client secret")

Because we only read public playlists, the Action uses Spotify's Client Credentials flow — no browser consent step and no refresh token.

---

## Step 3 — Add the two secrets to the repo

On GitHub:

1. Repo **Settings → Secrets and variables → Actions → New repository secret**
2. Add each of these (names must match exactly):
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`

---

## Step 4 — Trigger the workflow once to verify

1. Repo **Actions** tab → pick **Update IB playlist archive** in the left sidebar → **Run workflow** → branch `main` → **Run workflow**.
2. The run should finish in under a minute.
3. Open the logs for the "Run playlist sync" step. One of two outcomes is expected:
   - `IBNNN already in index.html; no change.`  → everything works; there's just nothing new to add yet.
   - `Wrote index.html.` followed by a commit pushed to `main` by `github-actions[bot]`. Check the Pages URL — the new card should appear within ~1 minute after the Pages build completes.

From then on, the Action runs automatically every Tuesday at 16:00 UTC (≈10 AM MT).

---

## How the playlist naming is parsed

The script scans every public playlist you own and looks for names matching:

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
