from __future__ import annotations

from io import BytesIO
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://sociocom.naist.jp/manbyo-dic/"
USER_AGENT = "jp-med-dict/0.1 (+https://github.com/tanimurahifukka/jp-med-dict)"
TIMEOUT = 60
HEADERS = {"User-Agent": USER_AGENT}


def _normalize_header(value: object) -> str:
    return "".join(unicodedata.normalize("NFKC", str(value)).lower().split())


def _request(url: str) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def _find_download_link(html: bytes, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"])
        lower_href = href.lower().split("?", 1)[0]
        if lower_href.endswith((".tsv", ".csv")):
            candidates.append(href)
    candidates.sort(key=lambda url: (".csv" in url.lower(), url.lower()))
    return candidates[0] if candidates else None


def fetch() -> bytes:
    top_response = _request(SOURCE_URL)
    download_url = _find_download_link(top_response.content, SOURCE_URL)
    if download_url is None:
        raise RuntimeError(f"万病辞書のダウンロードリンクを解決できませんでした: {SOURCE_URL}")
    return _request(download_url).content


def _clean_cell(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = " ".join(str(value).split())
    return text or None


def _load_table(raw: bytes) -> pd.DataFrame:
    readers = [
        lambda: pd.read_csv(BytesIO(raw), sep="\t", dtype=str, encoding="utf-8-sig"),
        lambda: pd.read_csv(BytesIO(raw), sep="\t", dtype=str, encoding="cp932"),
        lambda: pd.read_csv(BytesIO(raw), dtype=str, encoding="utf-8-sig"),
        lambda: pd.read_csv(BytesIO(raw), dtype=str, encoding="cp932"),
    ]
    for reader in readers:
        try:
            frame = reader().dropna(how="all")
        except Exception:
            continue
        if not frame.empty:
            return frame
    raise ValueError("万病辞書を表形式で読み込めませんでした")


def _pick_column(columns: list[object], candidates: list[tuple[str, ...]]) -> object | None:
    normalized = {column: _normalize_header(column) for column in columns}
    for tokens in candidates:
        for column, normalized_name in normalized.items():
            if all(token in normalized_name for token in tokens):
                return column
    return None


def _series_or_none(frame: pd.DataFrame, column: object | None) -> pd.Series:
    if column is None:
        return pd.Series([None] * len(frame), index=frame.index, dtype="object")
    return frame[column].map(_clean_cell)


def parse(raw: bytes) -> pd.DataFrame:
    frame = _load_table(raw)
    columns = list(frame.columns)

    surface_col = _pick_column(columns, [("surface",), ("出現",), ("表記",), ("別名",)])
    standard_col = _pick_column(columns, [("standard",), ("標準",), ("正規",), ("疾患名",)])
    icd_col = _pick_column(columns, [("icd",), ("icd10",)])
    confidence_col = _pick_column(columns, [("confidence",), ("信頼",), ("score",)])

    confidence_text = _series_or_none(frame, confidence_col).fillna("")
    confidence = pd.to_numeric(confidence_text.str.extract(r"([0-9]+(?:\.[0-9]+)?)")[0], errors="coerce")

    result = pd.DataFrame(
        {
            "surface": _series_or_none(frame, surface_col),
            "standard_name": _series_or_none(frame, standard_col),
            "icd10": _series_or_none(frame, icd_col),
            "confidence": confidence,
        }
    )
    return result.dropna(subset=["surface", "standard_name"], how="all").reset_index(drop=True)


def run() -> pd.DataFrame:
    """Return columns: surface, standard_name, icd10, confidence."""
    return parse(fetch())


if __name__ == "__main__":
    print(len(run()))
