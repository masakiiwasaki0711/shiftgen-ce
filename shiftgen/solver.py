from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .calendar_utils import is_sunday, iter_dates, month_range
from .domain import (
    AlertItem,
    Assignment,
    EMP_PART_TIME,
    EMP_SHORT_TIME,
    MonthInput,
    ROLE_CHIEF,
    SHIFT_A_MAIN,
    SHIFT_A_OTHER,
    SHIFT_B,
    SHIFT_C,
    SHIFT_D_MAIN,
    SHIFT_D_OTHER,
    SHIFT_EMERGENCY,
    SHIFT_E_MAIN,
    SHIFT_E_OTHER,
    SHIFT_F_MAIN,
    SHIFT_F_OTHER,
    SHIFT_G_MAIN,
    SHIFT_G_OTHER,
    SHIFT_HOURS,
    Staff,
)


class SolveError(RuntimeError):
    pass


@dataclass(frozen=True)
class SolveResult:
    assignments: tuple[Assignment, ...]
    status: str  # ok | partial
    alerts: tuple[AlertItem, ...]
    request_violations: tuple[tuple[date, str], ...] = ()


def _month_rest_min(month: str) -> int:
    mon = int(month.split("-")[1])
    if mon in (1, 2, 6, 9):
        return 8
    return 9


def _open_days(month: str) -> list[date]:
    start, end = month_range(month)
    return [d for d in iter_dates(start, end) if not is_sunday(d)]


def _required_codes(day: date, holidays: set[date]) -> list[str]:
    wd = day.weekday()
    if wd in (0, 2, 4):
        if day in holidays:
            return [SHIFT_A_MAIN, SHIFT_A_MAIN, SHIFT_A_MAIN, SHIFT_A_MAIN, SHIFT_B, SHIFT_B, SHIFT_B]
        return [SHIFT_A_MAIN, SHIFT_C, SHIFT_C, SHIFT_C, SHIFT_F_MAIN, SHIFT_G_MAIN, SHIFT_G_MAIN]
    return [SHIFT_B, SHIFT_B, SHIFT_D_MAIN, SHIFT_E_MAIN, SHIFT_G_MAIN, SHIFT_G_MAIN]


def _overflow_codes(day: date) -> list[str]:
    wd = day.weekday()
    if wd in (0, 2, 4):
        return [SHIFT_A_OTHER, SHIFT_F_OTHER, SHIFT_G_OTHER]
    return [SHIFT_D_OTHER, SHIFT_E_OTHER, SHIFT_G_OTHER]


def _is_preferred_overflow_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() in (0, 2, 3, 5) and day not in holidays


def _shift_allowed(staff: Staff, shift_code: str, day: date) -> bool:
    if staff.role == ROLE_CHIEF:
        return day.weekday() != 1 and shift_code in (SHIFT_G_MAIN, SHIFT_G_OTHER)

    if staff.employment_type == EMP_PART_TIME:
        return day.weekday() != 1 and shift_code == SHIFT_G_MAIN

    if staff.employment_type == EMP_SHORT_TIME:
        return shift_code == SHIFT_G_MAIN

    return True


