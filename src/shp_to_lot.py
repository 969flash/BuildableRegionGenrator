"""SHP -> Lot selection helpers.

`LotRepository`는 SHP를 1회 로드하고,
- target_lot 조회
- other_lots 조회(옵션: bbox 사전 필터)
를 제공한다.
"""

import os
from typing import List, Optional

import Rhino.Geometry as geo  # type: ignore

try:
    from . import utils, constants
except Exception:
    import utils
    import constants
import importlib

importlib.reload(utils)
importlib.reload(constants)


def print_lot_info(lot: utils.Lot):
    """필지 정보 출력"""
    print(f"PNU: {lot.pnu}")
    print(f"지목: {lot.jimok}")
    print(f"면적: {lot.area:.2f} ㎡")


class LotRepository(object):
    def __init__(self, shp_path):
        # type: (str) -> None
        if not shp_path or not os.path.isfile(shp_path):
            raise FileNotFoundError("SHP 파일을 찾을 수 없습니다: {}".format(shp_path))

        self.shp_path = shp_path
        shapes, records, fields = utils.read_shp_file(shp_path)
        parcels = utils.get_parcels_from_shapes(shapes, records, fields)
        self.lots, self.roads = utils.classify_parcels(parcels)
        self._bbox_cache = {}

    def get_target_lot(self, pnu):
        # type: (str) -> Optional[utils.Lot]
        if pnu is None:
            return None
        pnu_text = str(pnu)
        return next((lot for lot in self.lots if str(lot.pnu) == pnu_text), None)

    def _get_bbox(self, lot):
        # type: (utils.Lot) -> Optional[geo.BoundingBox]
        key = id(lot)
        cached = self._bbox_cache.get(key)
        if cached is not None:
            return cached

        region = getattr(lot, "region", None)
        if not region:
            self._bbox_cache[key] = None
            return None

        try:
            bb = region.GetBoundingBox(True)
        except Exception:
            bb = None

        if bb is None or (hasattr(bb, "IsValid") and not bb.IsValid):
            self._bbox_cache[key] = None
            return None

        self._bbox_cache[key] = bb
        return bb

    def is_bbox_overlapping(self, bb_a, bb_b):
        # type: (Optional[geo.BoundingBox], Optional[geo.BoundingBox]) -> bool
        if not bb_a or not bb_b:
            return False
        return not (
            bb_a.Max.X < bb_b.Min.X
            or bb_a.Min.X > bb_b.Max.X
            or bb_a.Max.Y < bb_b.Min.Y
            or bb_a.Min.Y > bb_b.Max.Y
        )

    def get_other_lots(self, target_lot):
        # type: (utils.Lot) -> List[utils.Lot]
        if target_lot is None:
            return []

        others = [lot for lot in self.lots if lot is not target_lot]

        bb_target = self._get_bbox(target_lot)
        if not bb_target:
            return others

        bb_query = geo.BoundingBox(bb_target.Min, bb_target.Max)
        dist = max(float(constants.PREFILTER_DISTANCE_M), 0.0)
        bb_query.Inflate(dist, dist, 0.0)

        return [
            lot
            for lot in others
            if self.is_bbox_overlapping(bb_query, self._get_bbox(lot))
        ]

    def get_target_and_others(self, pnu):
        # type: (str) -> tuple
        target_lot = self.get_target_lot(pnu)
        if target_lot is None:
            raise ValueError("PNU '{}'에 해당하는 필지를 찾을 수 없습니다.".format(pnu))
        other_lots = self.get_other_lots(target_lot)
        return target_lot, other_lots


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

    repo = LotRepository(shp_path)
    lots, roads = repo.lots, repo.roads
    # 데이터 확인
    print(f"대지: {len(lots)}개, 도로: {len(roads)}개")

    # 3. 입력된 PNU에 해당하는 필지 선택
    selected_lot = repo.get_target_lot(pnu)
    if not selected_lot:
        raise ValueError("PNU '{}'에 해당하는 필지를 찾을 수 없습니다.".format(pnu))
    print("선택된 PNU의 필지 정보")
    print_lot_info(selected_lot)

    target_lot = selected_lot
    other_lots = repo.get_other_lots(target_lot)
