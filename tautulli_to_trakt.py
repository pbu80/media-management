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
from datetime import datetime, timedelta, timezone
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
            except HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace").strip()
                    error_payload = json.loads(detail)
                    api_response = error_payload.get("response", {})
                    detail = api_response.get("message") or detail
                except (AttributeError, json.JSONDecodeError):
                    pass
                detail = detail[:300] if detail else str(exc.reason)
                error = TautulliError(
                    f"Tautulli {command!r} returned HTTP {exc.code}: {detail}"
                )
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise error from exc
                last_error = error
                if attempt < self.retries:
                    time.sleep(2 ** (attempt - 1))
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
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

    def history(
        self,
        user_id: Any,
        page_size: int,
        *,
        after: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        start = 0
        while True:
            params: dict[str, Any] = {
                "user_id": user_id,
                "grouping": 0,
                "include_activity": 0,
                "start": start,
                "length": page_size,
            }
            if after:
                params["after"] = after
            result = self.call("get_history", **params) or {}
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
    timestamp = history_timestamp(row)
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def history_timestamp(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("stopped") or row.get("started"))


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
    if row["type"] == "episode":
        return has_id
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
    parser.add_argument(
        "weeks_ago",
        nargs="?",
        type=int,
        help="Optional shorthand: -2 exports only the last 2 weeks.",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        help="Export only the last N weeks; both --weeks 2 and --weeks -2 are accepted.",
    )
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
        "--no-metadata",
        action="store_true",
        help="Do not query metadata IDs. Fast, but episodes without IDs are skipped.",
    )
    parser.add_argument(
        "--metadata-failure-limit",
        type=int,
        default=10,
        help=(
            "Stop metadata lookups after this many consecutive failures "
            "(default: 10; use 0 for unlimited)."
        ),
    )
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
    if args.weeks is not None and args.weeks_ago is not None:
        print("error: use either the -N shorthand or --weeks, not both", file=sys.stderr)
        return 2

    requested_weeks = args.weeks if args.weeks is not None else args.weeks_ago
    weeks = abs(requested_weeks) if requested_weeks is not None else None
    if (
        args.page_size < 1
        or not 0 <= args.minimum_progress <= 100
        or args.metadata_failure_limit < 0
        or weeks == 0
    ):
        print(
            "error: page size must be positive, progress must be between 0 and 100, "
            "metadata failure limit cannot be negative, and weeks cannot be zero",
            file=sys.stderr,
        )
        return 2

    default_name = (
        f"tautulli_{args.user}_trakt_last_{weeks}_weeks.csv"
        if weeks is not None
        else f"tautulli_{args.user}_trakt.csv"
    )
    output = args.output or Path(default_name)
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

        cutoff = (
            datetime.now(timezone.utc) - timedelta(weeks=weeks)
            if weeks is not None
            else None
        )
        history_rows = list(
            client.history(
                user_id,
                args.page_size,
                after=cutoff.date().isoformat() if cutoff else None,
            )
        )
        metadata_cache: dict[str, dict[str, Any]] = {}
        exported: list[dict[str, str]] = []
        skipped_incomplete = skipped_unsupported = skipped_unmatched = 0
        skipped_outside_range = 0
        metadata_failures = 0
        consecutive_metadata_failures = 0
        metadata_disabled = args.no_metadata
        metadata_failure_examples: list[str] = []

        for position, history in enumerate(history_rows, start=1):
            timestamp = history_timestamp(history)
            if cutoff is not None and (timestamp is None or timestamp < cutoff.timestamp()):
                skipped_outside_range += 1
                continue
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
            if not any(ids.values()) and rating_key and not metadata_disabled:
                if rating_key not in metadata_cache:
                    try:
                        metadata_cache[rating_key] = client.metadata(rating_key)
                        consecutive_metadata_failures = 0
                    except TautulliError as exc:
                        metadata_failures += 1
                        consecutive_metadata_failures += 1
                        if len(metadata_failure_examples) < 3:
                            metadata_failure_examples.append(f"{rating_key}: {exc}")
                        metadata_cache[rating_key] = {}
                        if (
                            args.metadata_failure_limit
                            and consecutive_metadata_failures
                            >= args.metadata_failure_limit
                        ):
                            metadata_disabled = True
                metadata = metadata_cache[rating_key]

            row = build_csv_row(history, metadata)
            if not row["watched_at"] or not has_trakt_identity(row):
                skipped_unmatched += 1
            else:
                exported.append(row)

            if position % 100 == 0:
                print(
                    f"Processed {position}/{len(history_rows)} history records...",
                    file=sys.stderr,
                )

        exported.sort(key=lambda item: item["watched_at"])
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(exported)

        print(f"User: {user.get('username')} (Tautulli user_id {user_id})")
        if cutoff is not None:
            print(
                f"Date range: {cutoff.isoformat().replace('+00:00', 'Z')} to now "
                f"(last {weeks} weeks)"
            )
        print(f"History records read: {len(history_rows)}")
        print(f"Trakt rows exported: {len(exported)}")
        print(f"Skipped incomplete: {skipped_incomplete}")
        print(f"Skipped unsupported media: {skipped_unsupported}")
        print(f"Skipped outside requested range: {skipped_outside_range}")
        print(f"Skipped without timestamp/Trakt identity: {skipped_unmatched}")
        print(f"Metadata lookup failures: {metadata_failures}")
        if metadata_failure_examples:
            print("First metadata errors:", file=sys.stderr)
            for example in metadata_failure_examples:
                print(f"  {example}", file=sys.stderr)
        if metadata_disabled and not args.no_metadata:
            print(
                "Metadata lookups were disabled after repeated failures; movies can "
                "still match by title/year, but episodes without IDs were skipped.",
                file=sys.stderr,
            )
        print(f"Output: {output.resolve()}")
        return 0
    except (TautulliError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
