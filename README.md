# spotify-bpm

CLI tool that takes a Spotify playlist URL and displays the BPM (tempo) of each track, sorted from slowest to fastest.

BPM data is sourced from [GetSongBPM](https://getsongbpm.com).

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### API Keys

You'll need two sets of credentials:

1. **Spotify** - Create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) to get a client ID and secret.
2. **GetSongBPM** - Register at [getsongbpm.com/api](https://getsongbpm.com/api) for a free API key.

### Install

```sh
git clone <this-repo>
cd spotify-bpm
cp .env.example .env
# Fill in your API keys in .env
uv sync
```

## Usage

```sh
# Default table output
uv run spotify-bpm "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# CSV output
uv run spotify-bpm --format csv "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# JSON output
uv run spotify-bpm --format json "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
```

You can also pass a Spotify URI or raw playlist ID:

```sh
uv run spotify-bpm spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
uv run spotify-bpm 37i9dQZF1DXcBWIGoYBM5M
```

### Example Output

```
Track                                  Artist                    BPM
-----------------------------------------------------------------------
Someone Like You                       Adele                      67
Bohemian Rhapsody                      Queen                      72
Blinding Lights                        The Weeknd                171
```

Progress is printed to stderr, so you can pipe the output cleanly:

```sh
uv run spotify-bpm --format csv "https://open.spotify.com/playlist/..." > playlist.csv
```
