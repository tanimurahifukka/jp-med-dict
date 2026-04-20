from __future__ import annotations

from io import BytesIO
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000049343.html"
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
    direct_links: list[str] = []
    page_links: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"])
        text = anchor.get_text(" ", strip=True)
        lower_href = href.lower().split("?", 1)[0]
        if lower_href.endswith(".csv"):
            direct_links.append(href)
            continue
        if "dpc" in lower_href or "傷病名" in text or "master" in lower_href:
            page_links.append(href)
    if direct_links:
        return direct_links[0]
    for page_url in page_links:
        try:
            page_response = _request(page_url)
        except requests.RequestException:
            continue
        nested = _find_download_link(page_response.content, page_url)
        if nested:
            return nested
    return None


def fetch() -> bytes:
    top_response = _request(SOURCE_URL)
    download_url = _find_download_link(top_response.content, SOURCE_URL)
    if download_url is None:
        raise RuntimeError(f"DPC 傷病名マスターのダウンロードリンクを解決できませんでした: {SOURCE_URL}")
    return _request(download_url).content


def _clean_cell(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = " ".join(str(value).split())
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text or None


def _load_table(raw: bytes) -> pd.DataFrame:
    readers = [
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
    raise ValueError("DPC 傷病名マスターを CSV として読み込めませんでした")


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

    dpc_col = _pick_column(columns, [("dpc", "コード"), ("傷病名", "コード")])
    standard_col = _pick_column(columns, [("標準", "病名"), ("傷病名",), ("名称",)])
    icd_col = _pick_column(columns, [("icd",), ("icd10",)])

    result = pd.DataFrame(
        {
            "dpc_code": _series_or_none(frame, dpc_col),
            "standard_name": _series_or_none(frame, standard_col),
            "icd10_code": _series_or_none(frame, icd_col),
        }
    )
    return result.dropna(subset=["dpc_code", "standard_name"], how="all").reset_index(drop=True)


def run() -> pd.DataFrame:
    """Return columns: dpc_code, standard_name, icd10_code."""
    return parse(fetch())


if __name__ == "__main__":
    print(len(run()))