def _solve_once(mi: MonthInput, allow_partial: bool) -> SolveResult | None:
    try:
        from ortools.sat.python import cp_model
    except ImportError as e:
        msg = str(e)
        if "numpy.core.multiarray failed to import" in msg or "compiled using NumPy 1.x" in msg:
            raise SolveError(
                "NumPy 依存エラーです。Anaconda ではなくこのプロジェクトの .venv の Python で起動してください。"
            ) from e
        raise SolveError("ortools の読み込みに失敗しました。`.venv` で起動しているか確認してください。") from e

    staff = list(mi.staff)
    if not staff:
        raise SolveError("スタッフが0人です。")

    staff_ids = [s.id for s in staff]
    if len(set(staff_ids)) != len(staff_ids):
        raise SolveError("staff.id が重複しています。")

    staff_index = {sid: i for i, sid in enumerate(staff_ids)}
    for sid in mi.requests_off.keys():
        if sid not in staff_index:
            raise SolveError(f"requests_off に未知の staff id があります: {sid}")

    days = _open_days(mi.month)
    if not days:
        raise SolveError("営業日がありません。")

    holidays = set(mi.holidays)
    model = cp_model.CpModel()

    slot_meta: list[tuple[int, str, str, bool, bool, bool]] = []
    day_to_slot_keys: dict[int, list[str]] = {di: [] for di in range(len(days))}
    required_counts: dict[tuple[int, str], int] = {}

    for di, d in enumerate(days):
        req_codes = _required_codes(d, holidays)
        per_code: dict[str, int] = {}
        for code in req_codes:
            per_code[code] = per_code.get(code, 0) + 1
            key = f"{code}#{per_code[code]}"
            slot_meta.append((di, key, code, True, False, False))
            day_to_slot_keys[di].append(key)
            required_counts[(di, code)] = required_counts.get((di, code), 0) + 1

        overflow_pref = _is_preferred_overflow_day(d, holidays)
        for i, code in enumerate(_overflow_codes(d), start=1):
            key = f"{code}#{i}"
            slot_meta.append((di, key, code, False, True, overflow_pref))
            day_to_slot_keys[di].append(key)

        em_key = f"{SHIFT_EMERGENCY}#1"
        slot_meta.append((di, em_key, SHIFT_EMERGENCY, False, False, False))
        day_to_slot_keys[di].append(em_key)

    slot_index = {(di, key): (code, is_req, is_over, is_pref) for di, key, code, is_req, is_over, is_pref in slot_meta}

    active: dict[tuple[int, str], cp_model.IntVar] = {}
    x: dict[tuple[int, int, str], cp_model.IntVar] = {}

    for di, key, _code, is_req, _is_over, _is_pref in slot_meta:
        if is_req and not allow_partial:
            active[(di, key)] = model.NewConstant(1)
        else:
            active[(di, key)] = model.NewBoolVar(f"active_d{di}_{key}")

    for p in range(len(staff)):
        for di, key, _code, _is_req, _is_over, _is_pref in slot_meta:
            x[(p, di, key)] = model.NewBoolVar(f"x_p{p}_d{di}_{key}")

    for di, key, _code, _is_req, _is_over, _is_pref in slot_meta:
        model.Add(sum(x[(p, di, key)] for p in range(len(staff))) == active[(di, key)])

    for p in range(len(staff)):
        for di in range(len(days)):
            model.Add(sum(x[(p, di, key)] for key in day_to_slot_keys[di]) <= 1)

    request_violation_vars: list[tuple[cp_model.IntVar, int, int]] = []
    for sid, offs in mi.requests_off.items():
        p = staff_index[sid]
        off_set = set(offs)
        for di, d in enumerate(days):
            if d not in off_set:
                continue
            worked_on_off = model.NewBoolVar(f"req_off_violation_p{p}_d{di}")
            model.Add(
                worked_on_off
                == sum(x[(p, di, key)] for key in day_to_slot_keys[di])
            )
            request_violation_vars.append((worked_on_off, p, di))

    for p, s in enumerate(staff):
        for di, key, code, _is_req, _is_over, _is_pref in slot_meta:
            if not _shift_allowed(s, code, days[di]):
                model.Add(x[(p, di, key)] == 0)

    week_to_indices: dict[tuple[int, int], list[int]] = {}
    for di, d in enumerate(days):
        iso = d.isocalendar()
        wk = (iso.year, iso.week)
        week_to_indices.setdefault(wk, []).append(di)

    hours_scale = 20
    shift_hour_units = {code: int(round(hours * hours_scale)) for code, hours in SHIFT_HOURS.items()}

    for p, s in enumerate(staff):
        if s.employment_type == EMP_PART_TIME:
            for widx in week_to_indices.values():
                model.Add(
                    sum(x[(p, di, key)] for di in widx for key in day_to_slot_keys[di]) == 2
                )

    weekly_cap_units = int(40 * hours_scale)
    for p, s in enumerate(staff):
        if s.employment_type == EMP_PART_TIME:
            continue
        for widx in week_to_indices.values():
            model.Add(
                sum(
                    x[(p, di, key)] * shift_hour_units[slot_index[(di, key)][0]]
                    for di in widx
                    for key in day_to_slot_keys[di]
                )
                <= weekly_cap_units
            )

    start, end = month_range(mi.month)
    total_days_in_month = end.day
    month_cap_units = int(round(5.7 * total_days_in_month * hours_scale))
    rest_min = _month_rest_min(mi.month)
    max_work_days = total_days_in_month - rest_min

    worked_days: list[cp_model.IntVar] = []
    total_hours_by_staff: list[cp_model.IntVar] = []
    for p, s in enumerate(staff):
        worked = model.NewIntVar(0, len(days), f"worked_days_p{p}")
        model.Add(worked == sum(x[(p, di, key)] for di in range(len(days)) for key in day_to_slot_keys[di]))
        worked_days.append(worked)
        model.Add(worked <= max_work_days)

        hour_total = model.NewIntVar(0, len(days) * int(12 * hours_scale), f"hours_p{p}")
        model.Add(
            hour_total
            == sum(
                x[(p, di, key)] * shift_hour_units[slot_index[(di, key)][0]]
                for di in range(len(days))
                for key in day_to_slot_keys[di]
            )
        )
        total_hours_by_staff.append(hour_total)

        if s.employment_type != EMP_PART_TIME:
            model.Add(hour_total <= month_cap_units)

    total_hours_all = model.NewIntVar(0, len(days) * len(staff) * int(12 * hours_scale), "total_hours_all")
    model.Add(total_hours_all == sum(total_hours_by_staff))

    missing_required_vars: list[cp_model.IntVar] = []
    preferred_overflow_vars: list[cp_model.IntVar] = []
    other_skill_overflow_vars: list[cp_model.IntVar] = []
    emergency_vars: list[cp_model.IntVar] = []

    for di, key, _code, is_req, is_over, is_pref in slot_meta:
        a = active[(di, key)]
        if is_req:
            miss = model.NewBoolVar(f"miss_d{di}_{key}")
            model.Add(miss == 1 - a)
            missing_required_vars.append(miss)

        if is_over and is_pref:
            preferred_overflow_vars.append(a)

        if slot_index[(di, key)][0] == SHIFT_EMERGENCY:
            emergency_vars.append(a)

        if is_over:
            for p, s in enumerate(staff):
                if s.has_other_skill:
                    other_skill_overflow_vars.append(x[(p, di, key)])

    max_hours = model.NewIntVar(0, len(days) * int(12 * hours_scale), "max_hours")
    min_hours = model.NewIntVar(0, len(days) * int(12 * hours_scale), "min_hours")
    model.AddMaxEquality(max_hours, total_hours_by_staff)
    model.AddMinEquality(min_hours, total_hours_by_staff)
    imbalance = model.NewIntVar(0, len(days) * int(12 * hours_scale), "imbalance")
    model.Add(imbalance == max_hours - min_hours)

    objective = (
        sum(missing_required_vars) * 10_000_000
        + sum(emergency_vars) * 1_000_000
        + sum(v for v, _p, _di in request_violation_vars) * 10_000
        + imbalance * 10
        - total_hours_all * 1_000
        - sum(preferred_overflow_vars) * 100
        - sum(other_skill_overflow_vars) * 50
    )
    model.Minimize(objective)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = mi.settings.max_time_in_seconds
    solver.parameters.num_search_workers = mi.settings.num_search_workers

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignments: list[Assignment] = []
    alerts_by_day_and_code: dict[tuple[date, str], int] = {}

    for di, d in enumerate(days):
        slots_out: dict[str, str] = {}
        assigned_count_by_code: dict[str, int] = {}

        for key in day_to_slot_keys[di]:
            if solver.Value(active[(di, key)]) == 0:
                continue
            chosen = None
            for p in range(len(staff)):
                if solver.Value(x[(p, di, key)]) == 1:
                    chosen = staff[p].id
                    break
            if chosen is None:
                continue
            slots_out[key] = chosen
            code = slot_index[(di, key)][0]
            assigned_count_by_code[code] = assigned_count_by_code.get(code, 0) + 1

        assignments.append(Assignment(day=d, slots=slots_out))

        for (ddi, code), req_n in required_counts.items():
            if ddi != di:
                continue
            got = assigned_count_by_code.get(code, 0)
            if got < req_n:
                alerts_by_day_and_code[(d, code)] = req_n - got

    alerts = tuple(
        AlertItem(date=d, shift_code=code, missing_count=n)
        for (d, code), n in sorted(alerts_by_day_and_code.items(), key=lambda x: (x[0][0], x[0][1]))
    )
    request_violations = tuple(
        (days[di], staff[p].id)
        for v, p, di in request_violation_vars
        if solver.Value(v) == 1
    )
    status_text = "partial" if (alerts or request_violations) else "ok"
    return SolveResult(
        assignments=tuple(assignments),
        status=status_text,
        alerts=alerts,
        request_violations=request_violations,
    )


def solve(mi: MonthInput) -> SolveResult:
    try:
        strict = _solve_once(mi, allow_partial=False)
        if strict is not None:
            return strict

        if not mi.settings.allow_partial:
            raise SolveError("厳格制約で解が見つかりませんでした。")

        partial = _solve_once(mi, allow_partial=True)
        if partial is None:
            raise SolveError("部分解モードでも解が見つかりませんでした。")
        return partial
    except ModuleNotFoundError as e:
        raise SolveError("ortools が見つかりません。`pip install -r requirements.txt` を実行してください。") from e
