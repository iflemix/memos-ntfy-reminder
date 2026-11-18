import math
import re
from datetime import UTC, datetime, timedelta

from dateutil.relativedelta import relativedelta

from app.parsing.patterns import (
    _DAY_PART_HOUR,
    _MONTHS,
    _NUM_WORDS,
    _RE_CLOCK,
    _RE_CLOCK_NOPREP,
    _RE_DATE_NUM,
    _RE_DATE_WORD,
    _RE_DAY_PART,
    _RE_REL,
    _RE_REL_NUM_WORD,
    _RE_REL_WORD,
    _RE_TOMORROW,
    _RE_WEEKDAY,
    _UNIT_SECONDS,
    _WEEKDAYS,
    _WORD_SECONDS,
)

_DAY_OFFSETS = {"сегодня": 0, "завтра": 1, "послезавтра": 2}
_MONTH_UNITS = {"месяц", "месяца", "месяцев", "мес"}
_YEAR_UNITS = {"год", "года", "годов", "годы", "лет", "г"}

_DEFAULT_HOUR = 9
_SECONDS_IN_DAY = 86_400
_MAX_INTERVAL_YEARS = 100
_MAX_INTERVAL_SECONDS = _MAX_INTERVAL_YEARS * 366 * _SECONDS_IN_DAY
_MAX_INTERVAL_MONTHS = _MAX_INTERVAL_YEARS * 12

_RE_TIME_PREP_BEFORE = re.compile(r"(?:в|к)\s+$")


class InvalidDateError(ValueError):
    """Найдено некорректное выражение даты или времени."""


def _at_time(date: datetime, hour: int, minute: int = 0) -> datetime:
    try:
        result = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError as exc:
        raise InvalidDateError("Invalid time") from exc

    normalized = result.astimezone(UTC).astimezone(result.tzinfo)
    if normalized.replace(tzinfo=None) != result.replace(tzinfo=None):
        return normalized

    return result


def _extract_time(match: re.Match[str], hour_group: int, minute_group: int) -> tuple[int, int]:
    return (int(match.group(hour_group) or _DEFAULT_HOUR), int(match.group(minute_group) or 0))


def _find_day_part_hour(text: str) -> int | None:
    for part, hour in _DAY_PART_HOUR.items():
        if re.search(rf"\b{re.escape(part)}\b", text):
            return hour


def parse_relative(text: str, now: datetime) -> datetime | None:
    if match := _RE_REL.search(text):
        number = float(match.group(1).replace(",", "."))
        unit = match.group(2)
    elif match := _RE_REL_NUM_WORD.search(text):
        number = float(_NUM_WORDS[match.group(1)])
        unit = match.group(2)
    elif match := _RE_REL_WORD.search(text):
        number = 1.0
        unit = match.group(1)
    else:
        return None

    if not math.isfinite(number) or number <= 0:
        raise InvalidDateError("Invalid interval")

    if unit in _MONTH_UNITS or unit in _YEAR_UNITS:
        if not number.is_integer():
            raise InvalidDateError("Expected integer interval")

        months = int(number) * (1 if unit in _MONTH_UNITS else 12)
        if months > _MAX_INTERVAL_MONTHS:
            raise InvalidDateError("Interval is too large")

        target = now + relativedelta(months=months)
        calendar_interval = True
    else:
        seconds = _UNIT_SECONDS.get(unit) or _WORD_SECONDS.get(unit)

        if not seconds:
            raise InvalidDateError("Unknown time unit")

        if number * seconds > _MAX_INTERVAL_SECONDS:
            raise InvalidDateError("Interval is too large")

        delta = timedelta(seconds=number * seconds)
        calendar_interval = seconds % _SECONDS_IN_DAY == 0
        target = now + delta if calendar_interval else now.astimezone(UTC) + delta

    if clock := _RE_CLOCK.search(text):
        if not calendar_interval:
            raise InvalidDateError("Time of day with sub-day interval")

        hour, minute = _extract_time(clock, 1, 2)
        return _at_time(target, hour, minute)

    return target


def parse_date(text: str, now: datetime) -> datetime | None:
    if match := _RE_DATE_WORD.search(text):
        month = _MONTHS.get(match.group(2))
        if month is None:
            raise InvalidDateError("Unknown month")
    elif match := _RE_DATE_NUM.search(text):
        if match.group(3) is None and _RE_TIME_PREP_BEFORE.search(text[: match.start()]):
            return None

        month = int(match.group(2))
        if not 1 <= month <= 12:
            return None
    else:
        return None

    day = int(match.group(1))
    year_raw = match.group(3)
    hour, minute = _extract_time(match, 4, 5)
    has_explicit_time = match.group(4) is not None

    years = (int(year_raw),) if year_raw else range(now.year, min(now.year + 9, 10000))
    for year in years:
        try:
            candidate = _at_time(now.replace(year=year, month=month, day=day), hour, minute)
        except InvalidDateError:
            raise
        except ValueError:
            continue

        if candidate > now:
            return candidate

        if not has_explicit_time and not year_raw and candidate.date() == now.date():
            raise InvalidDateError("Expected time")

    raise InvalidDateError("Invalid or past date")


def parse_weekday(text: str, now: datetime) -> datetime | None:
    if not (match := _RE_WEEKDAY.search(text)):
        return None

    weekday = _WEEKDAYS.get(match.group(1))
    if weekday is None:
        raise InvalidDateError("Unknown weekday")

    hour, minute = _extract_time(match, 2, 3)
    if match.group(2) is None and (part_hour := _find_day_part_hour(text)) is not None:
        hour, minute = part_hour, 0

    days = (weekday - now.weekday()) % 7
    candidate = _at_time(now + timedelta(days=days), hour, minute)
    return candidate + timedelta(weeks=1) if candidate <= now else candidate


def parse_day(text: str, now: datetime) -> datetime | None:
    if match := _RE_DAY_PART.search(text):
        day_word, day_part = match.group(1, 2)

        hour = _DAY_PART_HOUR.get(day_part)
        minute = 0

        if hour is None:
            raise InvalidDateError("Unknown day part")
    elif match := _RE_TOMORROW.search(text):
        day_word = match.group(1)
        if day_word == "сегодня" and match.group(2) is None:
            raise InvalidDateError("Expected time")

        hour, minute = _extract_time(match, 2, 3)
    else:
        return None

    days = _DAY_OFFSETS.get(day_word, 0)
    candidate = _at_time(now + timedelta(days=days), hour, minute)
    if candidate <= now:
        if day_word == "сегодня":
            raise InvalidDateError("Time is in the past")

        candidate += timedelta(days=1)

    return candidate


def parse_clock(text: str, now: datetime) -> datetime | None:
    match = _RE_CLOCK.search(text) or _RE_CLOCK_NOPREP.search(text)
    if match is None:
        return None

    hour, minute = _extract_time(match, 1, 2)
    candidate = _at_time(now, hour, minute)
    return candidate + timedelta(days=1) if candidate <= now else candidate
