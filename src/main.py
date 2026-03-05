"""Grasshopper entry module.

현재 단계에서는 `NorthSkyCalculator` 객체를 생성하고
`compute()`를 호출해 결과를 멤버 변수로 받는 방식으로 사용합니다.

GH Inputs (권장):
- target_lot: utils.Lot
- other_lots: List[utils.Lot]
- vec_exposure: geo.Vector3d (기본: (0,1,0))
- max_distance: float (기본: 20.0)

GH Outputs (권장):
- northsky_base_segments: List[geo.Curve]
- northsky_buildable_boundary: Optional[geo.Curve]
- northsky_calculator: northsky.NorthSkyCalculator
"""

import Rhino.Geometry as geo  # type: ignore

try:
    from . import northsky, constants  # type: ignore
except Exception:
    import constants  # type: ignore
    import northsky  # type: ignore

import importlib


importlib.reload(northsky)
importlib.reload(constants)


if __name__ == "__main__":
    # GH에서 스크립트로 실행될 때: globals() 입력을 읽어서 outputs 변수에 채워준다.
    debug = bool(globals().get("debug", True))

    target_lot = globals().get("target_lot")
    other_lots = globals().get("other_lots")

    vec_exposure = globals().get("vec_exposure") or geo.Vector3d(
        constants.DEFAULT_VEC_EXPOSURE_X,
        constants.DEFAULT_VEC_EXPOSURE_Y,
        constants.DEFAULT_VEC_EXPOSURE_Z,
    )
    max_distance = globals().get("max_distance", 20.0)
    height = globals().get("height", constants.DEFAULT_HEIGHT_M)
    ratio = globals().get("ratio", constants.DEFAULT_RATIO)

    if debug:
        target_pnu = ""
        if target_lot is not None:
            target_pnu = str(getattr(target_lot, "pnu", ""))
        other_count = 0 if other_lots is None else len(other_lots)
        print("[main] target_lot is None: {}".format(target_lot is None))
        print("[main] target_lot.pnu: {}".format(target_pnu))
        print("[main] other_lots count: {}".format(other_count))
        print(
            "[main] inputs: height={}, ratio={}, max_distance={}".format(
                height, ratio, max_distance
            )
        )

    if target_lot is None or other_lots is None:
        raise ValueError("target_lot and other_lots are required inputs.")

    northsky_base_segments = None
    northsky_buildable_boundary = None
    northsky_calculator = None

    northsky_calculator = northsky.create_calculator(
        target_lot=target_lot,
        neighbor_lots=other_lots,
        vec_exposure=vec_exposure,
        max_distance=max_distance,
        height=height,
        ratio=ratio,
    )
    northsky_calculator.compute(height=float(height))
    northsky_base_segments = northsky_calculator.base_segments
    northsky_buildable_boundary = northsky_calculator.buildable_boundary
    offset_lot_region = northsky_calculator.lot_region_inward

    if debug:
        print(
            "[main] base_segments count: {}".format(len(northsky_base_segments or []))
        )
        print(
            "[main] buildable_boundary is None: {}".format(
                northsky_buildable_boundary is None
            )
        )
        print("[main] offset_lot_region is None: {}".format(offset_lot_region is None))
