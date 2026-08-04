from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def now_in_tz(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name))


def today_in_tz(timezone_name: str) -> date:
    return now_in_tz(timezone_name).date()


def add_days(base: datetime, days: int) -> datetime:
    return base + timedelta(days=days)


def format_datetime_human(value: datetime, timezone_name: str) -> str:
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%d.%m.%Y %H:%M")


def format_date_human(value: date | datetime) -> str:
    return value.strftime("%d.%m.%Y")
