"""Project-level constants.

Core geometry constants:
- TOL: 연산 허용 오차
- RAW_TOL: 원시 데이터 허용 오차
- ANGLE_90_DEGREE: 90도(rad)

LANDUSE_MAP:
- DBF field `A13` (용도지역 코드) -> 한글 명칭
- 코드가 없거나 해석 불가하면 "미확인" 사용
"""

import math

# 지오메트리 연산 허용오차(모델 단위)
TOL = 0.001
# 원시 SHP 데이터 보정/판단에 쓰는 완화 오차
RAW_TOL = 0.1
# 90도 회전에 사용하는 라디안 값
ANGLE_90_DEGREE = math.pi / 2.0
# 이웃 필지 1차 bbox 프리필터 거리(m)
PREFILTER_DISTANCE_M = 300.0

# 일반주거지역 코드 집합(배치 대상 필터)
RESIDENTIAL_GENERAL_CODES = {"13", "14", "15"}
# 비일조권 용도지역일 때 도로 제외 판단 거리 기준(m)
ROAD_EXCLUSION_DISTANCE_M = 20.0
# 대상 필지 내부 옵셋 거리(m)
PARCEL_INWARD_OFFSET_M = 1.0
# 10m 미만 높이 구간에서 적용하는 고정 후퇴 깊이(m)
UNDER_10M_BUILDABLE_DEPTH_M = 1.5
# 높이 규칙 분기 기준 높이(m)
HEIGHT_LIMIT_M = 10.0

# 기본 노출 방향벡터 X 성분
DEFAULT_VEC_EXPOSURE_X = 0.0
# 기본 노출 방향벡터 Y 성분(정북)
DEFAULT_VEC_EXPOSURE_Y = 1.0
# 기본 노출 방향벡터 Z 성분
DEFAULT_VEC_EXPOSURE_Z = 0.0
# 단일 계산 실행 시 기본 높이(m)
DEFAULT_HEIGHT_M = 15.0
# 높이 대비 후퇴 깊이 비율(깊이 = ratio * height)
DEFAULT_RATIO = 1.5

LANDUSE_MAP = {
    "0": "지정되지않음",
    "11": "제1종전용주거지역",
    "12": "제2종전용주거지역",
    "13": "제1종일반주거지역",
    "14": "제2종일반주거지역",
    "15": "제3종일반주거지역",
    "16": "준주거지역",
    "17": "일반주거지역",
    "21": "중심상업지역",
    "22": "일반상업지역",
    "23": "근린상업지역",
    "24": "유통상업지역",
    "31": "전용공업지역",
    "32": "일반공업지역",
    "33": "준공업지역",
    "41": "보전녹지지역",
    "42": "생산녹지지역",
    "43": "자연녹지지역",
    "44": "개발제한구역",
    "51": "용도미지정지역",
    "61": "관리지역",
    "62": "보전관리지역",
    "63": "생산관리지역",
    "64": "계획관리지역",
    "71": "농림지역",
    "81": "자연환경보전지역",
}

# 용도지역 코드 해석 실패 시 표시 문자열
LANDUSE_UNKNOWN = "미확인"
