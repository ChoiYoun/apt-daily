from src.regions import (
    get_sido_list,
    get_sgg_list_by_sido,
    get_region_by_code,
    REGIONS
)

def test_regions_data_integrity():
    # 전국 200개 이상의 시군구 법정동 코드가 포함되어야 함
    assert len(REGIONS) >= 200
    
    # 시도 목록 확인
    sidos = get_sido_list()
    assert "서울특별시" in sidos
    assert "경기도" in sidos
    assert "부산광역시" in sidos
    assert "제주특별자치도" in sidos
    
    # 서울특별시 내 시군구 확인
    seoul_sggs = get_sgg_list_by_sido("서울특별시")
    assert any(r["sgg"] == "강남구" and r["code"] == "11680" for r in seoul_sggs)
    assert any(r["sgg"] == "서초구" and r["code"] == "11650" for r in seoul_sggs)
    assert any(r["sgg"] == "종로구" and r["code"] == "11110" for r in seoul_sggs)
    
    # 코드로 지역 조회 확인
    region = get_region_by_code("11110")
    assert region is not None
    assert region["sgg"] == "종로구"
    assert region["sido"] == "서울특별시"

    # 존재하지 않는 코드
    assert get_region_by_code("99999") is None
