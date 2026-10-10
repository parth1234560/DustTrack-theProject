"""Pure-Python geodesic helpers for road segments.

Coordinates are GeoJSON ``[lon, lat]`` in WGS84 decimal degrees. Distance
from a point to a polyline uses a local equirectangular projection, which
is accurate to well under a metre for the short ranges used here
(GPS plausibility is ~150 m).
"""

from __future__ import annotations

import itertools
from math import asin, cos, hypot, radians, sin, sqrt

EARTH_RADIUS_M: float = 6371000.0
_METERS_PER_DEG_LAT: float = radians(1.0) * EARTH_RADIUS_M


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in metres."""
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * asin(sqrt(a))


def _to_local(
    coords: list[list[float]], lat0: float
) -> tuple[list[tuple[float, float]], float, float]:
    """Project [lon, lat] coords to local metres; return points and scales."""
    kx = _METERS_PER_DEG_LAT * cos(radians(lat0))
    ky = _METERS_PER_DEG_LAT
    return [((lon * kx), (lat * ky)) for lon, lat in coords], kx, ky


def _point_to_segment_m(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_linestring_m(
    lat: float, lon: float, coords: list[list[float]]
) -> float:
    """Shortest distance from a point to a polyline, in metres."""
    if not coords:
        raise ValueError("coords must contain at least one point")
    if len(coords) == 1:
        return haversine_m(lat, lon, coords[0][1], coords[0][0])
    lat0 = sum(c[1] for c in coords) / len(coords)
    points, kx, ky = _to_local([list(c) for c in coords], lat0)
    px, py = lon * kx, lat * ky
    return min(
        _point_to_segment_m(px, py, ax, ay, bx, by)
        for (ax, ay), (bx, by) in itertools.pairwise(points)
    )


def linestring_length_m(coords: list[list[float]]) -> float:
    """Total length of a polyline in metres (0 for < 2 points)."""
    if len(coords) < 2:
        return 0.0
    return sum(
        haversine_m(a[1], a[0], b[1], b[0]) for a, b in itertools.pairwise(coords)
    )


def linestring_midpoint(coords: list[list[float]]) -> tuple[float, float]:
    """Midpoint along the length as (lat, lon); single point returns itself."""
    if not coords:
        raise ValueError("coords must contain at least one point")
    if len(coords) < 2:
        return (coords[0][1], coords[0][0])
    legs = [haversine_m(a[1], a[0], b[1], b[0]) for a, b in itertools.pairwise(coords)]
    total = sum(legs)
    if total == 0.0:
        return (coords[0][1], coords[0][0])
    target = total / 2.0
    acc = 0.0
    for a, b, leg in zip(coords, coords[1:], legs):
        if acc + leg >= target:
            frac = (target - acc) / leg if leg > 0 else 0.0
            lon = a[0] + (b[0] - a[0]) * frac
            lat = a[1] + (b[1] - a[1]) * frac
            return (lat, lon)
        acc += leg
    last = coords[-1]
    return (last[1], last[0])


def split_linestring(
    coords: list[list[float]], target_m: float
) -> list[list[list[float]]]:
    """Split a polyline into n equal-length pieces sharing endpoints.

    n = max(1, round(total / target_m)), so no tiny remainder stretch ever
    appears (1012 m at 250 m -> 4 pieces of ~253 m). A line shorter than
    half of target_m stays whole.
    """
    if target_m <= 0:
        raise ValueError("target_m must be positive")
    pts = [[float(c[0]), float(c[1])] for c in coords]
    if len(pts) < 2:
        return [pts]
    legs = [haversine_m(a[1], a[0], b[1], b[0]) for a, b in itertools.pairwise(pts)]
    total = sum(legs)
    if total <= 0.0:
        return [pts]

    def point_at(s: float) -> list[float]:
        acc = 0.0
        for i, leg in enumerate(legs):
            if acc + leg >= s or i == len(legs) - 1:
                frac = (s - acc) / leg if leg > 0 else 0.0
                frac = max(0.0, min(1.0, frac))
                a, b = pts[i], pts[i + 1]
                return [a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac]
            acc += leg
        return list(pts[-1])

    n = max(1, round(total / target_m))
    boundaries = [(total * k) / n for k in range(n + 1)]

    # Cumulative distance of each interior vertex, for inclusion in pieces.
    vertex_at: list[float] = []
    acc = 0.0
    for leg in legs[:-1]:
        acc += leg
        vertex_at.append(acc)

    pieces: list[list[list[float]]] = []
    for start, end in itertools.pairwise(boundaries):
        piece = [point_at(start)]
        for idx, vdist in enumerate(vertex_at, start=1):
            if start < vdist < end:
                piece.append(list(pts[idx]))
        piece.append(point_at(end))
        pieces.append(piece)
    return pieces
