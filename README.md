# ce-shift (CE部署向けシフト生成)

CE部署向けの月次シフトを自動生成し、Excel (`.xlsx`) に出力するプロジェクトです。
現在は **CE仕様のGUI + CLI** が利用できます。

## 対応範囲

- 対象: 1ヶ月 (`YYYY-MM`)
- 稼働日: 月〜土
- 休日: 日曜固定
- 祝日: 休業ではない（勤務日）
- 曜日/祝日条件に応じた必須シフトの自動割当
- 個別制約（技師長/パート/時短/他スキル）の反映
- 週40時間上限・月上限（非パート）
- 月休日数下限（2026ルール）
- 生成不能箇所の可視化:
  - 必須枠不足（不足アラート）
  - 希望休違反（努力目標として扱い、違反箇所を表示）
- CE形式のExcel出力（縦: 個人名、横: 日付、行末: 集計）

## セットアップ

### macOS

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 使い方（GUI）

推奨:

```bash
cd /Users/iwasakimasaki/ce-shift
./run.command
```

または:

```bash
.venv/bin/python app.py
```

ポイント:
- 左側は `入力` / `スタッフ設定` のタブ構成。
- 通常運用は `JSON読込` + `入力` タブで完結。
- `希望休` モードでは対象スタッフを選び、カレンダーをクリックして入力。
- 生成後、右側にプレビューと不足アラートを表示。

## 使い方（CLI）

```bash
.venv/bin/python -m shiftgen.cli --in sample_config_ce.json --out out.xlsx
```

Windows:

```powershell
.venv\Scripts\python -m shiftgen.cli --in sample_config_ce.json --out out.xlsx
```

実行結果:
- `status=ok`: 必須枠を充足
- `status=partial`: 一部不足あり（不足または希望休違反あり）

## 入力仕様

- スキーマ: `docs/ce_input_schema.json`
- サンプル: `sample_config_ce.json`
- 仕様詳細: `docs/ce_shift_spec_v1_1.md`

主な入力項目:
- `month`: `YYYY-MM`
- `holidays`: 祝日配列（Mon/Wed/Friの祝日パターン分岐に使用）
- `staff`: `id/name/role/employment_type/has_other_skill`
- `requests_off`: `staff_id -> [YYYY-MM-DD]`
- `settings`: `max_time_in_seconds/num_search_workers/allow_partial`

## 出力仕様

### 1枚目: 月次シフト表

- 行: 個人名
- 列: 日付（曜日付き）
- セル: シフトコード（例: `Aフ`, `C`, `Gフ`）または空欄
- 行末集計:
  - `勤務日数`
  - `勤務時間`
  - `休日数`

### 2枚目: 不足アラート

- `日付`
- `不足シフト`
- `不足人数`
- 希望休違反がある場合は `希望休違反(staff_id)` も出力

## NumPy 依存エラーについて

`numpy.core.multiarray failed to import` が出る場合、Anaconda環境で起動されています。

対処:
- `./run.command` で起動する
- もしくは `.venv/bin/python app.py` で起動する

`app.py` は可能な限り `.venv` へ自動切替しますが、起動方法によってはAnacondaを掴むことがあるため、上記コマンドを推奨します。

## 主要コード

- `shiftgen/ce_gui.py`
- `shiftgen/domain.py`
- `shiftgen/solver.py`
- `shiftgen/excel.py`
- `shiftgen/io.py`
- `shiftgen/cli.py`
