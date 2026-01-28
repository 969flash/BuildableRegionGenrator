"""Shared utilities for GH/Rhino scripts.

주의:
- 일부 기능(Shapefile 로딩)은 `pyshp`(shapefile) 설치가 필요합니다.
- 정북사선 등 순수 지오메트리 유틸을 쓰는 경우를 위해 `shapefile` import는 optional 입니다.
"""

try:
    import shapefile  # type: ignore
except Exception:
    shapefile = None  # type: ignore
import os
from typing import List, Tuple, Any, Optional, Union
import ghpythonlib.components as ghcomp
import Rhino.Geometry as geo
import math

TOL = 0.001  # 연산 허용 오차
RAW_TOL = 0.1  # 원시 데이터 허용 오차


class Parcel:
    """기본 필지 클래스"""

    def __init__(
        self,
        region: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve],
    ):
        self.region = region  # 외부 경계 커브
        self.hole_regions = (
            hole_regions if hole_regions is not None else []
        )  # 내부 구멍들
        self.pnu = pnu
        self.jimok = jimok
        self.record = record
        self._area = None

    @property
    def area(self) -> float:
        """필지 면적 계산"""
        if self._area is None:
            outer_area = get_area(self.region)
            hole_area = get_area(self.hole_regions) if self.hole_regions else 0.0
            self._area = outer_area - hole_area
        return self._area

    def preprocess_curve(self) -> bool:
        """커브 전처리 (invalid 제거, 자체교차 제거, 단순화)"""
        if not self.region or not self.region.IsValid:
            return False

        # 자체교차 확인
        intersection_events = geo.Intersect.Intersection.CurveSelf(self.region, TOL)
        if intersection_events:
            simplified = self.region.Simplify(
                geo.CurveSimplifyOptions.All, RAW_TOL, 1.0
            )
            if simplified:
                self.region = simplified
            else:
                return False

        # 일반 단순화
        simplified = self.region.Simplify(geo.CurveSimplifyOptions.All, RAW_TOL, 1.0)
        if simplified:
            self.region = simplified

        # 내부 구멍들도 처리
        valid_holes = []
        for hole in self.hole_regions:
            if hole and hole.IsValid:
                simplified_hole = hole.Simplify(
                    geo.CurveSimplifyOptions.All, RAW_TOL, 1.0
                )
                if simplified_hole:
                    valid_holes.append(simplified_hole)
                else:
                    valid_holes.append(hole)
        self.hole_regions = valid_holes

        return True


class Road(Parcel):
    """도로 클래스"""

    pass


class Lot(Parcel):
    """대지 클래스"""

    def __init__(
        self,
        curve_crv: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve] = None,
    ):
        super().__init__(curve_crv, pnu, jimok, record, hole_regions)
        self.is_flag_lot = False  # 자루형 토지 여부
        self.has_road_access = False  # 도로 접근 여부


def read_shp_file(file_path: str) -> Tuple[List[Any], List[Any], List[str]]:
    """shapefile을 읽어서 shapes와 records를 반환"""
    if shapefile is None:
        raise ImportError(
            "pyshp(shapefile) is required for read_shp_file(). Install it in your Rhino CPython environment."
        )
    try:
        sf = shapefile.Reader(file_path, encoding="utf-8")
    except:
        try:
            sf = shapefile.Reader(file_path, encoding="cp949")
        except:
            sf = shapefile.Reader(file_path)

    shapes = sf.shapes()
    records = sf.records()
    fields = [field[0] for field in sf.fields[1:]]
    return shapes, records, fields


