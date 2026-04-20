from __future__ import annotations

from io import BytesIO
import re
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000066545.html"
USER_AGENT = "jp-med-dict/0.1 (+https://github.com/tanimurahifukka/jp-med-dict)"
TIMEOUT = 60
HEADERS = {"User-Agent": USER_AGENT}
_BRAND_SPLIT_RE = re.compile(r"[;；、,\n]+")


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
        if lower_href.endswith((".xlsx", ".xls", ".csv")):
            direct_links.append(href)
            continue
        if "一般名" in text or "処方" in text or "master" in lower_href:
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
        raise RuntimeError(f"一般名処方マスタのダウンロードリンクを解決できませんでした: {SOURCE_URL}")
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
        lambda: pd.read_excel(BytesIO(raw), dtype=str),
        lambda: pd.read_excel(BytesIO(raw), dtype=str, header=1),
        lambda: pd.read_excel(BytesIO(raw), dtype=str, header=2),
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
    raise ValueError("一般名処方マスタを表形式で読み込めませんでした")


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


def _join_brand_names(frame: pd.DataFrame, brand_columns: list[object]) -> pd.Series:
    if not brand_columns:
        return pd.Series([None] * len(frame), index=frame.index, dtype="object")

    def collapse(row: pd.Series) -> str | None:
        names: list[str] = []
        for value in row:
            cell = _clean_cell(value)
            if not cell:
                continue
            names.extend(part.strip() for part in _BRAND_SPLIT_RE.split(cell) if part.strip())
        unique_names = list(dict.fromkeys(names))
        return ";".join(unique_names) if unique_names else None

    return frame[brand_columns].apply(collapse, axis=1)


def parse(raw: bytes) -> pd.DataFrame:
    frame = _load_table(raw)
    columns = list(frame.columns)
    normalized = {_normalize_header(column): column for column in columns}

    code_col = _pick_column(columns, [("コード",), ("一般名処方", "コード")])
    generic_col = _pick_column(columns, [("一般名処方", "標準的", "記載"), ("一般名",), ("成分",)])
    kana_col = _pick_column(columns, [("カナ",), ("かな",), ("ﾌﾘｶﾞﾅ",)])
    brand_columns = [
        column
        for column in columns
        if any(token in _normalize_header(column) for token in ("商品名", "販売名", "銘柄", "先発", "代表商品"))
    ]
    if not brand_columns and "対応商品名" in normalized:
        brand_columns = [normalized["対応商品名"]]

    result = pd.DataFrame(
        {
            "ippanmei_code": _series_or_none(frame, code_col),
            "generic_name": _series_or_none(frame, generic_col),
            "generic_kana": _series_or_none(frame, kana_col),
            "brand_names": _join_brand_names(frame, brand_columns),
        }
    )
    return result.dropna(subset=["ippanmei_code", "generic_name"], how="all").reset_index(drop=True)


def run() -> pd.DataFrame:
    """Return columns: ippanmei_code, generic_name, generic_kana, brand_names."""
    return parse(fetch())


if __name__ == "__main__":
    print(len(run()))
