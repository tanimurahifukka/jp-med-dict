"""Normalization helpers for jp-med-dict."""

from .dedupe import dedupe_diseases, dedupe_drugs, dedupe_ingredients
from .kana import normalize_name, to_fullwidth_kana, to_hiragana, to_katakana
from .link import link_disease_aliases, link_drug_ingredients

__all__ = [
    "dedupe_diseases",
    "dedupe_drugs",
    "dedupe_ingredients",
    "link_disease_aliases",
    "link_drug_ingredients",
    "normalize_name",
    "to_fullwidth_kana",
    "to_hiragana",
    "to_katakana",
]
