"""Optional MediaPipe hand-gesture recognition helpers.

Camera access is opt-in: importing this module does not access the webcam.
The caller is responsible for obtaining camera permission and opening frames.
"""
from __future__ import annotations

from typing import Any


class GestureDependencyError(RuntimeError):
    """Raised when MediaPipe is not installed or cannot be imported."""


def recognize_image(image: Any, model_path: str, min_confidence: float = 0.6) -> list[dict[str, Any]]:
    """Recognize hand gestures in an RGB image array.

    Args:
        image: RGB image as a NumPy array.
        model_path: Path to a MediaPipe Gesture Recognizer .task model file.
        min_confidence: Minimum score to return a prediction.

    Returns:
        A list of gesture predictions with gesture name, score, and hand index.

    Note:
        This uses MediaPipe's Tasks API. Download the model file separately
        from the official MediaPipe model resources and review its license.
    """
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise GestureDependencyError(
            "Gesture recognition requires the optional dependency. "
            "Install with: pip install -r requirements-vision.txt"
        ) from exc

    from pathlib import Path
    model = Path(model_path).expanduser().resolve()
    if not model.is_file():
        raise FileNotFoundError(
            f"MediaPipe gesture model not found: {model}. "
            "See docs/COMPONENTS.md for setup notes."
        )
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0.0 and 1.0")

    BaseOptions = mp.tasks.BaseOptions
    GestureRecognizer = mp.tasks.vision.GestureRecognizer
    GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=str(model)),
        running_mode=RunningMode.IMAGE,
        num_hands=2,
    )
    image_obj = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
    with GestureRecognizer.create_from_options(options) as recognizer:
        result = recognizer.recognize(image_obj)

    predictions: list[dict[str, Any]] = []
    for hand_index, hand_gestures in enumerate(result.gestures or []):
        if not hand_gestures:
            continue
        top = hand_gestures[0]
        score = float(top.score or 0.0)
        if score >= min_confidence:
            predictions.append({
                "gesture": str(top.category_name),
                "score": score,
                "hand_index": hand_index,
            })
    return predictions
