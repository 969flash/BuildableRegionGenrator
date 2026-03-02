"""Grasshopper entry module.

현재 단계에서는 `NorthSkyCalculator` 객체를 생성하고
`compute()`를 호출해 결과를 멤버 변수로 받는 방식으로 사용합니다.

GH Inputs (권장):
- target_lot_region: geo.Curve
- other_lot_regions: List[geo.Curve]
- vec_exposure: geo.Vector3d (기본: (0,1,0))
- max_distance: float (기본: 20.0)
- is_center_start: bool (기본: True)
- excluded_lot_regions: Optional[List[geo.Curve]]

GH Outputs (권장):
- northsky_base_segments: List[geo.Curve]
- northsky_buildable_boundary: Optional[geo.Curve]
- northsky_calculator: northsky.NorthSkyCalculator
"""

import Rhino.Geometry as geo  # type: ignore

try:
    from . import northsky  # type: ignore
except Exception:
    import northsky  # type: ignore

import importlib


importlib.reload(northsky)


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

    if not target_lot_region or not other_lot_regions:
        raise ValueError("target_lot_region and other_lot_regions are required inputs.")

    northsky_base_segments = None
    northsky_buildable_boundary = None
    northsky_calculator = None

    northsky_calculator = northsky.NorthSkyCalculator(
        vec_exposure=vec_exposure,
        max_distance=float(max_distance),
        is_center_start=bool(is_center_start),
        height=float(height),
        ratio=float(ratio),
        base_offset=float(base_offset),
        base_height=float(base_height),
        excluded_lot_crvs=excluded_lot_regions,
    )
    northsky_calculator.compute(
        lot_region=target_lot_region,
        neighbor_lot_crvs_without_gong=other_lot_regions,
    )
    northsky_base_segments = northsky_calculator.base_segments
    northsky_buildable_boundary = northsky_calculator.buildable_boundary
