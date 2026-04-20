build:
    python -m build.build_sqlite --version 0.1.0 --output dist/jp-med-dict-v0.1.0.sqlite

test:
    pytest -q

fetch-sources:
    python -m sources.pmda_attachment
    python -m sources.yakkakijun
    python -m sources.ippanmei
    python -m sources.manbyo
    python -m sources.dpc_shobyomei

make-dist:
    python -m build.build_sqlite --version 0.1.0 --output dist/jp-med-dict-v0.1.0.sqlite
    python -m build.manifest --sqlite dist/jp-med-dict-v0.1.0.sqlite --zst dist/jp-med-dict-v0.1.0.sqlite.zst --version 0.1.0 --output dist/manifest.json

clean:
    rm -rf dist/*.sqlite dist/*.zst dist/*.json __pycache__ .pytest_cache
