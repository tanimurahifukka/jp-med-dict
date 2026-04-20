# jp-med-dict

日本語の薬剤名・一般名・病名辞書を公開データから構築し、SQLite + zstd で配布する OSS です。

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Build
```bash
python -m build.build_sqlite --version 0.1.0 --output dist/jp-med-dict-v0.1.0.sqlite
python -m build.manifest --sqlite dist/jp-med-dict-v0.1.0.sqlite --zst dist/jp-med-dict-v0.1.0.sqlite.zst --version 0.1.0 --output dist/manifest.json
```

## Query
```bash
sqlite3 dist/jp-med-dict-v0.1.0.sqlite "SELECT brand_name, yj_code FROM drugs WHERE brand_name_kana = 'ロキソニン' LIMIT 5;"
```

## License
Code: MIT
Data: CC BY-SA 4.0

設計詳細、スキーマ根拠、配布仕様は `docs/plan.md` を参照してください。
