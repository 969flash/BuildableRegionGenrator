"""Batch processor: SHP directory -> NorthSky allowable area CSV.

Inputs (GH globals or CLI arg):
- shp_dir: SHP 파일이 들어있는 디렉토리 경로

동작:
1) 디렉토리에서 .shp 파일 탐색
2) 필지를 읽어 Lot/Road 분류
3) 제1/2/3종 일반주거지역(A13: 13,14,15) Lot만 대상
4) 1~7층(층고 3m) 기준으로 각 층 허용 바운더리 면적 계산
5) result 폴더에 CSV 저장
"""

import csv
import datetime
import importlib
import os
import sys
from collections import Counter

import Rhino.Geometry as geo  # type: ignore

try:
    from . import constants, northsky, utils, shp_to_lot  # type: ignore
except Exception:
    import constants  # type: ignore
    import northsky  # type: ignore
    import utils  # type: ignore
    import shp_to_lot  # type: ignore

importlib.reload(constants)
importlib.reload(utils)
importlib.reload(northsky)
importlib.reload(shp_to_lot)


RESIDENTIAL_GENERAL_CODES = {"13", "14", "15"}
FLOOR_HEIGHT_M = 3.0
MAX_FLOOR = 7

# NorthSky 계산 기본값
DEFAULT_VEC_EXPOSURE = geo.Vector3d(0, 1, 0)
DEFAULT_IS_CENTER_START = True
DEFAULT_RATIO = 1.5


