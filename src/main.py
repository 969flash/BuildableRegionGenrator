"""Grasshopper entry module.

현재 단계에서는 '정북/정남 사선(북측/남측 일조 사선) 베이스 커브/세그먼트' 계산만
`src/northsky.py`로 정리해서 노출합니다.

GH Inputs (권장):
- target_lot_region: geo.Curve
- other_lot_regions: List[geo.Curve]
- vec_exposure: geo.Vector3d (기본: (0,1,0))
- max_distance: float (기본: 20.0)
- is_center_start: bool (기본: True)
- excluded_lot_regions: Optional[List[geo.Curve]]

GH Outputs (권장):
- northsky_base_crvs: List[northsky.BaseCrv]
- northsky_base_segments: List[geo.Curve]
- northsky_buildable_boundary: Optional[geo.Curve]
"""

try:
    from typing import List, Optional
except ImportError:
    pass

import Rhino.Geometry as geo  # type: ignore

try:
    from . import northsky  # type: ignore
except Exception:
    import northsky  # type: ignore

import importlib


importlib.reload(northsky)


def compute_northsky_base_crvs(
    lot_region,
    neighbor_lot_regions,
    vec_exposure,
    max_distance,
    is_center_start,
    excluded_lot_regions=None,
):
    # type: (geo.Curve, List[geo.Curve], geo.Vector3d, float, bool, Optional[List[geo.Curve]]) -> List[northsky.BaseCrv]
    """GH에서 바로 호출 가능한 정북/정남 베이스 커브(BaseCrv) 계산."""
    calc = northsky.NorthSkyBaseCurveCalculator(
        vec_exposure=vec_exposure,
        max_distance=float(max_distance),
        is_center_start=bool(is_center_start),
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
    calc = northsky.NorthSkyBaseCurveCalculator(
        vec_exposure=vec_exposure,
        max_distance=float(max_distance),
        is_center_start=bool(is_center_start),
        excluded_lot_crvs=excluded_lot_regions,
    )
    return calc.compute_base_segments(lot_region, neighbor_lot_regions)


def compute_northsky_buildable_boundary(
    lot_region,
    neighbor_lot_regions,
    vec_exposure,
    max_distance,
    is_center_start,
    height,
    ratio,
    base_offset=0.0,
    base_height=0.0,
    excluded_lot_regions=None,
):
    # type: (geo.Curve, List[geo.Curve], geo.Vector3d, float, bool, float, float, float, float, Optional[List[geo.Curve]]) -> Optional[geo.Curve]
    """GH에서 바로 호출 가능한 높이별 정북/정남 사선 건축가능영역 계산."""
    return northsky.compute_northsky_buildable_boundary(
        lot_region=lot_region,
        vec_exposure=vec_exposure,
        max_distance=float(max_distance),
        neighbor_lot_crvs_without_gong=neighbor_lot_regions,
        is_center_start=bool(is_center_start),
        height=float(height),
        ratio=float(ratio),
        base_offset=float(base_offset),
        base_height=float(base_height),
        excluded_lot_crvs=excluded_lot_regions,
    )


if __name__ == "__main__":
    # GH에서 스크립트로 실행될 때: globals() 입력을 읽어서 outputs 변수에 채워준다.
    target_lot_region = globals().get("target_lot_region")
    other_lot_regions = globals().get("other_lot_regions")

    vec_exposure = globals().get("vec_exposure") or geo.Vector3d(0, 1, 0)
    max_distance = globals().get("max_distance", 20.0)
    is_center_start = globals().get("is_center_start", True)
    excluded_lot_regions = globals().get("excluded_lot_regions")
    height = globals().get("height", 15.0)
    ratio = globals().get("ratio", 1.5)
    base_offset = globals().get("base_offset", 0.0)
    base_height = globals().get("base_height", 0.0)

    northsky_base_crvs = None
    northsky_base_segments = None
    northsky_buildable_boundary = None
    if target_lot_region and other_lot_regions:
        northsky_base_crvs = compute_northsky_base_crvs(
            target_lot_region,
            other_lot_regions,
            vec_exposure,
            max_distance,
            is_center_start,
            excluded_lot_regions,
        )
        northsky_buildable_boundary = compute_northsky_buildable_boundary(
            target_lot_region,
            other_lot_regions,
            vec_exposure,
            max_distance,
            is_center_start,
            height,
            ratio,
            base_offset,
            base_height,
            excluded_lot_regions,
        )
        northsky_base_segments = compute_northsky_base_segments(
            target_lot_region,
            other_lot_regions,
            vec_exposure,
            max_distance,
            is_center_start,
            excluded_lot_regions,
        )
