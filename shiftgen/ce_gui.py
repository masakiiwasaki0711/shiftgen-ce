from __future__ import annotations

import json
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import date
from tkinter import filedialog, messagebox, ttk

from .calendar_utils import month_range
from .domain import EMP_FULL_TIME, EMP_PART_TIME, EMP_SHORT_TIME, ROLE_CHIEF, ROLE_NORMAL, MonthInput, Staff
from .excel import compute_summary, export_xlsx
from .solver import SolveError, solve

COL_SUN_BG = "#F3E8FF"
COL_SUN_FG = "#6B21A8"
COL_HOLIDAY_BG = "#F59E0B"
COL_HOLIDAY_FG = "#111827"
COL_REQ_BG = "#EF4444"
COL_REQ_FG = "#FFFFFF"
COL_SAT_BG = "#CFFAFE"
COL_SAT_FG = "#0F172A"
COL_WEEKDAY_BG = "#FFFFFF"
COL_WEEKDAY_FG = "#111827"

WEEKDAY_LABELS_JP = ["月", "火", "水", "木", "金", "土", "日"]
ROLE_CODE_TO_LABEL = {
    ROLE_NORMAL: "一般",
    ROLE_CHIEF: "技師長",
}
ROLE_LABEL_TO_CODE = {v: k for k, v in ROLE_CODE_TO_LABEL.items()}
EMP_CODE_TO_LABEL = {
    EMP_FULL_TIME: "常勤",
    EMP_PART_TIME: "パート",
    EMP_SHORT_TIME: "時短",
}
EMP_LABEL_TO_CODE = {v: k for k, v in EMP_CODE_TO_LABEL.items()}


