# -*- coding: utf-8 -*-
"""North/South sky-exposure base curve computation.

이 모듈은 사용자가 제공한 로직을 기반으로 정북(정남) 사선의 베이스 커브를 계산한다.
현재 `fx.utils`는 스텁 상태이므로, 실제 실행을 위해서는 utils 구현이 필요하다.

Grasshopper에서 import해서 호출하는 것을 전제로 한다.
"""

try:
    from typing import List, Optional
except ImportError:  # IronPython compatibility
    pass

import math
import itertools

import Rhino.Geometry as geo  # type: ignore

from fx import utils
from fx.constants import TOL, ANGLE_90_DEGREE


def get_target_segs(boundary, vec, tol=math.radians(1)):
    # type: (geo.Curve, geo.Vector3d, float) -> List[geo.Curve]
    """영역 내에서 해당 vec 방향의 segment들을 추출한다."""
    targets = []
    for seg in utils.explode(boundary):
        vec_in = utils.get_inside_perp_vec(seg, boundary)
        if vec * vec_in < math.sin(tol):
            continue
        targets.append(seg)
    return targets


def get_exposure_base_segs(seg, y_vec, neighbor_crvs, max_height):
    # type: (geo.Curve, geo.Vector3d, List[geo.Curve], float) -> List[geo.Curve]
    """이웃 토지들에서 seg에 영향을 주는 사선을 구해준다.

    Args:
        seg: 사선 고려할 segment
        y_vec: 사선이 들어오는 방향
        neighbor_crvs: 사선에 생성에 영향을 주는 토지들(자기 토지도 포함 가능)
        max_height: 최대 사선이 생길 수 있는 거리(그 밖 토지는 무시)

    Returns:
        사선 방향의 가장 가까운 토지의 segment들
    """
    x_vec = geo.Vector3d(y_vec)
    x_vec.Rotate(ANGLE_90_DEGREE, geo.Vector3d.ZAxis)
    plane = geo.Plane(seg.PointAtStart, x_vec, -y_vec)
    base_interval = utils.get_square_domain_from_seg(seg, plane).x_interval
    if base_interval.IsIncreasing:
        base_intervals = [base_interval]
    else:
        base_interval.Swap()
        base_intervals = [base_interval]

    region = utils.get_rect_from_seg(seg, -y_vec, max_height).crv
    filtered = [
        crv for crv in neighbor_crvs if utils.has_region_intersection(region, crv)
    ]
    if not filtered:
        return []

    intersections = utils.get_intersection_regions(
        [region], utils.get_union_regions(filtered)
    )
    if not intersections:
        return []

    vertices = list(itertools.chain(*[utils.get_vertices(crv) for crv in filtered]))

    dict_domain = {}
    for intersection in intersections:
        for target in get_target_segs(intersection, -y_vec):
            pts_cutter = [v for v in vertices if utils.is_pt_on_crv(v, target, TOL)]
            if pts_cutter:
                target_segs = utils.split_crv_from_pts(target, pts_cutter, TOL, TOL)
            else:
                target_segs = [target]
            for target_seg in target_segs:
                square_domain = utils.get_square_domain_from_seg(target_seg, plane)
                dict_domain[square_domain] = target_seg

    segs_front = []
    for square_domain in sorted(dict_domain.keys()):
        diff_intervals = utils.subtract_interval(
            base_intervals, square_domain.x_interval
        )
        if (
            sum(i.Length for i in base_intervals)
            - sum(i.Length for i in diff_intervals)
        ) < TOL:
            continue

        segs_front.append(dict_domain[square_domain])
        if not diff_intervals or sum(i.Length for i in diff_intervals) < TOL:
            break

        base_intervals = diff_intervals

    return segs_front


def get_centered_seg(crv, seg_exposure, vec):
    # type: (geo.Curve, geo.Curve, geo.Vector3d) -> geo.Curve
    """사선 시작 segment를 중심으로 옮겨준다."""
    pts = []
    for pt in (seg_exposure.PointAtStart, seg_exposure.PointAtEnd):
        if utils.is_pt_on_crv(pt, crv):
            pts.append(pt)
        else:
            pt_projected = utils.get_pt_from_pt_to_crvs(pt, vec, [crv])
            if not pt_projected:
                pts.append(pt)
            else:
                pts.append((pt + pt_projected) / 2)
    return geo.LineCurve(pts[0], pts[1])


def get_centered_segs(crv, segs_exposure, vec):
    # type: (geo.Curve, List[geo.Curve], geo.Vector3d) -> List[geo.Curve]
    """사선 시작 segment들을 중심으로 옮겨준다."""
    return [get_centered_seg(crv, seg, vec) for seg in segs_exposure]


def filter_short_segs(segs, vec_in):
    # type: (List[geo.Curve], geo.Vector3d) -> List[geo.Curve]
    vec_check = geo.Vector3d(vec_in)
    vec_check.Rotate(ANGLE_90_DEGREE, geo.Vector3d.ZAxis)

    filtered = []
    for crv in utils.get_joined_crvs(segs):
        if math.fabs(vec_check * (crv.PointAtStart - crv.PointAtEnd)) < 0.5:
            continue
        filtered += utils.explode(crv)

    return filtered


class BaseCrv(object):
    """사선 시작 선 + 시작 높이(현재는 0만 사용)."""

    def __init__(self, crv, height):
        # type: (geo.Curve, float) -> None
        self.crv = crv
        self.height = height