def _normalize_landuse_code(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _resolve_shp_path(shp_dir):
    """입력 디렉토리(또는 shp 파일 경로)에서 대상 shp 파일 1개를 결정한다."""
    if not shp_dir:
        raise ValueError("shp_dir 입력이 필요합니다.")

    candidate = os.path.abspath(shp_dir)
    if os.path.isfile(candidate) and candidate.lower().endswith(".shp"):
        return candidate

    if not os.path.isdir(candidate):
        raise FileNotFoundError("유효한 SHP 디렉토리가 아닙니다: {}".format(shp_dir))

    shp_files = sorted(
        [
            os.path.join(candidate, name)
            for name in os.listdir(candidate)
            if name.lower().endswith(".shp")
        ]
    )
    if not shp_files:
        raise FileNotFoundError(
            "디렉토리에서 .shp 파일을 찾지 못했습니다: {}".format(candidate)
        )

    return shp_files[0]


def _compute_allowable_rows(shp_path, include_counter=False):
    """대상 SHP에 대해 층별 허용면적 테이블(row dict 리스트) 생성."""
    repo = shp_to_lot.LotRepository(shp_path)
    lots, roads = repo.lots, repo.roads

    landuse_counter = Counter(
        _normalize_landuse_code(getattr(lot, "landuse_code", "")) for lot in lots
    )

    target_lots = [
        lot
        for lot in lots
        if _normalize_landuse_code(getattr(lot, "landuse_code", ""))
        in RESIDENTIAL_GENERAL_CODES
    ]

    rows = []
    total_height = FLOOR_HEIGHT_M * MAX_FLOOR
    warning_pnus = set()
    road20m_rows = []
    centerline_rows = []

    for lot in target_lots:
        other_lots = repo.get_other_lots(lot)

        try:
            calc = northsky.NorthSkyCalculator(
                target_lot=lot,
                neighbor_lots=other_lots,
                vec_exposure=DEFAULT_VEC_EXPOSURE,
                max_distance=total_height,
                is_center_start=DEFAULT_IS_CENTER_START,
                height=FLOOR_HEIGHT_M,
                ratio=DEFAULT_RATIO,
            )
        except Exception:
            warning_pnus.add(str(getattr(lot, "pnu", "")))
            continue

        if getattr(calc, "qa_has_road20m_exclusion", False):
            owner_pnus = sorted(getattr(calc, "qa_road20m_exclusion_owner_pnus", set()))
            if owner_pnus:
                for owner_pnu in owner_pnus:
                    road20m_rows.append(
                        {
                            "target_pnu": str(getattr(lot, "pnu", "")),
                            "owner_pnu": owner_pnu,
                        }
                    )
            else:
                road20m_rows.append(
                    {
                        "target_pnu": str(getattr(lot, "pnu", "")),
                        "owner_pnu": "",
                    }
                )

        if getattr(calc, "qa_has_apartment_centerline", False):
            owner_pnus = sorted(
                getattr(calc, "qa_apartment_centerline_owner_pnus", set())
            )
            if owner_pnus:
                for owner_pnu in owner_pnus:
                    centerline_rows.append(
                        {
                            "target_pnu": str(getattr(lot, "pnu", "")),
                            "owner_pnu": owner_pnu,
                        }
                    )
            else:
                centerline_rows.append(
                    {
                        "target_pnu": str(getattr(lot, "pnu", "")),
                        "owner_pnu": "",
                    }
                )

        lot_region_inward = calc.lot_region_inward
        lot_region_inward_area = (
            0.0 if lot_region_inward is None else utils.get_area(lot_region_inward)
        )
        if lot_region_inward is None:
            warning_pnus.add(str(getattr(lot, "pnu", "")))
            # 너무 작은경우 뒤의 연산도 의미 없으므로 허용면적 0으로 처리
            lot_region_inward = None

            rows.append(
                {
                    "pnu": lot.pnu,
                    "jimok": lot.jimok,
                    "landuse_code": getattr(lot, "landuse_code", ""),
                    "landuse": getattr(lot, "landuse", constants.LANDUSE_UNKNOWN),
                    "lot_area_m2": lot.area,
                    "lot_area_inward_1m_m2": lot_region_inward_area,
                    "floor": 0,
                    "height_m": 0.0,
                    "allowed_area_m2": 0.0,
                    "base_segment_count": 0,
                }
            )
            continue

        for floor in range(1, MAX_FLOOR + 1):
            height_m = FLOOR_HEIGHT_M * floor
            try:
                calc.compute(height=height_m)
            except Exception:
                warning_pnus.add(str(getattr(lot, "pnu", "")))
                break

            buildable = calc.buildable_boundary
            allowed_area = 0.0 if not buildable else utils.get_area(buildable)

            rows.append(
                {
                    "pnu": lot.pnu,
                    "jimok": lot.jimok,
                    "landuse_code": getattr(lot, "landuse_code", ""),
                    "landuse": getattr(lot, "landuse", constants.LANDUSE_UNKNOWN),
                    "lot_area_m2": lot.area,
                    "lot_area_inward_1m_m2": lot_region_inward_area,
                    "floor": floor,
                    "height_m": height_m,
                    "allowed_area_m2": allowed_area,
                    "base_segment_count": len(calc.base_segments or []),
                }
            )

    qa_data = {
        "warning_pnus": sorted([p for p in warning_pnus if p]),
        "road20m_rows": road20m_rows,
        "centerline_rows": centerline_rows,
    }

    if include_counter:
        return rows, len(lots), len(roads), len(target_lots), landuse_counter, qa_data
    return rows, len(lots), len(roads), len(target_lots), qa_data


def _save_qa_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _save_qa_reports(shp_path, qa_data):
    base_dir = os.path.dirname(os.path.abspath(shp_path))
    qa_dir = os.path.join(base_dir, "qa")
    if not os.path.isdir(qa_dir):
        os.makedirs(qa_dir)

    stem = os.path.splitext(os.path.basename(shp_path))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    warning_path = os.path.join(
        qa_dir, "{}_qa_warning_pnu_{}.csv".format(stem, timestamp)
    )
    road20m_path = os.path.join(
        qa_dir, "{}_qa_road20m_exclusion_{}.csv".format(stem, timestamp)
    )
    centerline_path = os.path.join(
        qa_dir, "{}_qa_apartment_centerline_{}.csv".format(stem, timestamp)
    )

    warning_rows = [{"pnu": p} for p in qa_data.get("warning_pnus", [])]
    _save_qa_csv(warning_path, ["pnu"], warning_rows)
    _save_qa_csv(
        road20m_path,
        ["target_pnu", "owner_pnu"],
        qa_data.get("road20m_rows", []),
    )
    _save_qa_csv(
        centerline_path,
        ["target_pnu", "owner_pnu"],
        qa_data.get("centerline_rows", []),
    )

    return {
        "warning_path": warning_path,
        "road20m_path": road20m_path,
        "centerline_path": centerline_path,
    }


def _save_csv(rows, shp_path):
    """result 폴더에 CSV 저장 후 경로 반환."""
    base_dir = os.path.dirname(os.path.abspath(shp_path))
    result_dir = os.path.join(base_dir, "result")
    if not os.path.isdir(result_dir):
        os.makedirs(result_dir)

    stem = os.path.splitext(os.path.basename(shp_path))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(
        result_dir, "{}_northsky_allowed_area_{}.csv".format(stem, timestamp)
    )

    headers = [
        "pnu",
        "jimok",
        "landuse_code",
        "landuse",
        "lot_area_m2",
        "lot_area_inward_1m_m2",
        "floor",
        "height_m",
        "allowed_area_m2",
        "base_segment_count",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return csv_path


if __name__ == "__main__":
    shp_dir = globals().get("shp_dir")
    if not shp_dir and len(sys.argv) > 1:
        shp_dir = sys.argv[1]

    shp_path = _resolve_shp_path(shp_dir)
    rows, lot_count, road_count, target_count, landuse_counter, qa_data = (
        _compute_allowable_rows(shp_path, include_counter=True)
    )
    output_csv_path = _save_csv(rows, shp_path)
    qa_paths = _save_qa_reports(shp_path, qa_data)

    print("SHP: {}".format(shp_path))
    print("전체 대지 수: {}, 도로 수: {}".format(lot_count, road_count))
    print("대지 landuse_code 상위 분포: {}".format(landuse_counter.most_common(10)))
    print("대상(일반주거 13/14/15) 대지 수: {}".format(target_count))
    print("저장 완료: {}".format(output_csv_path))
    print("QA 저장 완료: {}".format(qa_paths.get("warning_path")))
    print("QA 저장 완료: {}".format(qa_paths.get("road20m_path")))
    print("QA 저장 완료: {}".format(qa_paths.get("centerline_path")))