@dataclass
class UiState:
    month: str = "2026-04"
    holidays: set[date] = None  # type: ignore[assignment]
    staff: list[Staff] = None  # type: ignore[assignment]
    requests_off: dict[str, set[date]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.holidays is None:
            self.holidays = set()
        if self.staff is None:
            self.staff = []
        if self.requests_off is None:
            self.requests_off = {}


def _parse_date(raw: str) -> date:
    y, m, d = raw.split("-")
    return date(int(y), int(m), int(d))


def _parse_date_list(raw: str) -> set[date]:
    out: set[date] = set()
    for token in raw.split(","):
        s = token.strip()
        if not s:
            continue
        out.add(_parse_date(s))
    return out


def _date_list_str(ds: set[date]) -> str:
    return ", ".join(sorted(d.isoformat() for d in ds))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CEシフト生成")
        self.geometry("1360x780")

        self.state = UiState()
        self._assignments = None
        self._alerts = ()
        self._request_violations = ()
        self._calendar_buttons: dict[date, tk.Label] = {}
        self._staff_display_to_id: dict[str, str] = {}
        self._staff_id_to_display: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="対象月 (YYYY-MM)").pack(side="left")
        self.month_var = tk.StringVar(value=self.state.month)
        ttk.Entry(top, textvariable=self.month_var, width=10).pack(side="left", padx=6)
        ttk.Button(top, text="カレンダー更新", command=self._refresh_calendar).pack(side="left", padx=6)

        ttk.Button(top, text="JSON読込", command=self._load_json).pack(side="left", padx=6)
        ttk.Button(top, text="JSON保存", command=self._save_json).pack(side="left", padx=6)
        self.gen_btn = ttk.Button(top, text="生成", command=self._generate)
        self.gen_btn.pack(side="left", padx=6)
        ttk.Button(top, text="Excel出力", command=self._export).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(top, textvariable=self.status_var).pack(side="left", padx=10)

        mid = ttk.PanedWindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(mid)
        right = ttk.Frame(mid)
        mid.add(left, weight=1)
        mid.add(right, weight=3)

        self.left_tabs = ttk.Notebook(left)
        self.left_tabs.pack(fill="both", expand=True)

        input_tab = ttk.Frame(self.left_tabs)
        staff_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(input_tab, text="入力")
        self.left_tabs.add(staff_tab, text="スタッフ設定")

        self._build_calendar_rules_panel(input_tab)
        self._build_calendar_panel(input_tab)
        self._build_requests_panel(input_tab)
        self._build_staff_panel(staff_tab)

        self._build_preview_panel(right)
        self._build_alert_panel(right)

    def _build_staff_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="スタッフ")
        box.pack(fill="both", expand=True, pady=6)

        ttk.Label(
            box,
            text="通常運用は JSON読込 を推奨。ここはスタッフマスタ編集が必要なときだけ使ってください。",
            wraplength=420,
        ).pack(fill="x", padx=6, pady=(4, 0))

        self.staff_tree = ttk.Treeview(
            box,
            columns=("id", "name", "role", "employment", "other_skill"),
            show="headings",
            height=8,
        )
        for c, t, w in [
            ("id", "ID", 80),
            ("name", "名前", 120),
            ("role", "役割", 90),
            ("employment", "雇用", 110),
            ("other_skill", "他スキル", 90),
        ]:
            self.staff_tree.heading(c, text=t)
            self.staff_tree.column(c, width=w, anchor="center")
        self.staff_tree.pack(fill="x", padx=6, pady=6)
        self.staff_tree.bind("<<TreeviewSelect>>", lambda _e: self._on_staff_select())

        form = ttk.Frame(box)
        form.pack(fill="x", padx=6, pady=(0, 6))

        self.staff_id_var = tk.StringVar()
        self.staff_name_var = tk.StringVar()
        self.role_var = tk.StringVar(value=ROLE_CODE_TO_LABEL[ROLE_NORMAL])
        self.emp_var = tk.StringVar(value=EMP_CODE_TO_LABEL[EMP_FULL_TIME])
        self.other_skill_var = tk.BooleanVar(value=False)

        ttk.Label(form, text="ID").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.staff_id_var, width=8).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(form, text="名前").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.staff_name_var, width=12).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(form, text="役割").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            form, textvariable=self.role_var, values=tuple(ROLE_LABEL_TO_CODE.keys()), width=10, state="readonly"
        ).grid(
            row=1, column=1, sticky="w", padx=4
        )
        ttk.Label(form, text="雇用").grid(row=1, column=2, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.emp_var,
            values=tuple(EMP_LABEL_TO_CODE.keys()),
            width=10,
            state="readonly",
        ).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Checkbutton(form, text="他スキルあり", variable=self.other_skill_var).grid(row=2, column=0, columnspan=2, sticky="w")

        btns = ttk.Frame(box)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(btns, text="追加/更新", command=self._upsert_staff).pack(side="left")
        ttk.Button(btns, text="削除", command=self._delete_staff).pack(side="left", padx=6)

    def _build_calendar_rules_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="祝日 (YYYY-MM-DD をカンマ区切り)")
        box.pack(fill="x", pady=6)

        self.holidays_var = tk.StringVar()
        ttk.Entry(box, textvariable=self.holidays_var).pack(fill="x", padx=6, pady=6)

    def _build_calendar_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="カレンダー入力")
        box.pack(fill="x", pady=6)

        row = ttk.Frame(box)
        row.pack(fill="x", padx=6, pady=4)
        self.calendar_mode_var = tk.StringVar(value="requests_off")
        ttk.Radiobutton(
            row, text="希望休", variable=self.calendar_mode_var, value="requests_off", command=self._rebuild_calendar
        ).pack(side="left")
        ttk.Radiobutton(row, text="祝日", variable=self.calendar_mode_var, value="holidays", command=self._rebuild_calendar).pack(
            side="left", padx=8
        )

        ttk.Label(row, text="対象スタッフ").pack(side="left", padx=(8, 2))
        self.calendar_staff_var = tk.StringVar(value="")
        self.calendar_staff_combo = ttk.Combobox(row, textvariable=self.calendar_staff_var, state="readonly", width=14)
        self.calendar_staff_combo.pack(side="left")
        self.calendar_staff_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_calendar())

        ttk.Label(
            box,
            text="日付をクリックで切替。日曜は編集不可。希望休モードではスタッフ選択が必要です。",
            wraplength=420,
        ).pack(fill="x", padx=6, pady=(0, 4))

        self.calendar_frame = ttk.Frame(box)
        self.calendar_frame.pack(fill="x", padx=6, pady=6)
        self._rebuild_calendar()

    def _build_requests_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="希望休 (1行: staff_id: date1,date2)")
        box.pack(fill="both", expand=True, pady=6)

        self.requests_text = tk.Text(box, height=12)
        self.requests_text.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_preview_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="生成結果プレビュー")
        box.pack(fill="both", expand=True, pady=6)

        self.preview = ttk.Treeview(box, show="headings")
        ysb = ttk.Scrollbar(box, orient="vertical", command=self.preview.yview)
        xsb = ttk.Scrollbar(box, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscroll=ysb.set, xscroll=xsb.set)
        self.preview.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        ysb.grid(row=0, column=1, sticky="ns", pady=6)
        xsb.grid(row=1, column=0, sticky="ew", padx=6)
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)

    def _build_alert_panel(self, parent: ttk.Frame) -> None:
        box = ttk.Labelframe(parent, text="不足アラート")
        box.pack(fill="x", pady=6)

        self.alert_text = tk.Text(box, height=6, state="disabled")
        self.alert_text.pack(fill="x", padx=6, pady=6)

    def _refresh_staff_tree(self) -> None:
        self.staff_tree.delete(*self.staff_tree.get_children())
        self._staff_display_to_id = {}
        self._staff_id_to_display = {}
        for s in self.state.staff:
            display = s.name
            if display in self._staff_display_to_id:
                display = f"{s.name} ({s.id})"
            self._staff_display_to_id[display] = s.id
            self._staff_id_to_display[s.id] = display
            self.staff_tree.insert(
                "",
                "end",
                values=(
                    s.id,
                    s.name,
                    ROLE_CODE_TO_LABEL.get(s.role, s.role),
                    EMP_CODE_TO_LABEL.get(s.employment_type, s.employment_type),
                    str(s.has_other_skill),
                ),
            )
        if not hasattr(self, "calendar_staff_combo"):
            return
        displays = [self._staff_id_to_display[s.id] for s in self.state.staff if s.id in self._staff_id_to_display]
        self.calendar_staff_combo.configure(values=displays)
        if self.calendar_staff_var.get() not in displays:
            self.calendar_staff_var.set(displays[0] if displays else "")
        self._rebuild_calendar()

    def _on_staff_select(self) -> None:
        sel = self.staff_tree.selection()
        if not sel:
            return
        vals = self.staff_tree.item(sel[0], "values")
        if not vals:
            return
        sid, name, role, emp, other = vals
        self.staff_id_var.set(str(sid))
        self.staff_name_var.set(str(name))
        self.role_var.set(str(role))
        self.emp_var.set(str(emp))
        self.other_skill_var.set(str(other).lower() == "true")
        self.calendar_staff_var.set(self._staff_id_to_display.get(str(sid), str(name)))
        self._rebuild_calendar()

    def _upsert_staff(self) -> None:
        sid = self.staff_id_var.get().strip()
        name = self.staff_name_var.get().strip()
        if not sid or not name:
            messagebox.showerror("入力エラー", "ID と 名前 は必須です。")
            return

        new_staff = Staff(
            id=sid,
            name=name,
            role=ROLE_LABEL_TO_CODE.get(self.role_var.get().strip(), ROLE_NORMAL),
            employment_type=EMP_LABEL_TO_CODE.get(self.emp_var.get().strip(), EMP_FULL_TIME),
            has_other_skill=bool(self.other_skill_var.get()),
        )

        idx = next((i for i, s in enumerate(self.state.staff) if s.id == sid), None)
        if idx is None:
            self.state.staff.append(new_staff)
        else:
            self.state.staff[idx] = new_staff
        self._refresh_staff_tree()

    def _delete_staff(self) -> None:
        sel = self.staff_tree.selection()
        if not sel:
            return
        sid = str(self.staff_tree.item(sel[0], "values")[0])
        self.state.staff = [s for s in self.state.staff if s.id != sid]
        self.state.requests_off.pop(sid, None)
        self._refresh_staff_tree()
        self._render_requests_text()

    def _refresh_calendar(self) -> None:
        month = self.month_var.get().strip()
        if len(month) != 7 or month[4] != "-":
            messagebox.showerror("入力エラー", "対象月は YYYY-MM 形式で入力してください。")
            return
        self.state.month = month
        self._rebuild_calendar()

    def _selected_calendar_staff_id(self) -> str | None:
        display = self.calendar_staff_var.get().strip()
        if not display:
            return None
        return self._staff_display_to_id.get(display)

    def _day_bg(self, d: date) -> tuple[str, str]:
        if d.weekday() == 6:
            return (COL_SUN_BG, COL_SUN_FG)
        if d in self.state.holidays:
            return (COL_HOLIDAY_BG, COL_HOLIDAY_FG)
        sid = self._selected_calendar_staff_id()
        if sid and d in self.state.requests_off.get(sid, set()):
            return (COL_REQ_BG, COL_REQ_FG)
        if d.weekday() == 5:
            return (COL_SAT_BG, COL_SAT_FG)
        return (COL_WEEKDAY_BG, COL_WEEKDAY_FG)

    def _rebuild_calendar(self) -> None:
        if not hasattr(self, "calendar_frame"):
            return
        for w in self.calendar_frame.winfo_children():
            w.destroy()
        self._calendar_buttons.clear()

        month = self.month_var.get().strip()
        if len(month) != 7 or month[4] != "-":
            return

        start, end = month_range(month)
        for i, w in enumerate(["日", "月", "火", "水", "木", "金", "土"]):
            ttk.Label(self.calendar_frame, text=w).grid(row=0, column=i, padx=1, pady=1)

        r = 1
        c = (start.weekday() + 1) % 7
        for day in range(1, end.day + 1):
            d = date(start.year, start.month, day)
            bg, fg = self._day_bg(d)
            cell = tk.Label(
                self.calendar_frame,
                text=str(day),
                width=4,
                height=1,
                bg=bg,
                fg=fg,
                relief="solid",
                bd=1,
                font=("Helvetica", 10, "bold"),
            )
            if d.weekday() != 6:
                cell.bind("<Button-1>", lambda _e, dd=d: self._on_calendar_day_click(dd))
                cell.configure(cursor="hand2")
            cell.grid(row=r, column=c, padx=1, pady=1, sticky="nsew")
            self._calendar_buttons[d] = cell
            c += 1
            if c >= 7:
                c = 0
                r += 1

    def _on_calendar_day_click(self, d: date) -> None:
        if d.weekday() == 6:
            return
        mode = self.calendar_mode_var.get()
        if mode == "holidays":
            if d in self.state.holidays:
                self.state.holidays.remove(d)
            else:
                self.state.holidays.add(d)
            self.holidays_var.set(_date_list_str(self.state.holidays))
        else:
            sid = self._selected_calendar_staff_id()
            if not sid:
                messagebox.showerror("入力エラー", "希望休モードではスタッフを選択してください。")
                return
            sset = self.state.requests_off.setdefault(sid, set())
            if d in sset:
                sset.remove(d)
            else:
                sset.add(d)
            self._render_requests_text()
        self._rebuild_calendar()

    def _parse_requests_text(self) -> dict[str, set[date]]:
        out: dict[str, set[date]] = {}
        for line in self.requests_text.get("1.0", "end").splitlines():
            raw = line.strip()
            if not raw:
                continue
            if ":" not in raw:
                raise ValueError(f"Invalid line: {raw}")
            sid, dates = raw.split(":", 1)
            sid = sid.strip()
            if not sid:
                raise ValueError(f"Invalid staff id line: {raw}")
            out[sid] = _parse_date_list(dates)
        return out

    def _render_requests_text(self) -> None:
        lines = []
        for sid in sorted(self.state.requests_off.keys()):
            lines.append(f"{sid}: {_date_list_str(self.state.requests_off[sid])}")
        self.requests_text.delete("1.0", "end")
        self.requests_text.insert("end", "\n".join(lines))

    def _build_month_input(self) -> MonthInput:
        month = self.month_var.get().strip()
        if len(month) != 7 or month[4] != "-":
            raise ValueError("対象月は YYYY-MM 形式で入力してください。")
        if not self.state.staff:
            raise ValueError("スタッフを1人以上入力してください。")

        try:
            holidays = _parse_date_list(self.holidays_var.get().strip()) if self.holidays_var.get().strip() else set()
        except Exception as e:
            raise ValueError(f"祝日入力が不正です: {e}") from e

        requests_off = self._parse_requests_text()

        valid_ids = {s.id for s in self.state.staff}
        unknown = [sid for sid in requests_off.keys() if sid not in valid_ids]
        if unknown:
            raise ValueError(f"希望休に未知の staff_id があります: {', '.join(unknown)}")

        self.state.month = month
        self.state.holidays = holidays
        self.state.requests_off = requests_off
        self.holidays_var.set(_date_list_str(self.state.holidays))
        self._render_requests_text()
        self._rebuild_calendar()

        return MonthInput(
            month=month,
            staff=tuple(self.state.staff),
            holidays=tuple(sorted(holidays)),
            requests_off={sid: tuple(sorted(ds)) for sid, ds in requests_off.items()},
        )

    def _load_from_raw(self, raw: dict) -> None:
        self.month_var.set(str(raw.get("month", self.month_var.get())).strip())
        self.state.month = self.month_var.get().strip()

        self.state.staff = [
            Staff(
                id=s["id"],
                name=s["name"],
                role=str(s.get("role", ROLE_NORMAL)),
                employment_type=str(s.get("employment_type", EMP_FULL_TIME)),
                has_other_skill=bool(s.get("has_other_skill", False)),
            )
            for s in raw.get("staff", [])
        ]
        self._refresh_staff_tree()

        holidays = set()
        for d in raw.get("holidays", []):
            holidays.add(_parse_date(str(d)))
        self.state.holidays = holidays
        self.holidays_var.set(_date_list_str(holidays))

        reqs: dict[str, set[date]] = {}
        for sid, ds in (raw.get("requests_off", {}) or {}).items():
            reqs[str(sid)] = {_parse_date(str(d)) for d in ds}
        self.state.requests_off = reqs
        self._render_requests_text()
        self._rebuild_calendar()

    def _load_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._load_from_raw(raw)
            self.status_var.set(f"JSON読込: {path}")
        except Exception as e:
            messagebox.showerror("読込エラー", str(e))

    def _save_json(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return

        try:
            mi = self._build_month_input()
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))
            return

        raw = {
            "month": mi.month,
            "holidays": sorted(d.isoformat() for d in mi.holidays),
            "staff": [
                {
                    "id": s.id,
                    "name": s.name,
                    "role": s.role,
                    "employment_type": s.employment_type,
                    "has_other_skill": s.has_other_skill,
                }
                for s in mi.staff
            ],
            "requests_off": {sid: sorted(d.isoformat() for d in ds) for sid, ds in mi.requests_off.items()},
            "settings": {
                "max_time_in_seconds": 15,
                "num_search_workers": 8,
                "allow_partial": True,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"JSON保存: {path}")

    def _generate(self) -> None:
        try:
            mi = self._build_month_input()
        except Exception as e:
            messagebox.showerror("生成エラー", str(e))
            return

        self.gen_btn.configure(state="disabled")
        self.status_var.set("生成中...")

        def run() -> None:
            try:
                result = solve(mi)
                self.after(0, lambda: self._on_generated(mi, result, None))
            except Exception as e:
                self.after(0, lambda err=e: self._on_generated(mi, None, err))

        threading.Thread(target=run, daemon=True).start()

    def _on_generated(self, mi: MonthInput, result, error: Exception | None) -> None:
        self.gen_btn.configure(state="normal")
        if error is not None:
            messagebox.showerror("生成エラー", str(error))
            self.status_var.set("生成失敗: 制約矛盾または入力条件過多の可能性があります。")
            return

        self._assignments = result.assignments
        self._alerts = result.alerts
        self._request_violations = result.request_violations
        self._render_preview(mi, result.assignments)
        self._render_alerts(result.alerts, result.request_violations)
        self.status_var.set(
            f"生成完了: status={result.status}, 不足={len(result.alerts)}, 希望休違反={len(result.request_violations)}"
        )

    def _render_preview(self, mi: MonthInput, assignments) -> None:
        self.preview.delete(*self.preview.get_children())

        start, end = month_range(mi.month)
        total_days = end.day
        day_cols = [str(d) for d in range(1, total_days + 1)]
        cols = ("name", *day_cols, "work_days", "work_hours", "rest_days")
        self.preview.configure(columns=cols)

        self.preview.heading("name", text="名前")
        self.preview.column("name", width=130, anchor="center")
        for d in day_cols:
            wd = date(start.year, start.month, int(d)).weekday()
            label = f"{d}({WEEKDAY_LABELS_JP[wd]})"
            self.preview.heading(d, text=label)
            self.preview.column(d, width=72, anchor="center")

        self.preview.heading("work_days", text="勤務日数")
        self.preview.heading("work_hours", text="勤務時間")
        self.preview.heading("rest_days", text="休日数")
        self.preview.column("work_days", width=90, anchor="center")
        self.preview.column("work_hours", width=90, anchor="center")
        self.preview.column("rest_days", width=90, anchor="center")

        by_day: dict[tuple[str, date], str] = {}
        for a in assignments:
            for slot_key, sid in a.slots.items():
                by_day[(sid, a.day)] = slot_key.split("#", 1)[0]

        summary = compute_summary(mi, assignments)
        for sid, name, work_days, work_hours, rest_days in summary:
            row = [name]
            for d in range(1, total_days + 1):
                cur = date(start.year, start.month, d)
                row.append(by_day.get((sid, cur), ""))
            row.extend([work_days, f"{work_hours:.2f}", rest_days])
            self.preview.insert("", "end", values=tuple(row))

    def _render_alerts(self, alerts, request_violations) -> None:
        lines = []
        for a in alerts:
            lines.append(f"{a.date.isoformat()} | {a.shift_code} | missing={a.missing_count}")
        for d, sid in request_violations:
            lines.append(f"{d.isoformat()} | 希望休違反 | staff_id={sid}")
        if not lines:
            lines = ["不足はありません。"]

        self.alert_text.configure(state="normal")
        self.alert_text.delete("1.0", "end")
        self.alert_text.insert("end", "\n".join(lines))
        self.alert_text.configure(state="disabled")

    def _export(self) -> None:
        if not self._assignments:
            messagebox.showerror("出力エラー", "先にシフト生成を実行してください。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        try:
            mi = self._build_month_input()
            export_xlsx(
                mi,
                self._assignments,
                path,
                alerts=self._alerts,
                request_violations=self._request_violations,
            )
            self.status_var.set(f"Excel出力: {path}")
        except Exception as e:
            messagebox.showerror("出力エラー", str(e))


def run_app() -> None:
    app = App()
    app.mainloop()
