# r: pyshp
"""
가로구역별 최고높이 산정을 위한 필지 필터링 스크립트
Inputs:
    shp_path: str : SHP 파일 경로
    pnu: str : 필지 PNU 코드
Outputs:
    target_lot_region: geo.Region : 선택된 PNU의 대지 영역
    other_lot_regions: List[geo.Region] : 타 필지들의 대지 영역 리스트

1. SHP 파일에서 필지 데이터 읽기
2. 필지 데이터를 대지(Lot)와 도로(Road)로 분류
3. 입력된 PNU에 해당하는 필지와 타 필지 출력
"""

import Rhino.Geometry as geo
import scriptcontext as sc
import shapefile
import os
from typing import List, Tuple, Any, Optional

try:
    from . import utils
except Exception:
    import utils
import importlib

importlib.reload(utils)


def print_lot_info(lot: utils.Lot):
    """필지 정보 출력"""
    print(f"PNU: {lot.pnu}")
    print(f"지목: {lot.jimok}")
    print(f"면적: {lot.area:.2f} ㎡")


if __name__ == "__main__":
    ### 메인 실행 코드 ###
    # 인풋 값 설정
    # 파일 경로 읽기
    shp_path = globals().get("shp_path", None)
    if not shp_path or not os.path.isfile(shp_path):
        raise FileNotFoundError(f"SHP 파일을 찾을 수 없습니다: {shp_path}")
    # PNU 읽기
    pnu = globals().get("pnu", None)
    if not pnu:
        raise ValueError("PNU 값이 제공되지 않았습니다.")

    # 1. SHP 파일에서 필지 데이터 읽기
    # Shape, Record, Field 데이터 읽기
    shapes, records, fields = utils.read_shp_file(shp_path)

    # 2. 필지 데이터에서 lot과 road 분류
    # 필지 데이터로부터 Parcel 객체 생성
    parcels = utils.get_parcels_from_shapes(shapes, records, fields)
    # 대지와 도로 분류
    lots, roads = utils.classify_parcels(parcels)
    # 데이터 확인
    print(f"대지: {len(lots)}개, 도로: {len(roads)}개")

    # 3. 입력된 PNU에 해당하는 필지 선택
    selected_lot = next((lot for lot in lots if lot.pnu == pnu), None)
    if not selected_lot:
        raise ValueError(f"PNU '{pnu}'에 해당하는 필지를 찾을 수 없습니다.")
    print("선택된 PNU의 필지 정보")
    print_lot_info(selected_lot)

    target_lot_region = selected_lot.region
    other_lot_regions = [lot.region for lot in lots if lot.pnu != selected_lot.pnu]
