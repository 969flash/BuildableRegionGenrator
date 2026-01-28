# -*- coding: utf-8 -*-
"""Shapefile -> Rhino.Geometry loader for GH.

목표:
- shp 파일에서 특정 PNU 필지를 `lot_region` 으로
- 나머지 필지를 `neighbor_lot_regions` 으로 반환

의존성:
- Rhino 환경 (Rhino.Geometry)
- (선택) pyshp 라이브러리: `import shapefile`

GH 구성 예:
1) 첫 번째 컴포넌트: ShpManager로 shp 읽고, lots 리스트(파이썬 객체)를 출력
2) 두 번째 컴포넌트: lots + target_pnu로 lot_region / neighbors 추출

주의:
- 필지 폴리곤의 holes/multipart는 단순 처리(각 ring을 Curve로 변환)한다.
  실제 업무 규칙(outer만 사용, holes 제외 등)에 맞게 필요 시 보강.
"""

try:
    from typing import Any, Dict, List, Optional, Tuple
except ImportError:  # IronPython
    pass

import Rhino.Geometry as geo  # type: ignore


class ShpManager(object):
    def __init__(self):
        self._lots = None  # type: Optional[List[Dict[str, Any]]]

    @staticmethod
    def _require_pyshp():
        try:
            import shapefile  # type: ignore

            return shapefile
        except Exception as e:
            raise ImportError(
                "pyshp(shapefile) is required to read .shp in this environment. "
                "In Rhino 8 CPython you can pip install it; in IronPython you may need a different approach. "
                "Original error: %s" % e
            )

    @staticmethod
    def _points_to_polyline_curve(points, close_tol=1e-9):
        # type: (List[geo.Point3d], float) -> geo.Curve
        if not points or len(points) < 3:
            raise ValueError("Not enough points to create a polygon.")

        pts = list(points)
        if pts[0].DistanceTo(pts[-1]) > close_tol:
            pts.append(pts[0])

        pl = geo.Polyline(pts)
        return geo.PolylineCurve(pl)

    @staticmethod
    def _shape_to_curves(shape):
        # type: (Any) -> List[geo.Curve]
        """pyshp shape -> list[Curve]."""
        # pyshp polygon: shape.points + shape.parts
        pts2d = shape.points
        parts = list(shape.parts) if getattr(shape, "parts", None) else [0]
        parts.append(len(pts2d))

        curves = []
        for i in range(len(parts) - 1):
            a = parts[i]
            b = parts[i + 1]
            ring = pts2d[a:b]
            ring3d = [geo.Point3d(x, y, 0.0) for (x, y) in ring]
            try:
                curves.append(ShpManager._points_to_polyline_curve(ring3d))
            except Exception:
                # skip invalid rings
                pass
        return curves

    @staticmethod
    def _record_to_dict(reader, record):
        # type: (Any, Any) -> Dict[str, Any]
        # reader.fields: [ ('DeletionFlag','C',1,0), ('PNU','C',...), ...]
        field_names = [f[0] for f in reader.fields[1:]]
        return dict(zip(field_names, list(record)))

    def load_lots(self, shp_path, encoding="cp949"):
        # type: (str, str) -> List[Dict[str, Any]]
        """shp를 읽어서 lots(list[dict])로 반환하고 내부에 캐시한다.

        각 lot dict:
        - 'attrs': 속성 dict
        - 'curves': 폴리곤 ring curve 리스트
        """
        shapefile = self._require_pyshp()

        r = shapefile.Reader(shp_path, encoding=encoding)
        lots = []
        for sr in r.iterShapeRecords():
            attrs = self._record_to_dict(r, sr.record)
            curves = self._shape_to_curves(sr.shape)
            if not curves:
                continue
            lots.append({"attrs": attrs, "curves": curves})

        self._lots = lots
        return lots

    @staticmethod
    def pick_lot_and_neighbors(lots, target_pnu, pnu_field="PNU"):
        # type: (List[Dict[str, Any]], str, str) -> Tuple[Optional[geo.Curve], List[geo.Curve]]
        """lots에서 target_pnu 하나를 lot_region으로, 나머지를 neighbors로 분리."""
        lot_region = None  # type: Optional[geo.Curve]
        neighbors = []  # type: List[geo.Curve]

        for item in lots:
            attrs = item.get("attrs") or {}
            curves = item.get("curves") or []
            pnu = attrs.get(pnu_field)

            # 단순 규칙: ring 중 첫 번째를 대표 경계로 사용
            if not curves:
                continue
            representative = curves[0]

            if pnu == target_pnu:
                lot_region = representative
            else:
                neighbors.append(representative)

        return lot_region, neighbors
