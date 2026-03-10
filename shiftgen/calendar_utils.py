from __future__ import annotations

import calendar
from datetime import date, timedelta

import jpholiday


def month_range(month: str) -> tuple[date, date]:
    y, m = month.split("-")
    year = int(y)
    mon = int(m)
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


def iter_dates(start: date, end_inclusive: date):
    cur = start
    while cur <= end_inclusive:
        yield cur
        cur += timedelta(days=1)


def is_sunday(d: date) -> bool:
    return d.weekday() == 6  # Mon=0 ... Sun=6


def is_saturday(d: date) -> bool:
    return d.weekday() == 5


def month_holidays_jp(month: str) -> set[date]:
    start, end = month_range(month)
    return {d for d in iter_dates(start, end) if jpholiday.is_holiday(d)}
