# -*- coding: utf-8 -*-
"""Entry points for Grasshopper.

이 파일은 GH에서 import해서 바로 호출하기 위한 얇은 래퍼다.

예) 두 번째 컴포넌트(GhPython):

import Rhino.Geometry as geo
from shp_manager import ShpManager
from northsky import NorthSkyBaseCurveCalculator

# lots: 첫 번째 컴포넌트에서 전달받은 lots(list)
lot_region, neighbor_lot_regions = ShpManager.pick_lot_and_neighbors(lots, target_pnu)

calc = NorthSkyBaseCurveCalculator(
    vec_exposure=geo.Vector3d(0, 1, 0),
    max_distance=20.0,
    is_center_start=True,
)
base_segments = calc.compute_base_segments(lot_region, neighbor_lot_regions)

"""

try:
    from typing import List, Optional
except ImportError:
    pass

import Rhino.Geometry as geo  # type: ignore

from northsky import NorthSkyBaseCurveCalculator, BaseCrv


def compute_northsky_base_crvs(
    lot_region,
    neighbor_lot_regions,
    vec_exposure,
    max_distance,
    is_center_start,
    excluded_lot_regions=None,
):
    # type: (geo.Curve, List[geo.Curve], geo.Vector3d, float, bool, Optional[List[geo.Curve]]) -> List[BaseCrv]
    """GH에서 바로 호출 가능한 정북/정남 베이스 커브 계산."""
    calc = NorthSkyBaseCurveCalculator(
        vec_exposure=vec_exposure,
        max_distance=max_distance,
        is_center_start=is_center_start,
        excluded_lot_crvs=excluded_lot_regions,
    )
    return calc.compute_base_crvs(lot_region, neighbor_lot_regions)


def compute_northsky_base_segments(
    lot_region,
    neighbor_lot_regions,
    vec_exposure,
    max_distance,
    is_center_start,
    excluded_lot_regions=None,
):
    # type: (geo.Curve, List[geo.Curve], geo.Vector3d, float, bool, Optional[List[geo.Curve]]) -> List[geo.Curve]
    """GH에서 바로 호출 가능한 정북/정남 베이스 segment 계산."""
    calc = NorthSkyBaseCurveCalculator(
        vec_exposure=vec_exposure,
        max_distance=max_distance,
        is_center_start=is_center_start,
        excluded_lot_crvs=excluded_lot_regions,
    )
    return calc.compute_base_segments(lot_region, neighbor_lot_regions)
