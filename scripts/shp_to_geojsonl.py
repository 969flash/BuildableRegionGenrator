"""GH 출력 buildable SHP들을 Tippecanoe용 GeoJSONL로 변환.

- 좌표계: EPSG:5179 (Korea TM) -> EPSG:4326 (WGS84)
- type1, type2 모두 포함, 단일 layer (type 속성으로 구분)
- 동일 구의 여러 timestamp가 있으면 최신만 사용

사용:
  # 강남 결과
  python3 scripts/shp_to_geojsonl.py data/_gangnam/result_geom/

  # 서울 전체 결과
  python3 scripts/shp_to_geojsonl.py data/_seoul_apt/result_geom/

출력: 같은 폴더에 buildable_all.geojsonl 생성
"""

import os
import sys
import json
import re
import time
from collections import defaultdict

import geopandas as gpd
import pandas as pd


FILENAME_PATTERN = re.compile(
    r"^(.+?)_buildable_type([12])_[AB]_(\d{8}_\d{6})\.shp$"
)

# 출력 GeoJSONL에 포함할 properties (Tippecanoe가 MVT로 그대로 인코딩)
PROPS = ["pnu", "floor_from", "floor_to", "type",
         "h_base_m", "h_top_m", "zone_cd", "area_m2", "seg_cnt", "district"]


def _ts():
    return time.strftime("%H:%M:%S")


def _select_latest_shps(folder):
    """{(district_stem, type_int): latest_filename} 반환."""
    groups = defaultdict(list)
    for fn in os.listdir(folder):
        m = FILENAME_PATTERN.match(fn)
        if not m:
            continue
        stem, type_str, ts = m.groups()
        groups[(stem, int(type_str))].append((ts, fn))
    latest = {}
    for key, lst in groups.items():
        lst.sort(reverse=True)
        latest[key] = lst[0][1]
    return latest


def _extract_district_code(stem):
    """파일 stem에서 시군구 코드 추출.

    예) 'AL_D194_11680_20260520_with_apt' -> '11680'
        'Gangnam' -> '강남' (fallback: stem 자체)
    """
    m = re.search(r"AL_D\d+_(\d{5})_", stem)
    if m:
        return m.group(1)
    return stem


def convert(folder, out_path=None):
    if not os.path.isdir(folder):
        raise FileNotFoundError(folder)
    if out_path is None:
        out_path = os.path.join(folder, "buildable_all.geojsonl")

    latest = _select_latest_shps(folder)
    if not latest:
        print(f"[{_ts()}] [ERROR] buildable SHP 없음: {folder}")
        return None

    # 구별 + type별 그룹 (district_stem 단위로 묶어서 진행 표시)
    districts = defaultdict(dict)  # stem -> {type: filename}
    for (stem, t), fn in latest.items():
        districts[stem][t] = fn

    n_dist = len(districts)
    print(f"[{_ts()}] === 변환 시작: {n_dist}개 구, 총 {len(latest)}개 SHP ===")
    print(f"[{_ts()}] 출력: {out_path}")

    total_features = 0
    type_counts = {1: 0, 2: 0}
    t0 = time.time()

    with open(out_path, "w", encoding="utf-8") as f_out:
        for i, (stem, type_map) in enumerate(sorted(districts.items()), 1):
            district_code = _extract_district_code(stem)
            for t in sorted(type_map.keys()):
                shp_path = os.path.join(folder, type_map[t])
                gdf = gpd.read_file(shp_path, encoding="utf-8")

                # EPSG:5179 -> 4326
                if gdf.crs is None:
                    gdf.set_crs(epsg=5179, inplace=True)
                gdf = gdf.to_crs(epsg=4326)

                # district 속성 추가
                gdf["district"] = district_code

                # GeoJSONL로 한 줄씩
                # NOTE: gdf.to_json()은 단일 FeatureCollection이라 GeoJSONL이 아님
                # iterrows + 직접 dump
                n_before_total = total_features
                for _, row in gdf.iterrows():
                    geom = row.geometry
                    if geom is None or geom.is_empty:
                        continue
                    feature = {
                        "type": "Feature",
                        "geometry": geom.__geo_interface__,
                        "properties": {
                            k: (row[k] if k in row and pd.notna(row[k]) else None)
                            for k in PROPS
                            if k in row.index
                        },
                    }
                    # numpy 타입 -> Python 기본 타입 (JSON serializable)
                    for k, v in list(feature["properties"].items()):
                        if v is None:
                            continue
                        if isinstance(v, (int,)):
                            feature["properties"][k] = int(v)
                        elif isinstance(v, float):
                            feature["properties"][k] = float(v)
                        else:
                            feature["properties"][k] = str(v)
                    f_out.write(json.dumps(feature, ensure_ascii=False))
                    f_out.write("\n")
                    total_features += 1
                    type_counts[t] = type_counts.get(t, 0) + 1
                added = total_features - n_before_total
                print(f"[{_ts()}]   ({i}/{n_dist}) {stem[:40]:<40} type{t}: {added:,}")

    elapsed = time.time() - t0
    fsize = os.path.getsize(out_path) / (1024 * 1024)
    print()
    print(f"[{_ts()}] === 완료 ===")
    print(f"  총 features: {total_features:,}")
    print(f"  type 1: {type_counts.get(1, 0):,}")
    print(f"  type 2: {type_counts.get(2, 0):,}")
    print(f"  소요: {elapsed:.1f}s")
    print(f"  파일 크기: {fsize:.1f} MB  ({out_path})")
    return out_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    folder = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) >= 3 else None
    convert(folder, out)


if __name__ == "__main__":
    main()
