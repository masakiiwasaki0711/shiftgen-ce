from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

SHIFT_A_MAIN = "Aフ"
SHIFT_A_OTHER = "A他"
SHIFT_B = "B"
SHIFT_C = "C"
SHIFT_D_MAIN = "Dフ"
SHIFT_D_OTHER = "D他"
SHIFT_E_MAIN = "Eフ"
SHIFT_E_OTHER = "E他"
SHIFT_F_MAIN = "Fフ"
SHIFT_F_OTHER = "F他"
SHIFT_G_MAIN = "Gフ"
SHIFT_G_OTHER = "G他"
SHIFT_EMERGENCY = "通"

SHIFT_CODES = (
    SHIFT_A_MAIN,
    SHIFT_A_OTHER,
    SHIFT_B,
    SHIFT_C,
    SHIFT_D_MAIN,
    SHIFT_D_OTHER,
    SHIFT_E_MAIN,
    SHIFT_E_OTHER,
    SHIFT_F_MAIN,
    SHIFT_F_OTHER,
    SHIFT_G_MAIN,
    SHIFT_G_OTHER,
    SHIFT_EMERGENCY,
)

SHIFT_HOURS = {
    SHIFT_A_MAIN: 6.25,
    SHIFT_A_OTHER: 6.25,
    SHIFT_B: 8.0,
    SHIFT_C: 8.0,
    SHIFT_D_MAIN: 9.75,
    SHIFT_D_OTHER: 9.75,
    SHIFT_E_MAIN: 8.75,
    SHIFT_E_OTHER: 8.75,
    SHIFT_F_MAIN: 7.25,
    SHIFT_F_OTHER: 7.25,
    SHIFT_G_MAIN: 8.0,
    SHIFT_G_OTHER: 8.0,
    SHIFT_EMERGENCY: 12.0,
}

ROLE_CHIEF = "chief"
ROLE_NORMAL = "normal"

EMP_FULL_TIME = "full_time"
EMP_PART_TIME = "part_time"
EMP_SHORT_TIME = "short_time"


@dataclass(frozen=True)
class Staff:
    id: str
    name: str
    role: str = ROLE_NORMAL
    employment_type: str = EMP_FULL_TIME
    has_other_skill: bool = False


@dataclass(frozen=True)
class SolverSettings:
    max_time_in_seconds: float = 15.0
    num_search_workers: int = 8
    allow_partial: bool = True


@dataclass(frozen=True)
class MonthInput:
    month: str  # "YYYY-MM"
    staff: tuple[Staff, ...]
    holidays: tuple[date, ...]
    requests_off: Mapping[str, tuple[date, ...]]  # staff_id -> dates
    settings: SolverSettings = SolverSettings()

    def staff_by_id(self) -> dict[str, Staff]:
        return {s.id: s for s in self.staff}


@dataclass(frozen=True)
class Assignment:
    day: date
    slots: Mapping[str, str]  # slot_key -> staff_id

    def all_staff_ids(self) -> Iterable[str]:
        yield from self.slots.values()


@dataclass(frozen=True)
class AlertItem:
    date: date
    shift_code: str
    missing_count: int
