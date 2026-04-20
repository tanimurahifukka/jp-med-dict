from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import sqlite3
import sys
import warnings

import pandas as pd
import zstandard

from normalizer import dedupe, link
from sources import dpc_shobyomei, ippanmei, manbyo, pmda_attachment, yakkakijun

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT_DIR, "schema.sql")
SOURCE_ORDER = ("pmda", "yakkakijun", "ippanmei", "manbyo", "dpc")

DRUG_COLUMNS = [
    "yj_code",
    "brand_name",
    "brand_name_kana",
    "brand_name_hira",
    "dosage_form",
    "strength",
    "manufacturer",
    "approval_no",
    "price_yen",
    "source",
    "source_version",
]
INGREDIENT_COLUMNS = [
    "ippanmei_code",
    "generic_name",
    "generic_kana",
    "generic_hira",
    "source",
    "source_version",
]
DRUG_INGREDIENT_COLUMNS = ["drug_id", "ingredient_id", "amount"]
DISEASE_COLUMNS = [
    "standard_name",
    "standard_kana",
    "standard_hira",
    "icd10_code",
    "dpc_code",
    "source",
    "source_version",
]
DISEASE_ALIAS_COLUMNS = ["disease_id", "alias", "alias_kana", "alias_hira", "confidence", "source"]
ICD10_COLUMNS = ["icd10_code", "jp_label", "source", "source_version"]
SOURCE_META_COLUMNS = ["source", "source_version", "fetched_at", "row_count", "source_url", "license"]

SOURCE_SPECS = {
    "pmda": {
        "module": pmda_attachment,
        "source_url": pmda_attachment.SOURCE_URL,
        "license": "Public",
        "columns": [
            "yj_code",
            "brand_name",
            "brand_name_kana",
            "generic_name",
            "generic_kana",
            "dosage_form",
            "strength",
            "manufacturer",
            "approval_no",
        ],
    },
    "yakkakijun": {
        "module": yakkakijun,
        "source_url": yakkakijun.SOURCE_URL,
        "license": "Public",
        "columns": ["yj_code", "brand_name", "strength", "manufacturer", "price_yen"],
    },
    "ippanmei": {
        "module": ippanmei,
        "source_url": ippanmei.SOURCE_URL,
        "license": "Public",
        "columns": ["ippanmei_code", "generic_name", "generic_kana", "brand_names"],
    },
    "manbyo": {
        "module": manbyo,
        "source_url": manbyo.SOURCE_URL,
        "license": "CC BY-SA 4.0",
        "columns": ["surface", "standard_name", "icd10", "confidence"],
    },
    "dpc": {
        "module": dpc_shobyomei,
        "source_url": dpc_shobyomei.SOURCE_URL,
        "license": "Public",
        "columns": ["dpc_code", "standard_name", "icd10_code"],
    },
}


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _clean_text(value: object) -> str | None:
    if pd.isna(value) or value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _normalize_kana(value: object, fallback: object | None = None) -> str | None:
    text = _clean_text(value)
    if text is None:
        text = _clean_text(fallback)
    if text is None:
        return None
    return link.to_fullwidth_kana(text)


def _to_hiragana(value: object) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    return link.to_hiragana(text)


def _split_names(value: object) -> list[str]:
    return link._split_names(value)


def _split_name_pairs(name_value: object, kana_value: object) -> list[tuple[str, str | None]]:
    names = _split_names(name_value)
    if not names:
        return []

    kana_names = _split_names(kana_value)
    if kana_names and len(kana_names) == len(names):
        return list(zip(names, kana_names, strict=False))

    kana_text = _clean_text(kana_value)
    if len(names) == 1:
        return [(names[0], kana_text)]
    return [(name, None) for name in names]


def _run_source(name: str) -> tuple[pd.DataFrame, dict[str, object]]:
    spec = SOURCE_SPECS[name]
    fetched_at = _utc_now_iso()
    try:
        frame = spec["module"].run().reindex(columns=spec["columns"])
    except Exception as exc:  # pragma: no cover - exercised only when source fetch fails.
        message = f"{name} failed: {exc}"
        warnings.warn(message)
        print(f"warning: {message}", file=sys.stderr)
        frame = _empty_frame(spec["columns"])

    meta = {
        "source": name,
        "source_version": "",
        "fetched_at": fetched_at,
        "row_count": int(len(frame)),
        "source_url": spec["source_url"],
        "license": spec["license"],
    }
    return frame, meta


