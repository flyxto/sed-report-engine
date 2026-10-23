"""Dates on reports are New Zealand dates, wherever the server runs.

The servers may be in Europe or the US; the server's own clock would print
yesterday's date on an NZ morning. Pacific/Auckland covers NZST and NZDT.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

NZ = ZoneInfo("Pacific/Auckland")


def nz_today() -> date:
    """Today's date in New Zealand."""
    return datetime.now(NZ).date()


def long_date(value: str | date | None) -> str:
    """"2026-09-01" -> "1 September 2026"; other text is returned as given."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return value
    return f"{value.day} {value:%B %Y}"


def long_date_time(moment: datetime) -> str:
    """A moment as New Zealand date and time: "28 September 2026 at 5:11 pm"."""
    m = moment.astimezone(NZ)
    return f"{long_date(m.date())} at {m.hour % 12 or 12}:{m.minute:02d} {'am' if m.hour < 12 else 'pm'}"


def nz_now() -> datetime:
    return datetime.now(NZ)


def nz_date(moment: datetime) -> date:
    """The New Zealand date of a timezone-aware moment (the portal sends UTC):
    2026-08-14T23:30Z is 15 August in New Zealand."""
    return moment.astimezone(NZ).date()
