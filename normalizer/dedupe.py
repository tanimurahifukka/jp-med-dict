from __future__ import annotations

import pandas as pd

DRUG_PRIORITY = {"yakkakijun": 3, "pmda": 2, "ippanmei": 1}
INGREDIENT_PRIORITY = {"ippanmei": 2, "pmda": 1}
DISEASE_PRIORITY = {"dpc": 2, "manbyo": 1}


def _is_missing(value: object) -> bool:
    if pd.isna(value):
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _string_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].map(lambda value: "" if _is_missing(value) else str(value).strip())


def _merge_group(group: pd.DataFrame, priority_map: dict[str, int]) -> pd.Series:
    ranked = group.copy()
    source_series = ranked["source"] if "source" in ranked.columns else pd.Series("", index=ranked.index, dtype="object")
    version_series = (
        ranked["source_version"] if "source_version" in ranked.columns else pd.Series("", index=ranked.index, dtype="object")
    )
    ranked["__priority"] = source_series.map(lambda value: priority_map.get(str(value), 0))
    ranked["__version_sort"] = version_series.fillna("").astype(str)
    ranked = ranked.sort_values(["__priority", "__version_sort"], ascending=[False, False], kind="stable")

    merged = ranked.iloc[0].drop(labels=["__priority", "__version_sort"]).copy()
    for column in group.columns:
        if not _is_missing(merged[column]):
            continue
        for value in ranked[column]:
            if not _is_missing(value):
                merged[column] = value
                break
    return merged


def _dedupe(frame: pd.DataFrame, key: pd.Series, priority_map: dict[str, int]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

    working = frame.copy()
    working["__dedupe_key"] = key.fillna("")
    merged_rows = [_merge_group(group.drop(columns="__dedupe_key"), priority_map) for _, group in working.groupby("__dedupe_key", sort=False)]
    result = pd.DataFrame(merged_rows)
    return result.loc[:, frame.columns].reset_index(drop=True)


def dedupe_drugs(df: pd.DataFrame) -> pd.DataFrame:
    yj = _string_series(df, "yj_code")
    brand = _string_series(df, "brand_name_kana")
    manufacturer = _string_series(df, "manufacturer")
    key = yj.where(yj != "", "brand:" + brand + "|maker:" + manufacturer).map(lambda value: f"drug:{value}")
    return _dedupe(df, key, DRUG_PRIORITY)


def dedupe_ingredients(df: pd.DataFrame) -> pd.DataFrame:
    code = _string_series(df, "ippanmei_code")
    generic = _string_series(df, "generic_kana")
    key = code.where(code != "", "generic:" + generic).map(lambda value: f"ingredient:{value}")
    return _dedupe(df, key, INGREDIENT_PRIORITY)


def dedupe_diseases(df: pd.DataFrame) -> pd.DataFrame:
    dpc = _string_series(df, "dpc_code")
    name = _string_series(df, "standard_name")
    key = dpc.where(dpc != "", "name:" + name).map(lambda value: f"disease:{value}")
    return _dedupe(df, key, DISEASE_PRIORITY)
