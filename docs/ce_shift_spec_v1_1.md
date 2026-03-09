# CE Shift Service Spec v1.1

## Scope
- Generate one-month shift assignments for a 9-person department.
- Human operator can review and manually modify after auto-generation.
- If strict satisfaction is impossible (for example due to requests off), partial schedule with blanks is allowed.
- Missing assignments must be reported with alert details (date, shift, count).

## Calendar Rules
- Working days: Monday through Saturday.
- Closed day: Sunday only.
- Public holidays are working days (not auto-closed).

## Shift Catalog
| code | start-end | hours |
|---|---|---:|
| Aフ | 07:45-14:45 | 6.25 |
| A他 | 07:45-14:45 | 6.25 |
| B | 11:30-20:30 | 8.0 |
| C | 13:30-22:30 | 8.0 |
| Dフ | 07:45-18:45 | 9.75 |
| D他 | 07:45-18:45 | 9.75 |
| Eフ | 07:45-17:45 | 8.75 |
| E他 | 07:45-17:45 | 8.75 |
| Fフ | 07:45-15:45 | 7.25 |
| F他 | 07:45-15:45 | 7.25 |
| Gフ | 07:45-16:45 | 8.0 |
| G他 | 07:45-16:45 | 8.0 |
| 通 | 07:45-22:00 | 12.0 |

Notes:
- `通` is emergency-only and should be heavily penalized in normal optimization.
- `A他/D他/E他/F他/G他` are overflow slots used when extra staffing is possible.

## Required Daily Slots (Hard)
For each target date `d` (excluding Sundays):

1. If weekday is Mon/Wed/Fri and `d` is NOT holiday:
- required multiset = `Aフ x1, C x3, Fフ x1, Gフ x2` (total 7)

2. If weekday is Mon/Wed/Fri and `d` IS holiday:
- required multiset = `Aフ x4, B x3` (total 7)

3. If weekday is Tue/Thu/Sat (holiday or non-holiday):
- required multiset = `B x2, Dフ x1, Eフ x1, Gフ x2` (total 6)

## Overflow Placement Policy (Soft)
- Primary preferred overflow weekdays: Monday, Wednesday, Thursday, Saturday (excluding holidays).
- Candidate overflow slots:
- Mon/Wed/Fri pattern days: `A他, F他, G他`
- Tue/Thu/Sat pattern days: `D他, E他, G他`
- No fixed priority order among these slots.

## Staff Attributes
Each staff has the following fields:
- `id`: unique string
- `name`: display name
- `role`: one of `chief`, `normal`
- `employment_type`: one of `full_time`, `part_time`, `short_time`
- `has_other_skill`: boolean
- `requests_off`: list of off dates in target month

## Staff Hard Constraints
1. One staff can take at most one slot per day.
2. Requests off are absolute: staff cannot be assigned on those dates.
3. Role and employment constraints:
- Chief (`role=chief`): only `Gフ` or `G他`; cannot work Tuesday.
- Part-time (`employment_type=part_time`): exactly 2 assignments per week; only `Gフ`; cannot work Tuesday.
- Short-time (`employment_type=short_time`): only `Gフ`.
4. Weekly max 40 hours for non-part-time staff.
5. Monthly max hours `5.7 * days_in_month` for non-part-time staff.

## Monthly Rest-Day Rule
- Rest-day minimum (including Sundays) for 2026:
- Months 1,2,6,9: at least 8 days
- Months 3,4,5,7,8,10,11,12: at least 9 days
- For this release, evaluate monthly only; annual leave accounting is out of scope.

## Objective Function (Lexicographic)
Use multi-priority objective in this order:
1. Minimize missing required slots.
2. Maximize total assigned work hours within constraints.
3. Maximize overflow allocation on preferred weekdays (Mon/Wed/Thu/Sat non-holiday).
4. Maximize assigning `has_other_skill=true` staff into overflow slots (`A他/D他/E他/F他/G他`).
5. Minimize workload imbalance across staff (e.g., max-min hours or deviation from mean).
6. Penalize any usage of `通` strongly.

## Partial Schedule + Alert Contract
When strict fill is impossible, return partial result and alert payload.

Alert item schema:
- `date`: `YYYY-MM-DD`
- `shift_code`: shift code string
- `missing_count`: positive integer

Top-level solver status:
- `status`: `ok` | `partial` | `infeasible`
- `alerts`: list of alert items

Rules:
- `status=partial` when at least one required slot is unfilled.
- `status=infeasible` only if even partial model cannot be solved.

## Output Format Requirement
Final exported table must be:
- Rows: staff names
- Columns: each day of month (`1..N`)
- Cell value: assigned shift code or blank
- End-of-row summary columns:
- `勤務日数` (monthly worked days)
- `勤務時間` (monthly total hours)
- `休日数` (monthly off days)

## Input Data Contract (JSON)
Top-level fields:
- `month`: `YYYY-MM`
- `holidays`: list of holiday dates (used only for Mon/Wed/Fri holiday pattern switch)
- `staff`: staff master with attributes
- `requests_off`: map `staff_id -> [YYYY-MM-DD]`
- `settings`: optional solver knobs (time limit, workers)

See `docs/ce_input_schema.json` for machine-readable validation rules.

## Out of Scope (This Release)
- Annual paid leave carry-over and minimum-5-days yearly compliance tracking.
- Annual special leave quota tracking.
- Automatic attendance/result reconciliation.
