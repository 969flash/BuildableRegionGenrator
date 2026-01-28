# -*- coding: utf-8 -*-
"""Geometry utility stubs.

요청대로 현재는 필요한 함수들을 '비워둔 상태'로 제공한다.
Grasshopper/Rhino 환경에 맞는 구현은 이후 채워 넣으면 된다.

주의:
- 현재 파일은 실행 가능한 구현을 제공하지 않으며,
  호출 시 NotImplementedError를 발생시킨다.
"""

try:
    import Rhino.Geometry as geo  # type: ignore
except Exception:  # pragma: no cover
    geo = None  # type: ignore


def _stub(name):
    raise NotImplementedError(
        "utils.%s is a stub. Implement it for your GH/Rhino environment." % name
    )


def explode(crv):
    _stub("explode")


def get_inside_perp_vec(seg, boundary):
    _stub("get_inside_perp_vec")


def get_square_domain_from_seg(seg, plane):
    _stub("get_square_domain_from_seg")


def get_rect_from_seg(seg, vec, distance):
    _stub("get_rect_from_seg")


def has_region_intersection(region_a, region_b):
    _stub("has_region_intersection")


def get_intersection_regions(regions_a, regions_b):
    _stub("get_intersection_regions")


def get_union_regions(crvs):
    _stub("get_union_regions")


def get_vertices(crv):
    _stub("get_vertices")


def is_pt_on_crv(pt, crv, tol=None):
    _stub("is_pt_on_crv")


def split_crv_from_pts(crv, pts, split_tol=None, join_tol=None):
    _stub("split_crv_from_pts")


def subtract_interval(intervals, interval_to_subtract):
    _stub("subtract_interval")


def get_joined_crvs(crvs):
    _stub("get_joined_crvs")


def is_seg_on_crv(seg, crv):
    _stub("is_seg_on_crv")


def get_pt_from_pt_to_crvs(pt, vec, crvs):
    _stub("get_pt_from_pt_to_crvs")
