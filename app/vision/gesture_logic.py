"""Pure gesture classification and filtering helpers.

This module deliberately has no camera, GUI, or desktop-input dependencies so
its behavior can be tested in headless CI.
"""
from __future__ import annotations

import math


def classify_gesture(
    *,
    index_up: bool,
    middle_up: bool,
    ring_up: bool,
    pinky_up: bool,
    pinching: bool,
) -> str:
    """Classify a single-hand pose into one deterministic control mode."""
    if index_up and middle_up and ring_up and not pinky_up:
        return "scroll"
    if index_up and middle_up and not ring_up and not pinky_up:
        return "zoom"
    if pinching:
        return "click"
    if index_up and not middle_up and not ring_up and not pinky_up:
        return "pointer"
    return "idle"


def smoothing_alpha(delta_seconds: float, time_constant: float = 0.045) -> float:
    """Return a frame-rate-independent EMA alpha in the inclusive range 0..1."""
    if time_constant <= 0:
        raise ValueError("time_constant must be positive")
    dt = min(0.1, max(0.001, float(delta_seconds)))
    return 1.0 - math.exp(-dt / time_constant)


def smooth_point(
    previous: tuple[float, float] | None,
    target: tuple[float, float],
    delta_seconds: float,
    time_constant: float = 0.045,
) -> tuple[float, float]:
    """Smooth cursor coordinates without overshooting the target."""
    if previous is None:
        return target
    alpha = smoothing_alpha(delta_seconds, time_constant)
    return (
        previous[0] + alpha * (target[0] - previous[0]),
        previous[1] + alpha * (target[1] - previous[1]),
    )


def wheel_delta(
    motion: float,
    *,
    sensitivity: float = 1800.0,
    deadzone: float = 0.0015,
    max_delta: int = 48,
) -> int:
    """Convert normalized fingertip motion into a small smooth wheel delta.

    Positive motion means scroll up / zoom in. The returned value uses the
    Windows wheel-delta unit (120 units per conventional notch).
    """
    if sensitivity <= 0 or deadzone < 0 or max_delta < 1:
        raise ValueError("Invalid wheel filter configuration")
    value = float(motion)
    if not math.isfinite(value) or abs(value) < deadzone:
        return 0
    scaled = int(round(value * sensitivity))
    if scaled == 0:
        scaled = 1 if value > 0 else -1
    return max(-max_delta, min(max_delta, scaled))
