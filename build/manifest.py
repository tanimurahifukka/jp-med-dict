from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sqlite3

SOURCE_ORDER = ("pmda", "yakkakijun", "ippanmei", "manbyo", "dpc")
ROW_COUNT_TABLES = ("drugs", "ingredients", "drug_ingredients", "diseases", "disease_aliases", "icd10")


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_sources(conn: sqlite3.Connection, sources_meta: dict | None = None) -> list[dict[str, str]]:
    if sources_meta:
        rows: list[dict[str, str]] = []
        for name in SOURCE_ORDER:
            if name not in sources_meta:
                continue
            meta = sources_meta[name]
            rows.append(
                {
                    "name": name,
                    "version": str(meta.get("version") or meta.get("source_version") or ""),
                    "url": str(meta.get("url") or meta.get("source_url") or ""),
                    "license": str(meta.get("license") or ""),
                }
            )
        return rows

    rows = conn.execute(
        """
        SELECT source, source_version, source_url, license
        FROM source_meta
        ORDER BY CASE source
            WHEN 'pmda' THEN 1
            WHEN 'yakkakijun' THEN 2
            WHEN 'ippanmei' THEN 3
            WHEN 'manbyo' THEN 4
            WHEN 'dpc' THEN 5
            ELSE 99
        END
        """
    ).fetchall()
    return [
        {"name": source, "version": source_version, "url": source_url, "license": license}
        for source, source_version, source_url, license in rows
    ]


def generate(sqlite_path: str, zst_path: str, version: str, sources_meta: dict | None = None) -> dict:
    conn = sqlite3.connect(sqlite_path)
    try:
        row_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ROW_COUNT_TABLES
        }
        sources = _load_sources(conn, sources_meta=sources_meta)
    finally:
        conn.close()

    return {
        "version": version,
        "built_at": _utc_now_iso(),
        "sqlite_file": os.path.basename(zst_path),
        "sqlite_sha256": _sha256(zst_path),
        "sqlite_size_bytes": os.path.getsize(zst_path),
        "uncompressed_sha256": _sha256(sqlite_path),
        "uncompressed_size_bytes": os.path.getsize(sqlite_path),
        "schema_version": 1,
        "row_counts": row_counts,
        "sources": sources,
        "license": {
            "code": "MIT",
            "data": "CC BY-SA 4.0",
        },
    }


def write(manifest: dict, output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate jp-med-dict manifest JSON.")
    parser.add_argument("--sqlite", required=True, help="Path to the uncompressed SQLite file.")
    parser.add_argument("--zst", required=True, help="Path to the compressed .zst file.")
    parser.add_argument("--version", required=True, help="Semantic version string.")
    parser.add_argument("--output", required=True, help="Manifest output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest = generate(sqlite_path=args.sqlite, zst_path=args.zst, version=args.version)
    write(manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
