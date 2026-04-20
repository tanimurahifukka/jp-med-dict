from __future__ import annotations

from io import BytesIO
import zipfile
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import etree

SOURCE_URL = "https://www.pmda.go.jp/PmdaSearch/iyakuSearch/"
USER_AGENT = "jp-med-dict/0.1 (+https://github.com/tanimurahifukka/jp-med-dict)"
TIMEOUT = 60
HEADERS = {"User-Agent": USER_AGENT}


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
        lower_href = href.lower()
        lower_text = text.lower()
        if lower_href.split("?", 1)[0].endswith(".zip"):
            direct_links.append(href)
            continue
        if any(token in lower_href or token in lower_text for token in ("download", "zip", "xml", "dl")):
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
    archive_url = _find_download_link(top_response.content, SOURCE_URL)
    if archive_url is None:
        raise RuntimeError(f"PMDA XML ZIP link not found from {SOURCE_URL}")
    return _request(archive_url).content


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return etree.QName(tag).localname.lower()
    return tag.lower()


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def _first_text(element: etree._Element, candidates: set[str]) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) not in candidates:
            continue
        text = _clean_value("".join(child.itertext()))
        if text:
            return text
    return None


def _parse_drug_element(element: etree._Element) -> dict[str, str | None]:
    row = {
        "yj_code": _first_text(element, {"yjcode", "yj_cd", "drugpricecode", "drugcode", "hotcode"}),
        "brand_name": _first_text(element, {"hanbainame", "salesname", "brandname", "productname", "meishouhanbai"}),
        "brand_name_kana": _first_text(element, {"hanbainamekana", "salesnamekana", "brandnamekana", "productnamekana"}),
        "generic_name": _first_text(element, {"ippanmei", "genericname", "ingredientname", "seibunmei", "compositionname"}),
        "generic_kana": _first_text(element, {"ippanmeikana", "genericnamekana", "ingredientnamekana", "seibunmeikana"}),
        "dosage_form": _first_text(element, {"zaikei", "dosageform", "form"}),
        "strength": _first_text(element, {"kikaku", "strength", "standard", "specification"}),
        "manufacturer": _first_text(
            element,
            {
                "seizouhanbaigyosha",
                "manufacturer",
                "companyname",
                "marketingauthorizationholder",
            },
        ),
        "approval_no": _first_text(element, {"shouninbango", "approvalnumber", "approvalno"}),
    }
    if row["brand_name"] or row["generic_name"]:
        return row
    return {}


def _iter_xml_payloads(raw: bytes) -> list[bytes]:
    if zipfile.is_zipfile(BytesIO(raw)):
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            return [archive.read(name) for name in archive.namelist() if name.lower().endswith(".xml")]
    return [raw]


def parse(raw: bytes) -> pd.DataFrame:
    rows: list[dict[str, str | None]] = []
    record_tags = {"iyakuhin", "drug", "record", "item", "medicine"}

    for payload in _iter_xml_payloads(raw):
        context = etree.iterparse(BytesIO(payload), events=("end",), recover=True, huge_tree=True)
        for _, element in context:
            if _local_name(element.tag) not in record_tags:
                continue
            row = _parse_drug_element(element)
            if row:
                rows.append(row)
            element.clear()
            parent = element.getparent()
            while parent is not None and element.getprevious() is not None:
                del parent[0]

    columns = [
        "yj_code",
        "brand_name",
        "brand_name_kana",
        "generic_name",
        "generic_kana",
        "dosage_form",
        "strength",
        "manufacturer",
        "approval_no",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).drop_duplicates().reset_index(drop=True)


def run() -> pd.DataFrame:
    """Return columns: yj_code, brand_name, brand_name_kana, generic_name, generic_kana, dosage_form, strength, manufacturer, approval_no."""
    return parse(fetch())


if __name__ == "__main__":
    print(len(run()))
