import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"

EXPECTED_TABLES = {
    "drugs",
    "ingredients",
    "drug_ingredients",
    "diseases",
    "disease_aliases",
    "icd10",
    "source_meta",
}


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def test_tables_exist():
    conn = _conn()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert EXPECTED_TABLES.issubset(names), f"missing tables: {EXPECTED_TABLES - names}"


def test_indexes_exist():
    conn = _conn()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex_%'"
    ).fetchall()
    names = {r[0] for r in rows}
    assert len(names) >= 10, f"too few indexes: {sorted(names)}"


def test_foreign_keys():
    conn = _conn()
    conn.execute("PRAGMA foreign_keys = ON")
    fks = conn.execute("PRAGMA foreign_key_list(drug_ingredients)").fetchall()
    assert len(fks) == 2
