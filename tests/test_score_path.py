"""The path of a score (studio/score/path.py): clips -> one embedding per step; slerp across the gaps, cuts without a gap."""
import numpy as np
import pytest

from studio.score.path import build_path, slerp

VECS = np.eye(4, dtype=np.float32)               # four orthogonal sources


def clip(start, dur, *comp):
    return {"start": start, "dur": dur, "comp": [list(p) for p in comp]}


def test_rows_run_from_the_first_clip_to_the_last():
    rows, t0 = build_path([clip(5, 2, (0, 1)), clip(10, 3, (1, 1))], VECS, 0.5)
    assert t0 == 5 and len(rows) == 16                       # 5 s .. 13 s, a row per half second
    assert np.allclose(np.linalg.norm(rows, axis=1), 1, atol=1e-5)
    assert np.allclose(rows[0], VECS[0]) and np.allclose(rows[-1], VECS[1])


def test_a_gap_is_a_slerp_and_no_gap_is_a_cut():
    rows, _ = build_path([clip(0, 2, (0, 1)), clip(4, 2, (1, 1))], VECS, 0.5)
    k = 6                                                      # the row of t = 3.25: 5/8 of the way across the gap 2 .. 4
    from studio.score.path import curve_position, read_curve
    assert np.allclose(rows[k], slerp(VECS[0], VECS[1], curve_position(read_curve(None), 0.625)), atol=1e-5)      # at the pace of the default curve
    assert rows[5][0] > rows[6][0] > rows[7][0]                # it moves from the first source to the second
    cut, _ = build_path([clip(0, 2, (0, 1)), clip(2, 2, (1, 1))], VECS, 0.5)
    assert set(np.round(cut[:, 0], 3)) == {0.0, 1.0}           # no step in between


def test_a_mix_is_the_normalised_sum():
    rows, _ = build_path([clip(0, 1, (0, 0.5), (1, 0.5))], VECS, 0.5)
    assert np.allclose(rows[0], np.array([1, 1, 0, 0]) / np.sqrt(2), atol=1e-6)


@pytest.mark.parametrize("bad", [[], [clip(0, 2, (9, 1))], [clip(0, 0.01, (0, 1))], [clip(0, 2, (0, 1)), clip(1, 2, (1, 1))], [clip(0, 2, (0, 0))]])
def test_bad_scores_are_refused(bad):
    with pytest.raises(ValueError):
        build_path(bad, VECS, 0.5)


def test_the_curve_sets_the_speed_of_the_interpolation():
    from studio.score.path import DEFAULT_CURVE, curve_position, read_curve
    pts = read_curve(None)
    assert pts == [tuple(map(float, p)) for p in DEFAULT_CURVE]
    assert curve_position(pts, 0.0) == 0 and curve_position(pts, 1.0) == 1 and curve_position(pts, 0.5) == pytest.approx(0.5)
    assert curve_position(pts, 0.2) == pytest.approx(0.4)                          # it goes through its dots
    assert 0 <= min(curve_position(pts, x / 50) for x in range(51)) and max(curve_position(pts, x / 50) for x in range(51)) <= 1
    slow = [[0, 0], [0.5, 0.1], [1, 1]]                                               # lingers on the first clip
    a = [clip(0, 2, (0, 1)), dict(clip(4, 2, (1, 1)))]
    a[0]["curve"] = slow
    rows, _ = build_path(a, VECS, 0.5)
    assert rows[6][0] > rows[6][1] and np.allclose(rows[6], slerp(VECS[0], VECS[1], curve_position(read_curve(slow), 0.625)), atol=1e-5)
    for bad in ([[0, 0]], [[0, 0], [0, 1]], [[0, 0], [2, 1]], [[0, 0], [1, float("nan")]]):
        with pytest.raises(ValueError):
            read_curve(bad)
