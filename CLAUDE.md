# shiftgen-ce — Claude Code 向けプロジェクトガイド

## プロジェクト概要

CE部署向けの月次シフト表を自動生成する Python デスクトップアプリ。
GUI (tkinter) と CLI の両エントリポイントを持ち、Google OR-Tools の CP-SAT ソルバーで制約最適化を行い、openpyxl で Excel ファイルを出力する。

## 環境

- Python 3.12
- 仮想環境: `.venv/`（macOS では `source .venv/bin/activate` で有効化）
- 依存パッケージ: `pip install -r requirements.txt`
- 開発用追加: `pip install -r requirements-dev.txt`（PyInstaller を含む）

## 実行方法

```bash
# GUI 起動
python app.py

# CLI 実行（JSON → Excel）
python -m shiftgen.cli --in sample_config_ce.json --out output.xlsx
```

## ディレクトリ構成

```
shiftgen-ce/
├── app.py                  # GUI エントリポイント（CE GUI を起動）
├── cli.py                  # CLI エントリポイント（shiftgen.cli へ委譲）
├── sample_config_ce.json   # CE入力 JSON サンプル
├── docs/
│   ├── ce_input_schema.json
│   └── ce_shift_spec_v1_1.md
├── requirements.txt        # 本番依存
├── requirements-dev.txt    # 開発依存（PyInstaller）
└── shiftgen/
    ├── ce_gui.py           # CE向け tkinter GUI
    ├── domain.py           # データモデル
    ├── solver.py           # CP-SAT ソルバー（solve 関数）
    ├── cli.py              # CLI（argparse）
    ├── excel.py            # CE形式の Excel 出力
    ├── io.py               # CE JSON 入力パース
    ├── calendar_utils.py   # 日付ユーティリティ
```

## ドメイン知識

仕様の正本は `docs/ce_shift_spec_v1_1.md` と `docs/ce_input_schema.json`。
ここでは実装確認用に要点だけ記す。

### 入力 JSON（sample_config_ce.json 参照）

```json
{
  "month": "YYYY-MM",
  "holidays": ["YYYY-MM-DD"],
  "staff": [
    {
      "id": "S1",
      "name": "名前",
      "role": "normal",
      "employment_type": "full_time",
      "has_other_skill": false
    }
  ],
  "requests_off": {"S1": ["YYYY-MM-DD"]},
  "settings": {
    "max_time_in_seconds": 15.0,
    "num_search_workers": 8,
    "allow_partial": true
  }
}
```

## コーディング規約

- `from __future__ import annotations` を各ファイル先頭に記載（Python 3.12 互換）
- データモデルは `@dataclass(frozen=True)` で不変オブジェクトとして定義
- ソルバー内部は OR-Tools の `cp_model` を直接使用（抽象化レイヤーなし）
- GUI 側のスレッド安全性: ソルバーは別スレッドで実行し `self.after(0, ...)` で UI 更新
- エラーは `SolveError` (RuntimeError サブクラス) に集約して GUI/CLI 両方で捕捉
- 日本語文字列はソースコード内に直書き（`ensure_ascii=False` で JSON 出力）

## テスト

現時点でテストコードは未整備。変更後は以下で動作確認する:

```bash
python -m shiftgen.cli --in sample_config_ce.json --out /tmp/test_output.xlsx
python app.py
```

## パッケージング（PyInstaller）

```bash
pyinstaller app.py --name shiftgen --onefile --windowed
```
