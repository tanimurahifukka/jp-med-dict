from __future__ import annotations

from datetime import date
from io import BytesIO
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.mhlw.go.jp/topics/2024/04/tp20240401-01.html"
USER_AGENT = "jp-med-dict/0.1 (+https://github.com/tanimurahifukka/jp-med-dict)"
TIMEOUT = 60
HEADERS = {"User-Agent": USER_AGENT}


def _normalize_header(value: object) -> str:
    return "".join(unicodedata.normalize("NFKC", str(value)).lower().split())


def _request(url: str) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def _candidate_pages() -> list[str]:
    current_year = date.today().year
    years = [current_year, current_year - 1, current_year - 2, 2024]
    return list(dict.fromkeys([f"https://www.mhlw.go.jp/topics/{year}/04/tp{year}0401-01.html" for year in years] + [SOURCE_URL]))


def _find_download_link(html: bytes, base_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(base_url, anchor["href"])
        lower_href = href.lower().split("?", 1)[0]
        if lower_href.endswith((".xlsx", ".xls", ".csv")):
            candidates.append(href)
    candidates.sort(key=lambda url: (".csv" in url.lower(), url.lower()))
    return candidates[0] if candidates else None


def fetch() -> bytes:
    for page_url in _candidate_pages():
        try:
            page_response = _request(page_url)
        except requests.RequestException:
            continue
        download_url = _find_download_link(page_response.content, page_url)
        if download_url:
            return _request(download_url).content
    raise RuntimeError(f"薬価基準収載品目のダウンロードリンクを解決できませんでした: {SOURCE_URL}")


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
    raise ValueError("薬価基準収載品目を表形式で読み込めませんでした")


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

    yj_col = _pick_column(columns, [("yj", "コード"), ("薬価", "コード"), ("薬価基準", "コード")])
    brand_col = _pick_column(columns, [("品名",), ("販売名",), ("商品名",)])
    strength_col = _pick_column(columns, [("規格",), ("包装", "単位"), ("単位",)])
    manufacturer_col = _pick_column(columns, [("製造販売",), ("メーカー",), ("会社",)])
    price_col = _pick_column(columns, [("薬価",), ("金額",)])

    price_text = _series_or_none(frame, price_col).fillna("").str.replace(",", "", regex=False)
    price_yen = pd.to_numeric(price_text.str.extract(r"([0-9]+(?:\.[0-9]+)?)")[0], errors="coerce")

    result = pd.DataFrame(
        {
            "yj_code": _series_or_none(frame, yj_col),
            "brand_name": _series_or_none(frame, brand_col),
            "strength": _series_or_none(frame, strength_col),
            "manufacturer": _series_or_none(frame, manufacturer_col),
            "price_yen": price_yen,
        }
    )
    return result.dropna(subset=["yj_code", "brand_name"], how="all").reset_index(drop=True)


def run() -> pd.DataFrame:
    """Return columns: yj_code, brand_name, strength, manufacturer, price_yen."""
    return parse(fetch())


if __name__ == "__main__":
    print(len(run()))
