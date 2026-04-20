from __future__ import annotations

import re
import unicodedata

import jaconv

_CONTROL_RE = re.compile(r"[\u0000-\u001f\u007f\u200b\u200c\u200d\ufeff]")
_SPACE_RE = re.compile(r"\s+")
_LONG_SOUND_RE = re.compile(r"[-‐‑‒–—―ｰ]+")


def _clean_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = _CONTROL_RE.sub("", text)
    return text.strip()


def to_fullwidth_kana(s: str) -> str:
    text = _clean_text(s)
    text = jaconv.z2h(text, kana=False, digit=True, ascii=True)
    text = jaconv.h2z(text, kana=True, digit=False, ascii=False)
    text = _LONG_SOUND_RE.sub("ー", text)
    return _SPACE_RE.sub("", text)


def to_hiragana(s: str) -> str:
    return jaconv.kata2hira(to_fullwidth_kana(s))


def to_katakana(s: str) -> str:
    return jaconv.hira2kata(to_hiragana(s))


def normalize_name(s: str) -> str:
    text = _clean_text(s)
    return _SPACE_RE.sub("", text)
