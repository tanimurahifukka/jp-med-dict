import os
import sqlite3

import pytest

SQLITE = os.environ.get("JP_MED_DICT_SQLITE")

pytestmark = pytest.mark.skipif(
    not SQLITE or not os.path.exists(SQLITE),
    reason="JP_MED_DICT_SQLITE not set or file missing",
)

THRESHOLDS = {
    "drugs": 1000,
    "ingredients": 500,
    "diseases": 1000,
    "disease_aliases": 1000,
}


def test_row_counts():
    conn = sqlite3.connect(SQLITE)
    for table, threshold in THRESHOLDS.items():
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count >= threshold, f"{table}: {count} < {threshold}"
    conn.close()
