#!/usr/bin/env python3
"""CLI tool to fetch BPM (tempo) for each track in a Spotify playlist."""

import argparse
import csv
import io
import json
import os
import sys

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()


def get_spotify_client():
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set.", file=sys.stderr)
        sys.exit(1)
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret
    ))


def extract_playlist_id(url: str) -> str:
    """Extract playlist ID from a Spotify URL or URI."""
    if "open.spotify.com/playlist/" in url:
        path = url.split("open.spotify.com/playlist/")[1]
        return path.split("?")[0].split("/")[0]
    if url.startswith("spotify:playlist:"):
        return url.split("spotify:playlist:")[1]
    return url.strip()


def fetch_playlist_tracks(sp, playlist_id: str) -> list[dict]:
    """Fetch all tracks from a Spotify playlist, handling pagination."""
    tracks = []
    results = sp.playlist_tracks(playlist_id)
    while True:
        for item in results["items"]:
            track = item.get("track")
            if not track or not track.get("id"):
                continue
            artists = ", ".join(a["name"] for a in track["artists"])
            tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artist": artists,
            })
        if results["next"]:
            results = sp.next(results)
        else:
            break
    return tracks


def fetch_bpms(sp, tracks: list[dict]) -> None:
    """Fetch BPMs for all tracks using Spotify's audio features endpoint.

    Processes in batches of 100 (Spotify's limit). Mutates tracks in place,
    adding a 'bpm' key to each.
    """
    track_ids = [t["id"] for t in tracks]
    tempos = {}

    # audio_features accepts up to 100 IDs at a time
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i + 100]
        results = sp.audio_features(batch)
        for features in results:
            if features and features.get("tempo"):
                tempos[features["id"]] = round(features["tempo"])

    for track in tracks:
        track["bpm"] = str(tempos.get(track["id"], "unknown"))


def format_table(tracks: list[dict]) -> str:
    """Format tracks as an aligned table."""
    if not tracks:
        return "No tracks found."

    name_width = max(len(t["name"]) for t in tracks)
    artist_width = max(len(t["artist"]) for t in tracks)
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

    playlist_id = extract_playlist_id(args.playlist_url)
    print("Fetching playlist tracks...", file=sys.stderr)
    tracks = fetch_playlist_tracks(sp, playlist_id)
    print(f"Found {len(tracks)} tracks. Fetching BPMs...", file=sys.stderr)

    fetch_bpms(sp, tracks)

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
