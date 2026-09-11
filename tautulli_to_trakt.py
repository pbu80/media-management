#!/usr/bin/env python3
"""Export one Tautulli user's completed watch history to Trakt CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_USER = "maggi"
CSV_FIELDS = (
    "trakt_id",
    "imdb_id",
    "tmdb_id",
    "tvdb_id",
    "type",
    "title",
    "year",
    "season",
    "episode",
    "watched_at",
    "action",
)

GUID_PATTERNS = {
    "imdb_id": re.compile(r"(?:imdb|imdb\.com)(?:://|/)(tt\d+)", re.I),
    "tmdb_id": re.compile(r"(?:tmdb|themoviedb)(?:://|/)(\d+)", re.I),
    "tvdb_id": re.compile(r"(?:tvdb|thetvdb)(?:://|/)(\d+)", re.I),
    "trakt_id": re.compile(r"trakt(?:://|/)(\d+)", re.I),
}


class TautulliError(RuntimeError):
    """Raised when Tautulli cannot complete an API request."""


class TautulliClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: int = 30,
        retries: int = 3,
        verify_tls: bool = True,
    ) -> None:
        self.api_url = f"{base_url.rstrip('/')}/api/v2"
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.ssl_context = (
            ssl.create_default_context()
            if verify_tls
            else ssl._create_unverified_context()  # noqa: SLF001
        )

    def call(self, command: str, **params: Any) -> Any:
        query = urlencode(
            {"apikey": self.api_key, "cmd": command, **params},
            doseq=True,
        )
        request = Request(
            f"{self.api_url}?{query}",
            headers={"Accept": "application/json", "User-Agent": "tautulli-to-trakt/1.0"},
        )

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with urlopen(
                    request,
                    timeout=self.timeout,
                    context=self.ssl_context,
                ) as response:
                    payload = json.load(response)

                api_response = payload.get("response", {})
                if api_response.get("result") != "success":
                    message = api_response.get("message") or "unknown API error"
                    raise TautulliError(f"Tautulli {command!r} failed: {message}")
                return api_response.get("data")
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))

        raise TautulliError(
            f"Unable to call Tautulli {command!r} after {self.retries} attempts: "
            f"{last_error}"
        )

    def find_user(self, username: str) -> dict[str, Any]:
        users = self.call("get_users") or []
        match = next(
            (
                user
                for user in users
                if str(user.get("username", "")).casefold() == username.casefold()
            ),
            None,
        )
        if match is None:
            available = ", ".join(
                sorted(str(user.get("username")) for user in users if user.get("username"))
            )
            raise TautulliError(
                f"Plex user {username!r} was not found in Tautulli. "
                f"Available users: {available or 'none'}"
            )
        return match

    def history(self, user_id: Any, page_size: int) -> Iterable[dict[str, Any]]:
        start = 0
        while True:
            result = self.call(
                "get_history",
                user_id=user_id,
                grouping=0,
                include_activity=0,
                start=start,
                length=page_size,
            ) or {}
            rows = result.get("data", []) if isinstance(result, dict) else []
            if not rows:
                break

            yield from rows
            start += len(rows)
            total = _to_int(result.get("recordsFiltered") or result.get("recordsTotal"))
            if total is not None and start >= total:
                break

    def metadata(self, rating_key: Any) -> dict[str, Any]:
        if rating_key in (None, ""):
            return {}
        result = self.call("get_metadata", rating_key=rating_key)
        return result if isinstance(result, dict) else {}


def _to_int(value: Any) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def is_completed(row: dict[str, Any], minimum_progress: float) -> bool:
    watched_status = row.get("watched_status")
    if watched_status not in (None, ""):
        normalized = str(watched_status).strip().casefold()
        if normalized in {"1", "true", "yes", "watched"}:
            return True

    progress = _to_float(
        row.get("percent_complete", row.get("progress_percent", row.get("progress")))
    )
    return progress is not None and progress >= minimum_progress


def guid_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key in ("id", "guid", "url"):
            if value.get(key):
                yield str(value[key])
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from guid_strings(item)


def extract_ids(*sources: dict[str, Any]) -> dict[str, str]:
    ids = {key: "" for key in GUID_PATTERNS}

    for source in sources:
        if not isinstance(source, dict):
            continue

        for field in ids:
            value = source.get(field) or source.get(field.removesuffix("_id"))
            if value not in (None, "", 0, "0"):
                ids[field] = str(value)

        candidates: list[Any] = []
        for key, value in source.items():
            if "guid" in str(key).casefold():
                candidates.append(value)

        for candidate in candidates:
            for guid in guid_strings(candidate):
                for field, pattern in GUID_PATTERNS.items():
                    match = pattern.search(guid)
                    if match and not ids[field]:
                        ids[field] = match.group(1)

    return ids


def watched_at(row: dict[str, Any]) -> str:
    timestamp = _to_float(row.get("stopped") or row.get("started"))
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def build_csv_row(
    history: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, str]:
    media_type = str(history.get("media_type") or metadata.get("media_type") or "").lower()
    ids = extract_ids(history, metadata)

    if media_type == "movie":
        title = history.get("title") or metadata.get("title")
        year = history.get("year") or metadata.get("year")
        season = episode = ""
    else:
        title = history.get("title") or metadata.get("title")
        year = history.get("year") or metadata.get("year")
        season = (
            history.get("parent_media_index")
            or metadata.get("parent_media_index")
            or metadata.get("parent_index")
            or ""
        )
        episode = (
            history.get("media_index")
            or metadata.get("media_index")
            or metadata.get("index")
            or ""
        )

    return {
        **ids,
        "type": media_type,
        "title": str(title or ""),
        "year": str(year or ""),
        "season": str(season),
        "episode": str(episode),
        "watched_at": watched_at(history),
        "action": "history",
    }


def has_trakt_identity(row: dict[str, str]) -> bool:
    has_id = any(row[field] for field in ("trakt_id", "imdb_id", "tmdb_id", "tvdb_id"))
    return has_id or bool(row["title"] and row["year"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a Tautulli user's completed movie/episode history to Trakt CSV."
    )
    parser.add_argument(
        "--tautulli-url",
        default=os.getenv("TAUTULLI_URL"),
        help="Tautulli base URL (or set TAUTULLI_URL).",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("TAUTULLI_API_KEY"),
        help="Tautulli API key (prefer the TAUTULLI_API_KEY environment variable).",
    )
    parser.add_argument("--user", default=DEFAULT_USER, help=f"Plex user (default: {DEFAULT_USER}).")
    parser.add_argument("--output", type=Path, help="Output CSV path.")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument(
        "--minimum-progress",
        type=float,
        default=90.0,
        help="Fallback completion percentage when watched_status is unavailable (default: 90).",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate validation (use only for a trusted local server).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.tautulli_url or not args.api_key:
        print(
            "error: provide --tautulli-url and --api-key, or set TAUTULLI_URL "
            "and TAUTULLI_API_KEY",
            file=sys.stderr,
        )
        return 2
    if args.page_size < 1 or not 0 <= args.minimum_progress <= 100:
        print("error: page size must be positive and progress must be between 0 and 100", file=sys.stderr)
        return 2

    output = args.output or Path(f"tautulli_{args.user}_trakt.csv")
    client = TautulliClient(
        args.tautulli_url,
        args.api_key,
        timeout=args.timeout,
        retries=args.retries,
        verify_tls=not args.insecure,
    )

    try:
        user = client.find_user(args.user)
        user_id = user.get("user_id")
        if user_id in (None, ""):
            raise TautulliError(f"Tautulli returned no user_id for {args.user!r}")

        history_rows = list(client.history(user_id, args.page_size))
        metadata_cache: dict[str, dict[str, Any]] = {}
        exported: list[dict[str, str]] = []
        skipped_incomplete = skipped_unsupported = skipped_unmatched = 0

        for history in history_rows:
            media_type = str(history.get("media_type", "")).lower()
            if media_type not in {"movie", "episode"}:
                skipped_unsupported += 1
                continue
            if not is_completed(history, args.minimum_progress):
                skipped_incomplete += 1
                continue

            rating_key = str(history.get("rating_key") or "")
            ids = extract_ids(history)
            metadata: dict[str, Any] = {}
            if not any(ids.values()) and rating_key:
                if rating_key not in metadata_cache:
                    try:
                        metadata_cache[rating_key] = client.metadata(rating_key)
                    except TautulliError as exc:
                        print(f"warning: metadata {rating_key}: {exc}", file=sys.stderr)
                        metadata_cache[rating_key] = {}
                metadata = metadata_cache[rating_key]

            row = build_csv_row(history, metadata)
            if not row["watched_at"] or not has_trakt_identity(row):
                skipped_unmatched += 1
                continue
            exported.append(row)

        exported.sort(key=lambda item: item["watched_at"])
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(exported)

        print(f"User: {user.get('username')} (Tautulli user_id {user_id})")
        print(f"History records read: {len(history_rows)}")
        print(f"Trakt rows exported: {len(exported)}")
        print(f"Skipped incomplete: {skipped_incomplete}")
        print(f"Skipped unsupported media: {skipped_unsupported}")
        print(f"Skipped without timestamp/identity: {skipped_unmatched}")
        print(f"Output: {output.resolve()}")
        return 0
    except (TautulliError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
