import logging
from datetime import UTC, datetime

from app.config import LOCAL_TIMEZONE
from app.parsing.parsers import (
    parse_clock,
    parse_date,
    parse_day,
    parse_relative,
    parse_weekday,
)

logger = logging.getLogger(__name__)


def parse_due(text: str, now: datetime) -> datetime | None:
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    if not text or not text.strip():
        return None

    text = " ".join(text.casefold().replace("ё", "е").split())
    now = now.astimezone(LOCAL_TIMEZONE)

    parsers = (
        parse_relative,
        parse_date,
        parse_weekday,
        parse_day,
        parse_clock,
    )

    try:
        for parser in parsers:
            if (result := parser(text, now)) is not None:
                return result.astimezone(UTC)

    except (ValueError, OverflowError) as exc:
        logger.debug("parse_due(%r) failed: %s", text, exc)
        return None

    return None
