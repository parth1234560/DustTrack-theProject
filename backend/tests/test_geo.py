"""Golden-number tests for geo helpers."""

from __future__ import annotations

import itertools

import pytest

from common import geo

# 1 degree of latitude ~= pi/180 * 6371000 m.
DEG_LAT_M = 111194.92664455874


def test_haversine_one_degree_latitude():
    assert geo.haversine_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(DEG_LAT_M, abs=0.5)


def test_haversine_zero():
    assert geo.haversine_m(28.61, 77.20, 28.61, 77.20) == pytest.approx(0.0)


def test_distance_to_linestring_on_line_is_zero():
    coords = [[77.20, 28.61], [77.21, 28.62]]
    lat, lon = geo.linestring_midpoint(coords)
    assert geo.distance_to_linestring_m(lat, lon, coords) < 0.01


def test_distance_to_linestring_offset():
    # A point 150 m north of a short east-west segment.
    coords = [[77.20, 28.61], [77.21, 28.61]]
    lat = 28.61 + 150.0 / DEG_LAT_M
    dist = geo.distance_to_linestring_m(lat, 77.205, coords)
    assert dist == pytest.approx(150.0, abs=2.0)


def test_distance_single_point():
    dist = geo.distance_to_linestring_m(28.61, 77.20, [[77.20, 28.61]])
    assert dist == pytest.approx(0.0)


def test_distance_empty_raises():
    with pytest.raises(ValueError):
        geo.distance_to_linestring_m(0.0, 0.0, [])


def test_linestring_length():
    coords = [[77.20, 28.61], [77.20, 28.61 + 1000.0 / DEG_LAT_M]]
    assert geo.linestring_length_m(coords) == pytest.approx(1000.0, abs=1.0)
    assert geo.linestring_length_m([[1.0, 2.0]]) == 0.0


def test_linestring_midpoint_straight_line():
    coords = [[77.20, 28.60], [77.20, 28.62]]
    lat, lon = geo.linestring_midpoint(coords)
    assert lat == pytest.approx(28.61)
    assert lon == pytest.approx(77.20)


def test_split_even():
    span = 1000.0 / DEG_LAT_M
    coords = [[77.20, 28.60], [77.20, 28.60 + span]]
    pieces = geo.split_linestring(coords, 250.0)
    assert len(pieces) == 4
    for piece in pieces:
        assert geo.linestring_length_m(piece) == pytest.approx(250.0, abs=1.0)
    # Consecutive pieces share endpoints.
    for first, second in itertools.pairwise(pieces):
        assert first[-1] == pytest.approx(second[0])


def test_split_no_remainder_sliver():
    # 1012 m at 250 m -> 4 equal pieces of ~253 m, never 4x250 + 12 m.
    span = 1012.0 / DEG_LAT_M
    coords = [[77.20, 28.60], [77.20, 28.60 + span]]
    pieces = geo.split_linestring(coords, 250.0)
    assert len(pieces) == 4
    for piece in pieces:
        assert geo.linestring_length_m(piece) == pytest.approx(253.0, abs=1.0)


def test_split_rounds_to_nearest_count():
    span = 260.0 / DEG_LAT_M
    coords = [[77.20, 28.60], [77.20, 28.60 + span]]
    assert len(geo.split_linestring(coords, 250.0)) == 1
    span = 380.0 / DEG_LAT_M
    coords = [[77.20, 28.60], [77.20, 28.60 + span]]
    pieces = geo.split_linestring(coords, 250.0)
    assert len(pieces) == 2
    for piece in pieces:
        assert geo.linestring_length_m(piece) == pytest.approx(190.0, abs=1.0)


def test_split_short_line_returned_whole():
    coords = [[77.20, 28.60], [77.20, 28.601]]
    pieces = geo.split_linestring(coords, 250.0)
    assert len(pieces) == 1
    assert pieces[0][0] == pytest.approx(coords[0])
    assert pieces[0][-1] == pytest.approx(coords[-1])


def test_split_bad_target():
    with pytest.raises(ValueError):
        geo.split_linestring([[0.0, 0.0], [1.0, 1.0]], 0.0)
