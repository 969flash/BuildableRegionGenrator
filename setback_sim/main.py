"""Grasshopper entry module.

현재 단계에서는 `NorthSkyCalculator` 객체를 생성하고
`compute()`를 호출해 결과를 멤버 변수로 받는 방식으로 사용합니다.

GH Inputs (권장):
- target_lot: utils.Lot
- other_lots: List[utils.Lot]
- height: float (필수)
- type: int (1=기존, 2=10~17m 고정 5m)
- debug: bool (기본 True)

GH Outputs (권장):
- northsky_base_segments: List[geo.Curve]
- northsky_buildable_boundary: Optional[geo.Curve]
- northsky_cutter_breps: List[geo.Brep]
- northsky_calculator: northsky.NorthSkyCalculator
"""

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

    height = globals().get("height")
    setback_type = globals().get("setback_type")

    max_distance = constants.PREFILTER_DISTANCE_M
    ratio = constants.DEFAULT_RATIO

    if debug:
        target_pnu = ""
        if target_lot is not None:
            target_pnu = str(getattr(target_lot, "pnu", ""))
        other_count = 0 if other_lots is None else len(other_lots)
        print("[main] target_lot is None: {}".format(target_lot is None))
        print("[main] target_lot.pnu: {}".format(target_pnu))
        print("[main] other_lots count: {}".format(other_count))
        print(
            "[main] inputs: height={}, type={}, ratio={}, max_distance={}".format(
                height, setback_type, ratio, max_distance
            )
        )

    if target_lot is None:
        raise ValueError("target_lot is required.")
    if other_lots is None:
        raise ValueError("other_lots is required.")
    if height is None:
        raise ValueError("height is required.")
    if setback_type is None:
        raise ValueError("type is required.")

    northsky_base_segments = None
    northsky_buildable_boundary = None
    northsky_cutter_breps = None
    northsky_calculator = None

    northsky_calculator = northsky.create_calculator(
        target_lot=target_lot,
        neighbor_lots=other_lots,
        max_distance=max_distance,
        height=height,
        ratio=ratio,
    )
    northsky_calculator.compute(height=float(height), type=int(setback_type))
    northsky_base_segments = northsky_calculator.base_segments
    northsky_buildable_boundary = northsky_calculator.buildable_boundary
    northsky_cutter_breps = northsky_calculator.get_cutter_breps(
        setback_type=int(setback_type)
    )
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
        print("[main] cutter_breps count: {}".format(len(northsky_cutter_breps or [])))
        print("[main] offset_lot_region is None: {}".format(offset_lot_region is None))
