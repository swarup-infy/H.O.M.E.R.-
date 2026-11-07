"""Headless tests for gesture recognition and motion filtering."""
import math

import pytest

from app.vision.gesture_logic import (
    classify_gesture,
    smooth_point,
    smoothing_alpha,
    wheel_delta,
)


@pytest.mark.parametrize(
    ("pose", "expected"),
    [
        ({"index_up": True, "middle_up": True, "ring_up": True, "pinky_up": False}, "scroll"),
        ({"index_up": True, "middle_up": True, "ring_up": False, "pinky_up": False}, "zoom"),
        ({"index_up": False, "middle_up": False, "ring_up": False, "pinky_up": False, "pinching": True}, "click"),
        ({"index_up": True, "middle_up": False, "ring_up": False, "pinky_up": False}, "pointer"),
        ({"index_up": False, "middle_up": False, "ring_up": False, "pinky_up": False}, "idle"),
    ],
)
def test_gesture_pose_classification(pose, expected):
    defaults = {
        "index_up": False,
        "middle_up": False,
        "ring_up": False,
        "pinky_up": False,
        "pinching": False,
    }
    defaults.update(pose)
    assert classify_gesture(**defaults) == expected


def test_three_finger_scroll_has_priority_over_pinch():
    assert classify_gesture(
        index_up=True,
        middle_up=True,
        ring_up=True,
        pinky_up=False,
        pinching=True,
    ) == "scroll"


def test_two_finger_zoom_has_priority_over_click_pinch():
    assert classify_gesture(
        index_up=True,
        middle_up=True,
        ring_up=False,
        pinky_up=False,
        pinching=True,
    ) == "zoom"


def test_smoothing_alpha_is_bounded_and_positive():
    assert 0 < smoothing_alpha(1 / 60) < 1
    assert smoothing_alpha(0) > 0
    assert smoothing_alpha(1) < 1


def test_smoothing_rejects_invalid_time_constant():
    with pytest.raises(ValueError):
        smoothing_alpha(0.02, 0)


def test_smooth_point_initializes_without_lag():
    assert smooth_point(None, (100.0, 200.0), 0.02) == (100.0, 200.0)


def test_smooth_point_moves_toward_target_without_overshoot():
    result = smooth_point((0.0, 0.0), (100.0, 50.0), 0.02)
    assert 0 < result[0] < 100
    assert 0 < result[1] < 50


def test_wheel_delta_respects_deadzone():
    assert wheel_delta(0.001) == 0


def test_wheel_delta_preserves_scroll_and_zoom_direction():
    assert wheel_delta(0.02) > 0
    assert wheel_delta(-0.02) < 0


def test_wheel_delta_is_capped_to_keep_gesture_motion_controlled():
    assert wheel_delta(1.0, max_delta=24) == 24
    assert wheel_delta(-1.0, max_delta=24) == -24


def test_wheel_delta_handles_non_finite_input():
    assert wheel_delta(math.nan) == 0
    assert wheel_delta(math.inf) == 0


def test_wheel_delta_rejects_invalid_filter_configuration():
    with pytest.raises(ValueError):
        wheel_delta(0.1, sensitivity=0)
