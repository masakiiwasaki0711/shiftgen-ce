from __future__ import annotations

import argparse

from .excel import export_xlsx
from .io import load_month_input_json
from .solver import solve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="input JSON path")
    ap.add_argument("--out", dest="out_path", required=True, help="output xlsx path")
    args = ap.parse_args(argv)

    mi = load_month_input_json(args.in_path)
    res = solve(mi)
    export_xlsx(
        mi,
        res.assignments,
        args.out_path,
        alerts=res.alerts,
        request_violations=res.request_violations,
    )

    if res.status == "partial":
        print(f"status=partial alerts={len(res.alerts)} request_violations={len(res.request_violations)}")
    else:
        print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