def _prepare_pmda_drugs(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        brand_name = _clean_text(getattr(row, "brand_name", None))
        if brand_name is None:
            continue
        brand_kana = _normalize_kana(getattr(row, "brand_name_kana", None), brand_name)
        rows.append(
            {
                "yj_code": _clean_text(getattr(row, "yj_code", None)),
                "brand_name": brand_name,
                "brand_name_kana": brand_kana,
                "brand_name_hira": _to_hiragana(brand_kana),
                "dosage_form": _clean_text(getattr(row, "dosage_form", None)),
                "strength": _clean_text(getattr(row, "strength", None)),
                "manufacturer": _clean_text(getattr(row, "manufacturer", None)),
                "approval_no": _clean_text(getattr(row, "approval_no", None)),
                "price_yen": None,
                "source": "pmda",
                "source_version": version,
            }
        )
    return pd.DataFrame(rows, columns=DRUG_COLUMNS)


def _prepare_yakkakijun_drugs(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        brand_name = _clean_text(getattr(row, "brand_name", None))
        if brand_name is None:
            continue
        brand_kana = _normalize_kana(None, brand_name)
        rows.append(
            {
                "yj_code": _clean_text(getattr(row, "yj_code", None)),
                "brand_name": brand_name,
                "brand_name_kana": brand_kana,
                "brand_name_hira": _to_hiragana(brand_kana),
                "dosage_form": None,
                "strength": _clean_text(getattr(row, "strength", None)),
                "manufacturer": _clean_text(getattr(row, "manufacturer", None)),
                "approval_no": None,
                "price_yen": getattr(row, "price_yen", None),
                "source": "yakkakijun",
                "source_version": version,
            }
        )
    return pd.DataFrame(rows, columns=DRUG_COLUMNS)


def _prepare_ippanmei_drugs(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        for brand_name in _split_names(getattr(row, "brand_names", None)):
            brand_kana = _normalize_kana(None, brand_name)
            rows.append(
                {
                    "yj_code": None,
                    "brand_name": brand_name,
                    "brand_name_kana": brand_kana,
                    "brand_name_hira": _to_hiragana(brand_kana),
                    "dosage_form": None,
                    "strength": None,
                    "manufacturer": None,
                    "approval_no": None,
                    "price_yen": None,
                    "source": "ippanmei",
                    "source_version": version,
                }
            )
    return pd.DataFrame(rows, columns=DRUG_COLUMNS)


def _prepare_pmda_ingredients(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        for generic_name, generic_kana_raw in _split_name_pairs(
            getattr(row, "generic_name", None),
            getattr(row, "generic_kana", None),
        ):
            generic_name = _clean_text(generic_name)
            if generic_name is None:
                continue
            generic_kana = _normalize_kana(generic_kana_raw, generic_name)
            rows.append(
                {
                    "ippanmei_code": None,
                    "generic_name": generic_name,
                    "generic_kana": generic_kana,
                    "generic_hira": _to_hiragana(generic_kana),
                    "source": "pmda",
                    "source_version": version,
                }
            )
    return pd.DataFrame(rows, columns=INGREDIENT_COLUMNS)


def _prepare_ippanmei_ingredients(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        generic_name = _clean_text(getattr(row, "generic_name", None))
        if generic_name is None:
            continue
        generic_kana = _normalize_kana(getattr(row, "generic_kana", None), generic_name)
        rows.append(
            {
                "ippanmei_code": _clean_text(getattr(row, "ippanmei_code", None)),
                "generic_name": generic_name,
                "generic_kana": generic_kana,
                "generic_hira": _to_hiragana(generic_kana),
                "source": "ippanmei",
                "source_version": version,
            }
        )
    return pd.DataFrame(rows, columns=INGREDIENT_COLUMNS)


def _prepare_dpc_diseases(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        standard_name = _clean_text(getattr(row, "standard_name", None))
        if standard_name is None:
            continue
        standard_kana = _normalize_kana(None, standard_name)
        rows.append(
            {
                "standard_name": standard_name,
                "standard_kana": standard_kana,
                "standard_hira": _to_hiragana(standard_kana),
                "icd10_code": _clean_text(getattr(row, "icd10_code", None)),
                "dpc_code": _clean_text(getattr(row, "dpc_code", None)),
                "source": "dpc",
                "source_version": version,
            }
        )
    return pd.DataFrame(rows, columns=DISEASE_COLUMNS)


def _prepare_manbyo_diseases(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        standard_name = _clean_text(getattr(row, "standard_name", None))
        if standard_name is None:
            continue
        standard_kana = _normalize_kana(None, standard_name)
        rows.append(
            {
                "standard_name": standard_name,
                "standard_kana": standard_kana,
                "standard_hira": _to_hiragana(standard_kana),
                "icd10_code": _clean_text(getattr(row, "icd10", None)),
                "dpc_code": None,
                "source": "manbyo",
                "source_version": version,
            }
        )
    return pd.DataFrame(rows, columns=DISEASE_COLUMNS)


def _prepare_icd10(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in frame.itertuples(index=False):
        icd10_code = _clean_text(getattr(row, "icd10_code", None))
        if icd10_code is None:
            continue
        rows.append(
            {
                "icd10_code": icd10_code,
                "jp_label": _clean_text(getattr(row, "standard_name", None)),
                "source": "dpc",
                "source_version": version,
            }
        )

    if not rows:
        return _empty_frame(ICD10_COLUMNS)

    frame_out = pd.DataFrame(rows, columns=ICD10_COLUMNS)
    return frame_out.drop_duplicates(subset=["icd10_code"], keep="first").reset_index(drop=True)


def _insert_frame(conn: sqlite3.Connection, table: str, frame: pd.DataFrame) -> None:
    clean = frame.where(pd.notna(frame), None)
    clean.to_sql(table, conn, if_exists="append", index=False)


def _resolve_drug_ingredients(conn: sqlite3.Connection, links_df: pd.DataFrame) -> pd.DataFrame:
    if links_df.empty:
        return _empty_frame(DRUG_INGREDIENT_COLUMNS)

    drug_rows = conn.execute("SELECT drug_id, brand_name, strength FROM drugs").fetchall()
    ingredient_rows = conn.execute("SELECT ingredient_id, generic_name FROM ingredients").fetchall()

    by_brand: dict[str, list[int]] = {}
    by_brand_amount: dict[tuple[str, str], list[int]] = {}
    for drug_id, brand_name, strength in drug_rows:
        if brand_name is None:
            continue
        brand_text = str(brand_name)
        by_brand.setdefault(brand_text, []).append(int(drug_id))
        if strength is not None:
            by_brand_amount.setdefault((brand_text, str(strength)), []).append(int(drug_id))

    ingredient_by_name = {str(generic_name): int(ingredient_id) for ingredient_id, generic_name in ingredient_rows if generic_name is not None}

    records: list[dict[str, object]] = []
    for row in links_df.itertuples(index=False):
        brand_name = _clean_text(getattr(row, "brand_name", None))
        generic_name = _clean_text(getattr(row, "generic_name", None))
        amount = _clean_text(getattr(row, "amount", None))
        if brand_name is None or generic_name is None:
            continue

        ingredient_id = ingredient_by_name.get(generic_name)
        if ingredient_id is None:
            continue

        drug_ids = by_brand_amount.get((brand_name, amount), []) if amount else []
        if not drug_ids:
            drug_ids = by_brand.get(brand_name, [])

        for drug_id in drug_ids:
            records.append({"drug_id": drug_id, "ingredient_id": ingredient_id, "amount": amount})

    if not records:
        return _empty_frame(DRUG_INGREDIENT_COLUMNS)

    frame_out = pd.DataFrame(records, columns=DRUG_INGREDIENT_COLUMNS)
    return frame_out.drop_duplicates().reset_index(drop=True)


def _resolve_disease_aliases(conn: sqlite3.Connection, aliases_df: pd.DataFrame) -> pd.DataFrame:
    if aliases_df.empty:
        return _empty_frame(DISEASE_ALIAS_COLUMNS)

    disease_rows = conn.execute("SELECT disease_id, standard_name FROM diseases").fetchall()
    disease_by_name = {str(standard_name): int(disease_id) for disease_id, standard_name in disease_rows if standard_name is not None}

    records: list[dict[str, object]] = []
    for row in aliases_df.itertuples(index=False):
        standard_name = _clean_text(getattr(row, "standard_name", None))
        disease_id = disease_by_name.get(standard_name or "")
        if disease_id is None:
            continue
        records.append(
            {
                "disease_id": disease_id,
                "alias": _clean_text(getattr(row, "alias", None)),
                "alias_kana": _clean_text(getattr(row, "alias_kana", None)),
                "alias_hira": _clean_text(getattr(row, "alias_hira", None)),
                "confidence": getattr(row, "confidence", None),
                "source": _clean_text(getattr(row, "source", None)) or "manbyo",
            }
        )

    if not records:
        return _empty_frame(DISEASE_ALIAS_COLUMNS)

    frame_out = pd.DataFrame(records, columns=DISEASE_ALIAS_COLUMNS)
    return frame_out.drop_duplicates().reset_index(drop=True)


def build(output_path: str, version: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    conn = sqlite3.connect(output_path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())

        raw_frames: dict[str, pd.DataFrame] = {}
        source_meta_rows: list[dict[str, object]] = []
        for name in SOURCE_ORDER:
            frame, meta = _run_source(name)
            meta["source_version"] = version
            raw_frames[name] = frame
            source_meta_rows.append(meta)

        drugs_df = pd.concat(
            [
                _prepare_pmda_drugs(raw_frames["pmda"], version),
                _prepare_yakkakijun_drugs(raw_frames["yakkakijun"], version),
                _prepare_ippanmei_drugs(raw_frames["ippanmei"], version),
            ],
            ignore_index=True,
        )
        drugs_df = dedupe.dedupe_drugs(drugs_df)

        ingredients_df = pd.concat(
            [
                _prepare_pmda_ingredients(raw_frames["pmda"], version),
                _prepare_ippanmei_ingredients(raw_frames["ippanmei"], version),
            ],
            ignore_index=True,
        )
        ingredients_df = dedupe.dedupe_ingredients(ingredients_df)

        diseases_df = pd.concat(
            [
                _prepare_dpc_diseases(raw_frames["dpc"], version),
                _prepare_manbyo_diseases(raw_frames["manbyo"], version),
            ],
            ignore_index=True,
        )
        diseases_df = dedupe.dedupe_diseases(diseases_df)

        icd10_df = _prepare_icd10(raw_frames["dpc"], version)

        _insert_frame(conn, "drugs", drugs_df)
        _insert_frame(conn, "ingredients", ingredients_df)
        _insert_frame(conn, "diseases", diseases_df)
        _insert_frame(conn, "icd10", icd10_df)

        drug_link_inputs = raw_frames["pmda"].copy()
        ingredient_link_inputs = pd.concat(
            [
                ingredients_df[["generic_name"]],
                raw_frames["ippanmei"][["generic_name", "brand_names"]],
            ],
            ignore_index=True,
            sort=False,
        )
        drug_ingredients_df = link.link_drug_ingredients(drug_link_inputs, ingredient_link_inputs)
        disease_aliases_input = raw_frames["manbyo"].assign(source="manbyo")
        disease_aliases_df = link.link_disease_aliases(diseases_df, disease_aliases_input)

        _insert_frame(conn, "drug_ingredients", _resolve_drug_ingredients(conn, drug_ingredients_df))
        _insert_frame(conn, "disease_aliases", _resolve_disease_aliases(conn, disease_aliases_df))

        for row in source_meta_rows:
            conn.execute(
                """
                INSERT INTO source_meta (
                    source, source_version, fetched_at, row_count, source_url, license
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source"],
                    row["source_version"],
                    row["fetched_at"],
                    row["row_count"],
                    row["source_url"],
                    row["license"],
                ),
            )

        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()


def compress(sqlite_path: str) -> str:
    zst_path = f"{sqlite_path}.zst"
    digest = hashlib.sha256(sqlite_path.encode("utf-8")).hexdigest()[:8]
    tmp_path = f"{zst_path}.{digest}.tmp"

    compressor = zstandard.ZstdCompressor(level=19)
    with open(sqlite_path, "rb") as src, open(tmp_path, "wb") as dst:
        with compressor.stream_writer(dst) as writer:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                writer.write(chunk)

    os.replace(tmp_path, zst_path)
    return zst_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build jp-med-dict SQLite and zstd archive.")
    parser.add_argument("--version", required=True, help="Version string written into source metadata.")
    parser.add_argument("--output", required=True, help="Path to the uncompressed SQLite output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    build(output_path=args.output, version=args.version)
    zst_path = compress(args.output)
    print(zst_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
