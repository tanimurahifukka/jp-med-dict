from __future__ import annotations

import re

import pandas as pd

from .kana import to_fullwidth_kana, to_hiragana

_SPLIT_RE = re.compile(r"[;/、,，・+＋]+")


def _split_names(value: object) -> list[str]:
    if pd.isna(value) or value is None:
        return []
    parts = [part.strip() for part in _SPLIT_RE.split(str(value)) if part.strip()]
    return list(dict.fromkeys(parts))


def link_drug_ingredients(drugs_df: pd.DataFrame, ingredients_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    ingredient_names = set(ingredients_df.get("generic_name", pd.Series(dtype="object")).dropna().astype(str))

    if "generic_name" in drugs_df.columns:
        for row in drugs_df.itertuples(index=False):
            brand_name = getattr(row, "brand_name", None)
            amount = getattr(row, "strength", None)
            for generic_name in _split_names(getattr(row, "generic_name", None)):
                if brand_name and generic_name and (not ingredient_names or generic_name in ingredient_names):
                    records.append(
                        {
                            "brand_name": str(brand_name).strip(),
                            "generic_name": generic_name,
                            "amount": None if pd.isna(amount) else str(amount).strip(),
                        }
                    )

    if "brand_names" in ingredients_df.columns:
        for row in ingredients_df.itertuples(index=False):
            generic_name = getattr(row, "generic_name", None)
            for brand_name in _split_names(getattr(row, "brand_names", None)):
                if brand_name and generic_name:
                    records.append(
                        {
                            "brand_name": brand_name,
                            "generic_name": str(generic_name).strip(),
                            "amount": None,
                        }
                    )

    columns = ["brand_name", "generic_name", "amount"]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records, columns=columns).drop_duplicates().reset_index(drop=True)


def link_disease_aliases(diseases_df: pd.DataFrame, manbyo_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    standard_names = set(diseases_df.get("standard_name", pd.Series(dtype="object")).dropna().astype(str))

    for row in manbyo_df.itertuples(index=False):
        alias = getattr(row, "surface", None)
        standard_name = getattr(row, "standard_name", None)
        source = getattr(row, "source", None)
        if pd.isna(alias) or pd.isna(standard_name):
            continue
        alias_text = str(alias).strip()
        standard_text = str(standard_name).strip()
        if not alias_text or not standard_text or alias_text == standard_text or standard_text not in standard_names:
            continue
        alias_kana = to_fullwidth_kana(alias_text)
        records.append(
            {
                "standard_name": standard_text,
                "alias": alias_text,
                "alias_kana": alias_kana,
                "alias_hira": to_hiragana(alias_kana),
                "confidence": getattr(row, "confidence", None),
                "source": "manbyo" if pd.isna(source) or not str(source).strip() else str(source).strip(),
            }
        )

    columns = ["standard_name", "alias", "alias_kana", "alias_hira", "confidence", "source"]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records, columns=columns).drop_duplicates().reset_index(drop=True)
