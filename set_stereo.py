#!/usr/bin/env python3
"""Set default audio track to stereo for Plex managed users.

The script connects to a Plex server using ``plexapi`` and inspects MKV files
with ``mkvinfo`` to locate a 2‑channel audio track. When found, it sets that
stream as the default for selected managed users.

Environment variables ``PLEX_URL`` and ``PLEX_TOKEN`` must be defined to
specify the server URL and an administrator token.
"""

import argparse
import os
import subprocess
from typing import Optional

from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer


def get_media_path(video) -> Optional[str]:
    """Return the file path of the first part of a video item."""
    for media in video.media:
        for part in media.parts:
            return part.file
    return None


def find_stereo_track(path: str) -> Optional[int]:
    """Return the track index of a 2-channel audio stream using ``mkvinfo``."""
    try:
        output = subprocess.check_output(["mkvinfo", path], text=True)
    except (OSError, subprocess.CalledProcessError):
        return None

    track_id = None
    current_id = None
    is_audio = False
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Track number:"):
            # "Track number: 1 (track ID for mkvmerge & mkvextract: 0)"
            parts = line.split(":", 1)[1].split("(", 1)[0]
            current_id = int(parts.strip())
            is_audio = False
        elif line.startswith("Track type:"):
            is_audio = "audio" in line.lower()
        elif is_audio and "channels:" in line.lower():
            if line.split(":", 1)[1].strip().startswith("2"):
                track_id = current_id
                break
    return track_id


def set_default_audio(video, track_index: int) -> bool:
    """Mark the audio stream with ``track_index`` as default."""
    for part in video.iterParts():
        for stream in part.audioStreams():
            if stream.index == track_index:
                stream.setDefault()
                return True
    return False


def process_user(account: MyPlexAccount, username: str, library, dry_run: bool) -> None:
    user = account.user(username)
    if user is None:
        print(f"User {username} not found")
        return

    token = user.get_token(library._server.machineIdentifier)
    plex = PlexServer(account._baseurl, token)

    for video in library.all():
        path = get_media_path(video)
        if not path or not path.lower().endswith(".mkv"):
            continue
        track = find_stereo_track(path)
        if track is None:
            continue
        if dry_run:
            print(
                f"[DRY] Would set stereo track {track} for '{video.title}' in {username}"
            )
            continue
        user_video = plex.fetchItem(video.key)
        if set_default_audio(user_video, track):
            print(f"Set stereo track for '{video.title}' in {username}")
        else:
            print(f"Unable to update '{video.title}' for {username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set stereo audio as default")
    parser.add_argument("--library", required=True, help="Plex library name")
    parser.add_argument("--users", required=True, help="Comma-separated user names")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show actions without changing anything"
    )
    args = parser.parse_args()

    url = os.environ.get("PLEX_URL")
    token = os.environ.get("PLEX_TOKEN")
    if not url or not token:
        parser.error("PLEX_URL and PLEX_TOKEN environment variables must be set")

    account = MyPlexAccount(token=token)
    plex = PlexServer(url, token)
    library = plex.library.section(args.library)

    for username in [u.strip() for u in args.users.split(",") if u.strip()]:
        process_user(account, username, library, args.dry_run)


if __name__ == "__main__":
    main()
