"""Optional MediaPipe hand-gesture recognition helpers.

This module never opens the webcam. The caller must explicitly obtain camera
permission and supply an RGB NumPy image when requesting recognition.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class GestureDependencyError(RuntimeError):
    """Raised when MediaPipe is not installed."""


def recognize_image(
    image: Any,
    model_path: str | Path,
    min_confidence: float = 0.6,
) -> list[dict[str, Any]]:
    """Recognize gestures in an RGB image array using MediaPipe Tasks.

    The model asset is downloaded separately from official MediaPipe
    documentation. Model assets may have terms separate from the library.
    """
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise GestureDependencyError(
            "Install optional gesture dependencies with: "
            "pip install -r requirements-vision.txt"
        ) from exc

    model = Path(model_path).expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(
            f"MediaPipe model was not found at {model}. "
            "See app/vision/README.md for setup instructions."
        )
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0.0 and 1.0")

    options = mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=2,
    )
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
    with mp.tasks.vision.GestureRecognizer.create_from_options(options) as recognizer:
        result = recognizer.recognize(mp_image)

    predictions: list[dict[str, Any]] = []
    for hand_index, categories in enumerate(result.gestures or []):
        if not categories:
            continue
        top = categories[0]
        score = float(top.score or 0.0)
        if score >= min_confidence:
            predictions.append({
                "gesture": str(top.category_name),
                "score": score,
                "hand_index": hand_index,
            })
    return predictions
