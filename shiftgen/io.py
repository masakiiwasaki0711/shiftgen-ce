from __future__ import annotations

import json
from datetime import date

from .domain import MonthInput, SolverSettings, Staff


def _parse_date(d: str) -> date:
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd))


def load_month_input_json(path: str) -> MonthInput:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    staff = tuple(
        Staff(
            id=s["id"],
            name=s["name"],
            role=str(s.get("role", "normal")),
            employment_type=str(s.get("employment_type", "full_time")),
            has_other_skill=bool(s.get("has_other_skill", False)),
        )
        for s in raw["staff"]
    )

    holidays = tuple(_parse_date(d) for d in raw.get("holidays", []))

    requests_off_raw = raw.get("requests_off", {})
    requests_off: dict[str, tuple[date, ...]] = {}
    for staff_id, dates in requests_off_raw.items():
        requests_off[staff_id] = tuple(_parse_date(d) for d in dates)

    settings_raw = raw.get("settings") or {}
    settings = SolverSettings(
        max_time_in_seconds=float(settings_raw.get("max_time_in_seconds", 15.0)),
        num_search_workers=int(settings_raw.get("num_search_workers", 8)),
        allow_partial=bool(settings_raw.get("allow_partial", True)),
    )

    return MonthInput(
        month=str(raw["month"]),
        staff=staff,
        holidays=holidays,
        requests_off=requests_off,
        settings=settings,
    )
