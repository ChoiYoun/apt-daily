"""국토교통부 아파트 매매 및 전월세 OpenAPI XML 응답 파서 모듈"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional


def _get_text(element: ET.Element, tag: str, default: Optional[str] = None) -> Optional[str]:
    """XML 엘리먼트 내 특정 태그의 텍스트를 안전하게 추출하고 공백을 제거"""
    found = element.find(tag)
    if found is not None and found.text is not None:
        val = found.text.strip()
        return val if val else default
    return default


def parse_trade_xml(xml_content: str, region_info: Dict[str, str]) -> List[Dict]:
    """아파트 매매 실거래가 XML 응답을 파싱하여 딕셔너리 리스트로 반환"""
    if not xml_content or "<items>" not in xml_content:
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    results = []
    items = root.findall(".//item")
    for item in items:
        apt_name = _get_text(item, "aptNm")
        if not apt_name:
            continue

        raw_amount = _get_text(item, "dealAmount", "0").replace(",", "")
        try:
            deal_amount = int(raw_amount)
        except ValueError:
            deal_amount = 0

        year = int(_get_text(item, "dealYear", "0"))
        month = int(_get_text(item, "dealMonth", "0"))
        day = int(_get_text(item, "dealDay", "0"))
        deal_date = f"{year:04d}-{month:02d}-{day:02d}"

        try:
            exclusive_area = float(_get_text(item, "excluUseAr", "0.0"))
        except ValueError:
            exclusive_area = 0.0

        pyeong = round(exclusive_area / 3.30578, 2)
        price_per_pyeong = int(round(deal_amount / pyeong)) if pyeong > 0 else 0

        floor_str = _get_text(item, "floor")
        floor = int(floor_str) if floor_str and floor_str.lstrip("-").isdigit() else None

        build_year_str = _get_text(item, "buildYear")
        build_year = int(build_year_str) if build_year_str and build_year_str.isdigit() else None

        results.append({
            "deal_date": deal_date,
            "sido": region_info["sido"],
            "sgg": region_info["sgg"],
            "sgg_cd": _get_text(item, "sggCd", region_info["code"]),
            "umd": _get_text(item, "umdNm", ""),
            "apt_name": apt_name,
            "deal_amount": deal_amount,
            "exclusive_area": exclusive_area,
            "pyeong": pyeong,
            "price_per_pyeong": price_per_pyeong,
            "floor": floor,
            "build_year": build_year,
            "buyer_gbn": _get_text(item, "buyerGbn"),
            "dealing_gbn": _get_text(item, "dealingGbn"),
        })

    return results


def parse_rent_xml(xml_content: str, region_info: Dict[str, str]) -> List[Dict]:
    """아파트 전월세 실거래가 XML 응답을 파싱하여 딕셔너리 리스트로 반환"""
    if not xml_content or "<items>" not in xml_content:
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return []

    results = []
    items = root.findall(".//item")
    for item in items:
        apt_name = _get_text(item, "aptNm")
        if not apt_name:
            continue

        raw_deposit = _get_text(item, "deposit", "0").replace(",", "")
        try:
            deposit = int(raw_deposit)
        except ValueError:
            deposit = 0

        raw_rent = _get_text(item, "monthlyRent", "0").replace(",", "")
        try:
            monthly_rent = int(raw_rent)
        except ValueError:
            monthly_rent = 0

        rent_type = "전세" if monthly_rent == 0 else "월세"

        year = int(_get_text(item, "dealYear", "0"))
        month = int(_get_text(item, "dealMonth", "0"))
        day = int(_get_text(item, "dealDay", "0"))
        deal_date = f"{year:04d}-{month:02d}-{day:02d}"

        try:
            exclusive_area = float(_get_text(item, "excluUseAr", "0.0"))
        except ValueError:
            exclusive_area = 0.0

        pyeong = round(exclusive_area / 3.30578, 2)

        floor_str = _get_text(item, "floor")
        floor = int(floor_str) if floor_str and floor_str.lstrip("-").isdigit() else None

        build_year_str = _get_text(item, "buildYear")
        build_year = int(build_year_str) if build_year_str and build_year_str.isdigit() else None

        results.append({
            "deal_date": deal_date,
            "sido": region_info["sido"],
            "sgg": region_info["sgg"],
            "sgg_cd": _get_text(item, "sggCd", region_info["code"]),
            "umd": _get_text(item, "umdNm", ""),
            "apt_name": apt_name,
            "deposit": deposit,
            "monthly_rent": monthly_rent,
            "rent_type": rent_type,
            "exclusive_area": exclusive_area,
            "pyeong": pyeong,
            "floor": floor,
            "build_year": build_year,
            "contract_type": _get_text(item, "contractType"),
        })

    return results