def compute_northsky_base_crvs(
    lot_region,
    vec_exposure,
    max_distance,
    neighbor_lot_crvs_without_gong,
    is_center_start,
    excluded_lot_crvs=None,
):
    # type: (geo.Curve, geo.Vector3d, float, List[geo.Curve], bool, Optional[List[geo.Curve]]) -> List[BaseCrv]
    """정북(정남) 사선의 BaseCrv들을 계산한다.

    이 함수는 `NorthSkyManager._get_base_crvs()` 로직을 독립적으로 옮긴 것이다.

    Args:
        lot_region: 자기 토지 경계(닫힌 커브)
        vec_exposure: 사선 방향 벡터(정북/정남)
        max_distance: 사선이 영향을 줄 수 있는 최대 거리
        neighbor_lot_crvs_without_gong: 주변 토지 경계 커브들(공공부지 등 제외된 리스트)
        is_center_start: north_sky.is_center_start 대응
        excluded_lot_crvs: (옵션) 20m 이상 도로에 동시에 접한 토지 등의 제외 대상 토지 경계 커브들

    Returns:
        BaseCrv 리스트. 현재 height는 0으로 채운다.

    Notes:
        - 성능 최적화/캐싱 목적의 코드는 포함하지 않는다.
        - 정확히 동일한 결과가 필요하면 excluded_lot_crvs를 넘겨야 한다.
    """

    def _filter_excluded_segs(seg_base, segs):
        # type: (geo.Curve, List[geo.Curve]) -> List[geo.Curve]
        filtered = []
        for seg in segs:
            # 20m 이상 도로에 동시에 접한 토지에 생기는 정북사선 제거
            if excluded_lot_crvs and any(
                utils.is_seg_on_crv(seg, lot_crv) for lot_crv in excluded_lot_crvs
            ):
                continue
            # 사선 방향 segment는 제거하지 않는다
            if utils.is_seg_on_crv(seg, seg_base):
                filtered.append(seg)
                continue
            # 사선 방향이 아닌 자기 토지에 생기는 정북 사선 제거
            if utils.is_seg_on_crv(seg, lot_region):
                continue
            filtered.append(seg)
        return filtered

    crvs_check = list(neighbor_lot_crvs_without_gong) + [lot_region]

    result_bases = []  # type: List[geo.Curve]
    for seg_base in get_target_segs(lot_region, vec_exposure):
        segs_exposure = get_exposure_base_segs(
            seg_base, vec_exposure, crvs_check, max_distance
        )
        segs_filtered = _filter_excluded_segs(seg_base, segs_exposure)
        if not segs_filtered:
            continue

        if not is_center_start:
            result_bases += segs_filtered
        else:
            result_bases += get_centered_segs(seg_base, segs_filtered, vec_exposure)

    result_bases = filter_short_segs(result_bases, vec_exposure)
    return [BaseCrv(crv, 0) for crv in result_bases]


def compute_northsky_base_segments(
    lot_region,
    vec_exposure,
    max_distance,
    neighbor_lot_crvs_without_gong,
    is_center_start,
    excluded_lot_crvs=None,
):
    # type: (geo.Curve, geo.Vector3d, float, List[geo.Curve], bool, Optional[List[geo.Curve]]) -> List[geo.Curve]
    """`compute_northsky_base_crvs()`의 Curve 리스트 버전."""
    return [
        b.crv
        for b in compute_northsky_base_crvs(
            lot_region=lot_region,
            vec_exposure=vec_exposure,
            max_distance=max_distance,
            neighbor_lot_crvs_without_gong=neighbor_lot_crvs_without_gong,
            is_center_start=is_center_start,
            excluded_lot_crvs=excluded_lot_crvs,
        )
    ]


class NorthSkyBaseCurveCalculator(object):
    """GH에서 쓰기 좋게 감싼 정북/정남 베이스 커브 계산기."""

    def __init__(
        self,
        vec_exposure,
        max_distance,
        is_center_start,
        excluded_lot_crvs=None,
    ):
        # type: (geo.Vector3d, float, bool, Optional[List[geo.Curve]]) -> None
        self.vec_exposure = vec_exposure
        self.max_distance = max_distance
        self.is_center_start = is_center_start
        self.excluded_lot_crvs = excluded_lot_crvs

    def compute_base_crvs(self, lot_region, neighbor_lot_crvs_without_gong):
        # type: (geo.Curve, List[geo.Curve]) -> List[BaseCrv]
        return compute_northsky_base_crvs(
            lot_region=lot_region,
            vec_exposure=self.vec_exposure,
            max_distance=self.max_distance,
            neighbor_lot_crvs_without_gong=neighbor_lot_crvs_without_gong,
            is_center_start=self.is_center_start,
            excluded_lot_crvs=self.excluded_lot_crvs,
        )

    def compute_base_segments(self, lot_region, neighbor_lot_crvs_without_gong):
        # type: (geo.Curve, List[geo.Curve]) -> List[geo.Curve]
        return compute_northsky_base_segments(
            lot_region=lot_region,
            vec_exposure=self.vec_exposure,
            max_distance=self.max_distance,
            neighbor_lot_crvs_without_gong=neighbor_lot_crvs_without_gong,
            is_center_start=self.is_center_start,
            excluded_lot_crvs=self.excluded_lot_crvs,
        )
