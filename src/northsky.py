# -*- coding: utf-8 -*-
"""North/South sky-exposure computation (정북/정남 사선)."""

try:
    from typing import List, Optional
except ImportError:  # IronPython compatibility
    pass

import itertools
import math

import Rhino.Geometry as geo  # type: ignore

try:
    from . import utils  # type: ignore
except Exception:
    import utils  # type: ignore

import importlib


importlib.reload(utils)

ANGLE_90_DEGREE = math.pi / 2.0
TOL = getattr(utils, "TOL", 0.001)


class NorthSkyCalculator(object):
    """정북사선을 고려한 기준선/건축가능영역 계산기.

    외부에서 호출하는 메서드는 `compute()` 하나만 사용한다.
    계산 결과는 멤버 변수에 저장된다.
    - `base_segments`: List[geo.Curve]
    - `buildable_boundary`: Optional[geo.Curve]
    """

    def __init__(
        self,
        vec_exposure,
        max_distance,
        is_center_start,
        height,
        ratio,
        base_offset=0.0,
        base_height=0.0,
        excluded_lot_crvs=None,
    ):
        # type: (geo.Vector3d, float, bool, float, float, float, float, Optional[List[geo.Curve]]) -> None
        self.vec_exposure = geo.Vector3d(vec_exposure)
        self.max_distance = float(max_distance)
        self.is_center_start = bool(is_center_start)

        self.height = float(height)
        self.ratio = float(ratio)
        self.base_offset = float(base_offset)
        self.base_height = float(base_height)
        self.excluded_lot_crvs = excluded_lot_crvs

        self.base_segments = []  # type: List[geo.Curve]
        self.buildable_boundary = None  # type: Optional[geo.Curve]

    def compute(self, lot_region, neighbor_lot_crvs_without_gong):
        # type: (geo.Curve, List[geo.Curve]) -> None
        self.base_segments = self._compute_base_segments(
            lot_region=lot_region,
            neighbor_lot_crvs_without_gong=neighbor_lot_crvs_without_gong,
        )
        self.buildable_boundary = self._compute_buildable_boundary(
            region=lot_region,
            base_segments=self.base_segments,
            height=self.height,
        )

    def _get_target_segs(self, boundary, vec, tol=math.radians(1)):
        # type: (geo.Curve, geo.Vector3d, float) -> List[geo.Curve]
        targets = []
        for seg in utils.explode(boundary):
            vec_in = utils.get_inside_perp_vec(seg, boundary)
            if vec * vec_in < math.sin(tol):
                continue
            targets.append(seg)
        return targets

    def _get_exposure_base_segs(self, seg, y_vec, neighbor_crvs, max_height):
        # type: (geo.Curve, geo.Vector3d, List[geo.Curve], float) -> List[geo.Curve]
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
            for target in self._get_target_segs(intersection, -y_vec):
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

    def _get_centered_seg(self, crv, seg_exposure, vec):
        # type: (geo.Curve, geo.Curve, geo.Vector3d) -> geo.Curve
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

    def _get_centered_segs(self, crv, segs_exposure, vec):
        # type: (geo.Curve, List[geo.Curve], geo.Vector3d) -> List[geo.Curve]
        return [self._get_centered_seg(crv, seg, vec) for seg in segs_exposure]

    def _filter_short_segs(self, segs, vec_in):
        # type: (List[geo.Curve], geo.Vector3d) -> List[geo.Curve]
        vec_check = geo.Vector3d(vec_in)
        vec_check.Rotate(ANGLE_90_DEGREE, geo.Vector3d.ZAxis)

        filtered = []
        for crv in utils.get_joined_crvs(segs):
            if math.fabs(vec_check * (crv.PointAtStart - crv.PointAtEnd)) < 0.5:
                continue
            filtered += utils.explode(crv)

        return filtered

    def _filter_excluded_segs(self, lot_region, seg_base, segs):
        # type: (geo.Curve, geo.Curve, List[geo.Curve]) -> List[geo.Curve]
        filtered = []
        for seg in segs:
            if self.excluded_lot_crvs and any(
                utils.is_seg_on_crv(seg, lot_crv) for lot_crv in self.excluded_lot_crvs
            ):
                continue
            if utils.is_seg_on_crv(seg, seg_base):
                filtered.append(seg)
                continue
            if utils.is_seg_on_crv(seg, lot_region):
                continue
            filtered.append(seg)
        return filtered

    def _compute_base_segments(self, lot_region, neighbor_lot_crvs_without_gong):
        # type: (geo.Curve, List[geo.Curve]) -> List[geo.Curve]
        crvs_check = list(neighbor_lot_crvs_without_gong) + [lot_region]

        result_bases = []  # type: List[geo.Curve]
        for seg_base in self._get_target_segs(lot_region, -self.vec_exposure):
            segs_exposure = self._get_exposure_base_segs(
                seg_base, self.vec_exposure, crvs_check, self.max_distance
            )
            segs_filtered = self._filter_excluded_segs(
                lot_region=lot_region,
                seg_base=seg_base,
                segs=segs_exposure,
            )
            if not segs_filtered:
                continue

            if not self.is_center_start:
                result_bases += segs_filtered
            else:
                result_bases += self._get_centered_segs(
                    seg_base, segs_filtered, self.vec_exposure
                )

        return self._filter_short_segs(result_bases, self.vec_exposure)

    def _compute_buildable_boundary(self, region, base_segments, height):
        # type: (geo.Curve, List[geo.Curve], float) -> Optional[geo.Curve]
        if not region:
            return None
        if not base_segments:
            return region

        h = float(height)
        cutters = []
        for base_seg in base_segments:
            if h < self.base_height:
                depth = self.base_offset
            else:
                depth = self.ratio * h

            move_vec = geo.Vector3d(-self.vec_exposure)
            if move_vec.Length < 1e-9:
                continue
            move_vec.Unitize()
            move_vec *= depth

            moved = utils.move_crv(base_seg, move_vec)
            strip = utils.make_closed_crv_from_crv_crv(base_seg, moved)
            if strip and strip.IsValid:
                cutters.append(strip)

        if not cutters:
            return region

        result_regions = utils.get_difference_regions_one_to_one(region, cutters)
        if not result_regions:
            return None

        result_region = max(result_regions, key=lambda r: utils.get_area(r))
        simplified = result_region.Simplify(geo.CurveSimplifyOptions.All, TOL, 1.0)
        return simplified or result_region
