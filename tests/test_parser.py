import pytest
from src.parser import parse_trade_xml, parse_rent_xml

SAMPLE_TRADE_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<response>
  <header>
    <resultCode>000</resultCode>
    <resultMsg>OK</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <aptDong>101</aptDong>
        <aptNm>현대아파트</aptNm>
        <buildYear>2010</buildYear>
        <buyerGbn>개인</buyerGbn>
        <dealAmount> 125,000 </dealAmount>
        <dealDay>25</dealDay>
        <dealMonth>9</dealMonth>
        <dealYear>2026</dealYear>
        <dealingGbn>중개거래</dealingGbn>
        <excluUseAr>84.95</excluUseAr>
        <floor>15</floor>
        <sggCd>11110</sggCd>
        <umdNm>청운동</umdNm>
      </item>
    </items>
  </body>
</response>"""

SAMPLE_RENT_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<response>
  <header>
    <resultCode>000</resultCode>
    <resultMsg>OK</resultMsg>
  </header>
  <body>
    <items>
      <item>
        <aptNm>래미안원베일리</aptNm>
        <buildYear>2023</buildYear>
        <contractType>신규</contractType>
        <dealDay>26</dealDay>
        <dealMonth>9</dealMonth>
        <dealYear>2026</dealYear>
        <deposit> 150,000 </deposit>
        <monthlyRent> 0 </monthlyRent>
        <excluUseAr>84.9</excluUseAr>
        <floor>12</floor>
        <sggCd>11650</sggCd>
        <umdNm>반포동</umdNm>
      </item>
      <item>
        <aptNm>아크로리버파크</aptNm>
        <buildYear>2016</buildYear>
        <contractType>갱신</contractType>
        <dealDay>27</dealDay>
        <dealMonth>9</dealMonth>
        <dealYear>2026</dealYear>
        <deposit> 20,000 </deposit>
        <monthlyRent> 350 </monthlyRent>
        <excluUseAr>59.95</excluUseAr>
        <floor>7</floor>
        <sggCd>11650</sggCd>
        <umdNm>반포동</umdNm>
      </item>
    </items>
  </body>
</response>"""

EMPTY_XML = """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<response>
  <header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
  <body><items/></body>
</response>"""


def test_parse_trade_xml():
    region = {"sido": "서울특별시", "sgg": "종로구", "code": "11110"}
    trades = parse_trade_xml(SAMPLE_TRADE_XML, region)
    assert len(trades) == 1
    t = trades[0]
    assert t["deal_date"] == "2026-09-25"
    assert t["deal_amount"] == 125000
    assert t["apt_name"] == "현대아파트"
    assert t["floor"] == 15
    assert t["exclusive_area"] == 84.95
    assert round(t["pyeong"], 1) == 25.7
    assert t["price_per_pyeong"] > 0
    assert t["sido"] == "서울특별시"
    assert t["sgg"] == "종로구"
    assert t["umd"] == "청운동"


def test_parse_rent_xml():
    region = {"sido": "서울특별시", "sgg": "서초구", "code": "11650"}
    rents = parse_rent_xml(SAMPLE_RENT_XML, region)
    assert len(rents) == 2

    # 전세 항목
    r1 = rents[0]
    assert r1["rent_type"] == "전세"
    assert r1["deposit"] == 150000
    assert r1["monthly_rent"] == 0
    assert r1["deal_date"] == "2026-09-26"

    # 월세 항목
    r2 = rents[1]
    assert r2["rent_type"] == "월세"
    assert r2["deposit"] == 20000
    assert r2["monthly_rent"] == 350
    assert r2["deal_date"] == "2026-09-27"


def test_parse_empty_xml():
    region = {"sido": "서울특별시", "sgg": "종로구", "code": "11110"}
    assert parse_trade_xml(EMPTY_XML, region) == []
    assert parse_rent_xml(EMPTY_XML, region) == []