def get_curve_from_points(
    points: List[Tuple[float, float]], start_idx: int, end_idx: int
) -> Optional[geo.PolylineCurve]:
    """점 리스트에서 특정 구간의 커브를 생성"""
    # 최소 3개의 점이 필요
    if end_idx - start_idx < 3:
        return None

    # 시작과 끝 점이 동일하지 않으면(닫혀있지 않으면) None 반환
    first_pt = points[start_idx]
    last_pt = points[end_idx - 1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        return None

    curve_points = [
        geo.Point3d(points[i][0], points[i][1], 0) for i in range(start_idx, end_idx)
    ]

    curve_crv = geo.PolylineCurve(curve_points)
    return curve_crv if curve_crv and curve_crv.IsValid else None


def get_part_indices(shape: Any) -> List[Tuple[int, int]]:
    """shape의 각 파트의 시작과 끝 인덱스를 반환"""
    if not hasattr(shape, "parts") or len(shape.parts) <= 1:
        return [(0, len(shape.points))]

    parts = list(shape.parts) + [len(shape.points)]
    return [(parts[i], parts[i + 1]) for i in range(len(shape.parts))]


def get_intersection_points(
    curve_a: geo.Curve, curve_b: geo.Curve, tol: float = TOL
) -> List[geo.Point3d]:
    """두 커브 사이의 교차점을 계산합니다."""
    intersections = geo.Intersect.Intersection.CurveCurve(curve_a, curve_b, tol, tol)
    if not intersections:
        return []
    return [event.PointA for event in intersections]


def get_vertices(curve: geo.Curve) -> List[geo.Point3d]:
    """커브의 모든 정점(Vertex)들을 추출합니다."""
    if not curve:
        return []
    vertices = [curve.PointAt(curve.SpanDomain(i)[0]) for i in range(curve.SpanCount)]
    if not curve.IsClosed:
        vertices.append(curve.PointAtEnd)
    return vertices


def explode(crv: geo.Curve) -> List[geo.Curve]:
    """커브를 segment들로 분해합니다.

    - 폴리라인/폴리커브는 각 세그먼트로 분해
    - 일반 Curve는 가능한 경우 Polyline 근사 후 분해
    """
    if not crv:
        return []

    # PolylineCurve
    if isinstance(crv, geo.PolylineCurve):
        pl = crv.ToPolyline()
        pts = list(pl)
        if len(pts) < 2:
            return []
        return [geo.LineCurve(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]

    # PolyCurve 등: DuplicateSegments를 먼저 시도
    try:
        segs = list(crv.DuplicateSegments())
        segs = [s for s in segs if s and s.IsValid and s.GetLength() > TOL]
        if segs:
            return segs
    except Exception:
        pass

    # fallback: polyline 근사
    try:
        pl_crv = crv.ToPolyline(0, 0, RAW_TOL, RAW_TOL, RAW_TOL, 0, 0, 0, True)
        if pl_crv:
            return explode(pl_crv)
    except Exception:
        pass

    return [crv]


def get_inside_perp_vec(
    seg: geo.Curve, boundary: geo.Curve, tol: float = TOL
) -> geo.Vector3d:
    """segment 기준, boundary 내부를 향하는 수직 벡터를 반환합니다."""
    a = seg.PointAtStart
    b = seg.PointAtEnd
    tan = b - a
    tan.Z = 0
    if tan.Length < 1e-9:
        return geo.Vector3d(0, 0, 0)
    tan.Unitize()

    perp = geo.Vector3d(-tan.Y, tan.X, 0)
    perp.Unitize()

    mid = seg.PointAtNormalizedLength(0.5)
    eps = max(tol * 10.0, 0.01)
    plane = geo.Plane.WorldXY

    try:
        inside = boundary.Contains(mid + perp * eps, plane, tol)
        if inside != geo.PointContainment.Outside:
            return perp
    except Exception:
        pass

    return -perp


class _SquareDomain(object):
    """Plane 좌표계로 투영한 segment의 x/y 구간.

    - northsky 로직에서 dict key 및 sorting에 사용.
    - sorting은 y(사선 방향 거리) 오름차순 우선.
    """

    def __init__(self, x_min: float, x_max: float, y_min: float, y_max: float):
        if x_min <= x_max:
            self.x_interval = geo.Interval(x_min, x_max)
        else:
            self.x_interval = geo.Interval(x_max, x_min)
        if y_min <= y_max:
            self.y_interval = geo.Interval(y_min, y_max)
        else:
            self.y_interval = geo.Interval(y_max, y_min)

        # 해시 안정화를 위한 스냅
        snap = 1e-6
        self._key = (
            round(self.x_interval.T0 / snap) * snap,
            round(self.x_interval.T1 / snap) * snap,
            round(self.y_interval.T0 / snap) * snap,
            round(self.y_interval.T1 / snap) * snap,
        )

    def __lt__(self, other):
        return (
            self.y_interval.T0,
            self.y_interval.T1,
            self.x_interval.T0,
            self.x_interval.T1,
        ) < (
            other.y_interval.T0,
            other.y_interval.T1,
            other.x_interval.T0,
            other.x_interval.T1,
        )

    def __hash__(self):
        return hash(self._key)

    def __eq__(self, other):
        return isinstance(other, _SquareDomain) and self._key == other._key


def _plane_uv(plane: geo.Plane, pt: geo.Point3d) -> Tuple[float, float]:
    try:
        rc, u, v = plane.ClosestParameter(pt)
        if rc:
            return float(u), float(v)
    except Exception:
        pass
    # fallback: manually project using axes
    op = pt - plane.Origin
    return float(op * plane.XAxis), float(op * plane.YAxis)


def get_square_domain_from_seg(seg: geo.Curve, plane: geo.Plane) -> _SquareDomain:
    """segment를 plane 좌표계로 투영해 x/y 구간(domain)을 반환합니다."""
    pts = [seg.PointAtStart, seg.PointAtEnd]
    uvs = [_plane_uv(plane, p) for p in pts]
    xs = [uv[0] for uv in uvs]
    ys = [uv[1] for uv in uvs]
    return _SquareDomain(min(xs), max(xs), min(ys), max(ys))


class _RectRegion(object):
    def __init__(self, crv: geo.Curve):
        self.crv = crv


def get_rect_from_seg(
    seg: geo.Curve, vec: geo.Vector3d, distance: float
) -> _RectRegion:
    """segment를 기준으로 vec 방향으로 distance만큼 뻗은 직사각형 region을 만듭니다."""
    a = seg.PointAtStart
    b = seg.PointAtEnd
    v = geo.Vector3d(vec)
    v.Z = 0
    if v.Length < 1e-9:
        v = geo.Vector3d(0, 0, 0)
    else:
        v.Unitize()
        v *= float(distance)

    a2 = a + v
    b2 = b + v
    poly = geo.Polyline([a, b, b2, a2, a])
    return _RectRegion(geo.PolylineCurve(poly))


def is_pt_on_crv(pt: geo.Point3d, crv: geo.Curve, tol=TOL):
    """pt가 crv 위에 있는지 확인"""
    rc, param = crv.ClosestPoint(pt, tol)
    if not rc:
        return False

    closest_pt = crv.PointAt(param)
    if closest_pt.DistanceTo(pt) <= tol:
        return True

    return False


def is_seg_on_crv(seg: geo.Curve, crv: geo.Curve, tol=TOL):
    """seg가 crv 위에 있는지 확인"""
    # seg의 끝점 밑 중점은 crv 위에 있어야 한다.
    for pt in (seg.PointAtStart, seg.PointAtEnd):
        if not is_pt_on_crv(pt, crv, tol):
            return False

    pt_mid = seg.PointAtNormalizedLength(0.5)
    if not is_pt_on_crv(pt_mid, crv, tol):
        return False

    return True


def get_overlapped_curves(
    curve_a: geo.Curve, curve_b: geo.Curve, tol: float = TOL
) -> List[geo.Curve]:
    """두 커브가 겹치는 구간의 커브들을 반환합니다."""
    intersection_points = get_intersection_points(curve_a, curve_b)
    if not intersection_points:
        return []

    params = [curve_a.SpanDomain(i)[0] for i in range(curve_a.SpanCount)]
    params += [curve_a.ClosestPoint(pt, tol)[1] for pt in intersection_points]
    shatter_result = ghcomp.Shatter(curve_a, params)

    if not shatter_result:
        return []

    overlapped_segments = [seg for seg in shatter_result if is_seg_on_crv(seg, curve_b)]
    if not overlapped_segments:
        return []

    return geo.Curve.JoinCurves(overlapped_segments)


def get_overlapped_length(curve_a: geo.Curve, curve_b: geo.Curve) -> float:
    """두 커브가 겹치는 총 길이를 계산합니다."""
    overlapped_curves = get_overlapped_curves(curve_a, curve_b)
    if not overlapped_curves:
        return 0.0
    return sum(crv.GetLength() for crv in overlapped_curves)


def get_curves_from_shape(
    shape: Any,
) -> Tuple[Optional[geo.PolylineCurve], List[geo.PolylineCurve]]:
    """shape에서 외부 경계와 내부 구멍 커브들을 추출"""
    boundary_region = None
    hole_regions = []

    part_indices = get_part_indices(shape)

    for i, (start_idx, end_idx) in enumerate(part_indices):
        curve_crv = get_curve_from_points(shape.points, start_idx, end_idx)
        if curve_crv:
            if i == 0:
                boundary_region = curve_crv
            else:
                hole_regions.append(curve_crv)

    # 단일 폴리곤이고 닫혀있지 않은 경우 처리
    if boundary_region is None and len(part_indices) == 1:
        points = [geo.Point3d(pt[0], pt[1], 0) for pt in shape.points]
        if len(points) >= 3:
            if points[0].DistanceTo(points[-1]) > TOL:
                points.append(points[0])
            curve_crv = geo.PolylineCurve(points)
            if curve_crv and curve_crv.IsValid:
                boundary_region = curve_crv

    return boundary_region, hole_regions


def get_field_value(
    record: List[Any], fields: List[str], field_name: str, default: str = "Unknown"
) -> str:
    """레코드에서 특정 필드값을 안전하게 추출"""
    try:
        index = fields.index(field_name)
        return record[index]
    except (ValueError, IndexError):
        return default


def create_parcel_from_shape(
    shape: Any, record: List[Any], fields: List[str]
) -> Optional[Parcel]:
    """shape에서 Parcel 객체 생성"""
    boundary_region, hole_regions = get_curves_from_shape(shape)

    if not boundary_region or not boundary_region.IsValid:
        return None

    pnu = get_field_value(record, fields, "A1")  # 구 PNU
    jimok = get_field_value(record, fields, "A11")  # 구 JIMOK

    if jimok == "도로":
        parcel = Road(boundary_region, pnu, jimok, record, hole_regions)
    else:
        parcel = Lot(boundary_region, pnu, jimok, record, hole_regions)

    return parcel if parcel.preprocess_curve() else None


def has_intersection(
    curve_a: geo.Curve,
    curve_b: geo.Curve,
    plane: geo.Plane = geo.Plane.WorldXY,
    tol: float = TOL,
) -> bool:
    """두 커브가 교차하는지 여부를 확인합니다."""
    return geo.Curve.PlanarCurveCollision(curve_a, curve_b, plane, tol)


def has_region_intersection(
    region_a: geo.Curve, region_b: geo.Curve, tol: float = TOL
) -> bool:
    """두 영역(닫힌 커브)이 겹치거나 접하는지 검사합니다."""
    if not region_a or not region_b:
        return False

    plane = geo.Plane.WorldXY
    try:
        if geo.Curve.PlanarCurveCollision(region_a, region_b, plane, tol):
            return True
    except Exception:
        pass

    # collision이 false여도 포함 관계일 수 있으니 샘플 점으로 검사
    try:
        pt_b = region_b.PointAtNormalizedLength(0.5)
        if region_a.Contains(pt_b, plane, tol) != geo.PointContainment.Outside:
            return True
    except Exception:
        pass

    try:
        pt_a = region_a.PointAtNormalizedLength(0.5)
        if region_b.Contains(pt_a, plane, tol) != geo.PointContainment.Outside:
            return True
    except Exception:
        pass

    return False


def _normalize_ghcomp_result(result):
    """ghpythonlib.components 결과를 Curve 리스트로 정규화."""
    if result is None:
        return []
    if isinstance(result, tuple):
        # 일반적으로 첫 출력이 커브 리스트
        result = result[0] if result else []
    if isinstance(result, list):
        return [c for c in result if c]
    return [result]


def get_union_regions(crvs: List[geo.Curve]) -> List[geo.Curve]:
    """RegionUnion을 수행해 결과 영역 커브들을 반환합니다."""
    if not crvs:
        return []
    try:
        return _normalize_ghcomp_result(ghcomp.RegionUnion(crvs))
    except Exception:
        # 실패 시 원본 반환(최소한의 동작 보장)
        return [c for c in crvs if c]


def get_intersection_regions(
    regions_a: List[geo.Curve], regions_b: List[geo.Curve]
) -> List[geo.Curve]:
    """RegionIntersection을 수행해 교차 영역 커브들을 반환합니다."""
    if not regions_a or not regions_b:
        return []

    try:
        return _normalize_ghcomp_result(ghcomp.RegionIntersection(regions_a, regions_b))
    except Exception:
        # fallback: pairwise intersection
        out = []
        for a in regions_a:
            for b in regions_b:
                try:
                    out += _normalize_ghcomp_result(ghcomp.RegionIntersection([a], [b]))
                except Exception:
                    pass
        return out


def split_crv_from_pts(
    crv: geo.Curve,
    pts: List[geo.Point3d],
    split_tol: float = TOL,
    join_tol: float = TOL,
) -> List[geo.Curve]:
    """커브를 pts 위치에서 Split합니다."""
    if not crv:
        return []
    if not pts:
        return [crv]

    params = []
    for pt in pts:
        try:
            rc, t = crv.ClosestPoint(pt, split_tol)
            if rc:
                params.append(t)
        except Exception:
            pass

    if not params:
        return [crv]

    # 유사 파라미터 중복 제거
    params = sorted(params)
    uniq = []
    for t in params:
        if not uniq or abs(t - uniq[-1]) > 1e-9:
            uniq.append(t)

    try:
        pieces = crv.Split(uniq)
        if not pieces:
            return [crv]
        return [p for p in pieces if p and p.IsValid and p.GetLength() > split_tol]
    except Exception:
        return [crv]


def subtract_interval(
    intervals: List[geo.Interval], interval_to_subtract: geo.Interval
) -> List[geo.Interval]:
    """intervals에서 interval_to_subtract를 빼고 남은 Interval 리스트를 반환합니다."""
    if not intervals:
        return []

    sub = geo.Interval(interval_to_subtract)
    if not sub.IsIncreasing:
        sub.Swap()

    out = []
    for itv in intervals:
        cur = geo.Interval(itv)
        if not cur.IsIncreasing:
            cur.Swap()

        # no overlap
        if cur.T1 <= sub.T0 or cur.T0 >= sub.T1:
            out.append(cur)
            continue

        # left remainder
        if cur.T0 < sub.T0 - 1e-12:
            out.append(geo.Interval(cur.T0, min(cur.T1, sub.T0)))

        # right remainder
        if cur.T1 > sub.T1 + 1e-12:
            out.append(geo.Interval(max(cur.T0, sub.T1), cur.T1))

    return [i for i in out if i.Length > 0]


def get_joined_crvs(crvs: List[geo.Curve], tol: float = TOL) -> List[geo.Curve]:
    """커브들을 Join한 결과를 리스트로 반환합니다."""
    if not crvs:
        return []
    try:
        joined = geo.Curve.JoinCurves([c for c in crvs if c], tol)
        return [c for c in joined if c]
    except Exception:
        return [c for c in crvs if c]


def get_pt_from_pt_to_crvs(
    pt: geo.Point3d, vec: geo.Vector3d, crvs: List[geo.Curve], tol: float = TOL
) -> Optional[geo.Point3d]:
    """pt에서 vec 방향으로 ray를 쏴서 crvs와의 가장 가까운 교차점을 반환합니다."""
    if not crvs:
        return None

    v = geo.Vector3d(vec)
    v.Z = 0
    if v.Length < 1e-9:
        return None
    v.Unitize()

    far = 100000.0
    line = geo.Line(pt, pt + v * far)

    best_pt = None
    best_dist = None
    for crv in crvs:
        if not crv:
            continue
        try:
            events = geo.Intersect.Intersection.LineCurve(line, crv, tol, tol)
        except Exception:
            events = None
        if not events:
            continue

        for ev in events:
            p = getattr(ev, "PointA", None) or getattr(ev, "PointB", None)
            if p is None:
                continue

            dvec = p - pt
            if (dvec * v) <= tol:
                continue
            dist = dvec.Length
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_pt = p

    return best_pt


def get_parcels_from_shapes(
    shapes: List[Any], records: List[Any], fields: List[str]
) -> List[Parcel]:
    """모든 shape에서 Parcel 객체들을 생성"""
    parcels = []

    for shape, record in zip(shapes, records):
        parcel = create_parcel_from_shape(shape, record, fields)
        if parcel:
            parcels.append(parcel)

    return parcels


def classify_parcels(parcels: List[Parcel]) -> Tuple[List[Lot], List[Road]]:
    """Parcel 리스트를 Lot과 Road로 분류"""
    lots = []
    roads = []

    for parcel in parcels:
        if isinstance(parcel, Road):
            roads.append(parcel)
        else:
            lots.append(parcel)

    return lots, roads


def get_area(regions: Union[List[geo.Curve], geo.Curve]) -> float:
    """영역 커브의 면적을 계산합니다."""
    if not isinstance(regions, list):
        regions = [regions]

    area = sum([geo.AreaMassProperties.Compute(r).Area for r in regions])
    return round(area, 6)


def get_straight_skeleton(region_curve):
    """
    스트레이트 스켈레톤 알고리즘 기반 중심선 추출
    """
    # 1. 입력 커브를 폴리라인으로 변환
    if not region_curve.IsClosed:
        return None

    polyline = None
    if isinstance(region_curve, geo.PolylineCurve):
        polyline = region_curve.ToPolyline()
    else:
        # 곡선일 경우 분할하여 근사화
        polyline_curve = region_curve.ToPolyline(0, 0, 0.1, 0.1, 0.1, 0, 0, 0, True)
        polyline = polyline_curve.ToPolyline()

    points = list(polyline)
    if points[0].DistanceTo(points[-1]) < 0.001:
        points.pop()  # 중복 끝점 제거

    n = len(points)
    skeleton_lines = []

    # 2. 각 꼭짓점에서 이등분선(Bisector) 방향 계산
    bisectors = []
    for i in range(n):
        p_prev = points[(i - 1 + n) % n]
        p_curr = points[i]
        p_next = points[(i + 1) % n]

        v1 = p_prev - p_curr
        v2 = p_next - p_curr
        v1.Unitize()
        v2.Unitize()

        # 두 벡터의 합으로 이등분선 방향 설정
        bisect_vec = v1 + v2

        # 직선이 평행한 경우 처리
        if bisect_vec.Length < 1e-6:
            bisect_vec = geo.Vector3d(-v1.Y, v1.X, 0)
        else:
            bisect_vec.Unitize()

        # 내부 방향 확인 (Cross Product 활용)
        cross = geo.Vector3d.CrossProduct(v1, v2)
        if cross.Z > 0:  # 시계/반시계 방향에 따라 반전 필요할 수 있음
            bisect_vec *= -1

        bisectors.append(bisect_vec)

    # 3. 이웃한 이등분선 간의 교점 계산 (Event Simulation)
    # 단순화를 위해 각 꼭짓점에서 시작하는 이등분선과 다음 이등분선의 교점을 연결
    new_points = []
    for i in range(n):
        line1 = geo.Line(points[i], points[i] + bisectors[i] * 1000)
        next_idx = (i + 1) % n
        line2 = geo.Line(
            points[next_idx], points[next_idx] + bisectors[next_idx] * 1000
        )

        rc, a, b = geo.Intersect.Intersection.LineLine(line1, line2)
        if rc:
            intersect_pt = line1.PointAt(a)
            # 원래 꼭짓점에서 교점까지의 선을 스켈레톤의 일부로 추가
            skeleton_lines.append(geo.LineCurve(points[i], intersect_pt))
            skeleton_lines.append(geo.LineCurve(points[next_idx], intersect_pt))
            new_points.append(intersect_pt)

    # 4. 교점들끼리 연결하여 내부 중심선 완성
    for i in range(len(new_points)):
        p1 = new_points[i]
        p2 = new_points[(i + 1) % len(new_points)]
        if p1.DistanceTo(p2) > 0.001:
            skeleton_lines.append(geo.LineCurve(p1, p2))

    return geo.Curve.JoinCurves(skeleton_lines)


# 실행 예시
# skeleton = get_straight_skeleton(input_region)
