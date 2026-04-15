# AGENTS.md

このファイルは `ce-shift` リポジトリ内で作業するエージェント向けの補助指示です。

## 目的
- CE部署向けシフト生成サービスを保守・改善する。
- 既存 `shiftgen`（別部署向け）とは分離して扱う。

## 作業方針
- 仕様の正本は以下を参照すること。
  - `docs/ce_shift_spec_v1_1.md`
  - `docs/ce_input_schema.json`
- 実装の中心は以下。
  - `shiftgen/ce_gui.py`
  - `shiftgen/solver.py`
  - `shiftgen/domain.py`
  - `shiftgen/io.py`
  - `shiftgen/excel.py`

## 実行方針
- GUI起動は `.venv` 前提。
  - 推奨: `./run.command`
  - 代替: `.venv/bin/python app.py`
- CLI実行も `.venv` を使う。
  - `.venv/bin/python -m shiftgen.cli --in sample_config_ce.json --out out.xlsx`

## 変更時の注意
- 旧 `shiftgen/gui.py` を CE仕様の基準にしないこと（`ce_gui.py` を優先）。
- 互換性よりも CE仕様準拠を優先すること。
- 生成サンプルの `.xlsx` は原則コミットしないこと。

## ドキュメント更新ルール
- 仕様変更時は `README.md` と `docs/` を同時更新すること。
- 運用に影響する変更は README の「使い方」「注意点」に反映すること。
