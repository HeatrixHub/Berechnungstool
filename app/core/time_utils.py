"""Zentrale Hilfsfunktionen für konsistente UTC-Zeitstempel."""
from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc
_LEGACY_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)


def utc_now() -> datetime:
    """Liefert einen timezone-aware UTC-Zeitstempel."""
    return datetime.now(UTC)


def utc_now_iso_z(*, timespec: str = "seconds") -> str:
    """Liefert einen UTC-ISO-8601-Zeitstempel mit explizitem 'Z'-Suffix."""
    return utc_to_iso_z(utc_now(), timespec=timespec)


def parse_timestamp_to_utc(value: object) -> datetime | None:
    """Parst bekannte Zeitstempelformate robust und normalisiert nach UTC."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    parsed = _try_parse_iso(text)
    if parsed is None:
        parsed = _try_parse_legacy(text)
    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def normalize_timestamp(value: object, *, default: str | None = None) -> str | None:
    """Normalisiert einen Zeitstempel in das Format YYYY-MM-DDTHH:MM:SSZ."""
    parsed = parse_timestamp_to_utc(value)
    if parsed is None:
        return default
    return utc_to_iso_z(parsed)


def utc_to_iso_z(value: datetime, *, timespec: str = "seconds") -> str:
    """Formatiert ein datetime als UTC-ISO-8601 mit Z-Suffix."""
    utc_value = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")


def _try_parse_iso(text: str) -> datetime | None:
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _try_parse_legacy(text: str) -> datetime | None:
    for pattern in _LEGACY_PATTERNS:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None
