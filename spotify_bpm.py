#!/usr/bin/env python3
"""CLI tool to fetch BPM (tempo) for each track in a Spotify playlist."""

import argparse
import csv
import io
import json
import os
import sys
from urllib.parse import quote_plus

import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

GETSONGBPM_BASE = "https://api.getsong.co"


def get_spotify_client():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set.", file=sys.stderr)
        sys.exit(1)
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret
    ))


def get_getsongbpm_api_key():
    key = os.environ.get("GETSONGBPM_API_KEY")
    if not key:
        print("Error: GETSONGBPM_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    return key


def extract_playlist_id(url: str) -> str:
    """Extract playlist ID from a Spotify URL or URI."""
    # Handle URLs like https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
    if "open.spotify.com/playlist/" in url:
        path = url.split("open.spotify.com/playlist/")[1]
        return path.split("?")[0].split("/")[0]
    # Handle URIs like spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
    if url.startswith("spotify:playlist:"):
        return url.split("spotify:playlist:")[1]
    # Assume it's already a raw ID
    return url.strip()


def fetch_playlist_tracks(sp, playlist_id: str) -> list[dict]:
    """Fetch all tracks from a Spotify playlist, handling pagination."""
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while True:
        for item in results["items"]:
            track = item.get("track")
            if not track or not track.get("name"):
                continue
            artists = ", ".join(a["name"] for a in track["artists"])
            tracks.append({
                "name": track["name"],
                "artist": artists,
                "artist_first": track["artists"][0]["name"] if track["artists"] else "",
            })
        if results["next"]:
            results = sp.next(results)
        else:
            break
    return tracks


def lookup_bpm(api_key: str, track_name: str, artist: str) -> str:
    """Look up BPM for a track using the GetSongBPM API.

    Searches by song title, then matches against artist name.
    Returns the tempo as a string, or "unknown" if not found.
    """
    try:
        search_url = f"{GETSONGBPM_BASE}/search/?api_key={api_key}&type=song&lookup={quote_plus(track_name)}"
        resp = requests.get(search_url, timeout=10)
        if resp.status_code != 200:
            return "unknown"
        data = resp.json()
        search_results = data.get("search", [])
        if not search_results:
            return "unknown"

        artist_lower = artist.lower()
        # Try to find an exact artist match first
        for result in search_results:
            result_artist = result.get("artist", {}).get("name", "").lower()
            if result_artist == artist_lower:
                song_id = result["id"]
                return _fetch_tempo(api_key, song_id)

        # Fall back to partial match
        for result in search_results:
            result_artist = result.get("artist", {}).get("name", "").lower()
            if artist_lower in result_artist or result_artist in artist_lower:
                song_id = result["id"]
                return _fetch_tempo(api_key, song_id)

        # Last resort: use the first result if the title matches closely
        first = search_results[0]
        if first.get("title", "").lower() == track_name.lower():
            return _fetch_tempo(api_key, first["id"])

        return "unknown"
    except (requests.RequestException, KeyError, IndexError):
        return "unknown"


def _fetch_tempo(api_key: str, song_id: str) -> str:
    """Fetch the tempo for a specific song ID."""
    try:
        url = f"{GETSONGBPM_BASE}/song/?api_key={api_key}&id={song_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return "unknown"
        data = resp.json()
        tempo = data.get("song", {}).get("tempo", "")
        return str(tempo) if tempo else "unknown"
    except (requests.RequestException, KeyError):
        return "unknown"


def format_table(tracks: list[dict]) -> str:
    """Format tracks as an aligned table."""
    if not tracks:
        return "No tracks found."

    name_width = max(len(t["name"]) for t in tracks)
    artist_width = max(len(t["artist"]) for t in tracks)
    # Clamp column widths for readability
    name_width = min(max(name_width, 5), 50)
    artist_width = min(max(artist_width, 6), 40)

    header = f"{'Track':<{name_width}}  {'Artist':<{artist_width}}  {'BPM':>5}"
    separator = "-" * len(header)
    lines = [header, separator]
    for t in tracks:
        name = t["name"][:name_width]
        artist = t["artist"][:artist_width]
        lines.append(f"{name:<{name_width}}  {artist:<{artist_width}}  {t['bpm']:>5}")
    return "\n".join(lines)


def format_csv(tracks: list[dict]) -> str:
    """Format tracks as CSV."""
    output_buf = io.StringIO()
    writer = csv.writer(output_buf)
    writer.writerow(["track", "artist", "bpm"])
    for t in tracks:
        writer.writerow([t["name"], t["artist"], t["bpm"]])
    return output_buf.getvalue().rstrip()


def format_json(tracks: list[dict]) -> str:
    """Format tracks as JSON."""
    return json.dumps(
        [{"track": t["name"], "artist": t["artist"], "bpm": t["bpm"]} for t in tracks],
        indent=2,
    )


def main():
    parser = argparse.ArgumentParser(description="Get BPM for each track in a Spotify playlist.")
    parser.add_argument("playlist_url", help="Spotify playlist URL, URI, or ID")
    parser.add_argument(
        "--format", choices=["table", "csv", "json"], default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()

    sp = get_spotify_client()
    api_key = get_getsongbpm_api_key()

    playlist_id = extract_playlist_id(args.playlist_url)
    print(f"Fetching playlist tracks...", file=sys.stderr)
    tracks = fetch_playlist_tracks(sp, playlist_id)
    print(f"Found {len(tracks)} tracks. Looking up BPMs...", file=sys.stderr)

    for i, track in enumerate(tracks, 1):
        bpm = lookup_bpm(api_key, track["name"], track["artist_first"])
        track["bpm"] = bpm
        print(f"  [{i}/{len(tracks)}] {track['name']} - {bpm} BPM", file=sys.stderr)

    # Sort by BPM ascending (unknown at the end)
    def sort_key(t):
        try:
            return (0, int(t["bpm"]))
        except ValueError:
            return (1, 0)

    tracks.sort(key=sort_key)

    if args.format == "csv":
        print(format_csv(tracks))
    elif args.format == "json":
        print(format_json(tracks))
    else:
        print(format_table(tracks))


if __name__ == "__main__":
    main()
