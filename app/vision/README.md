# Gesture recognition (optional)

This module uses MediaPipe Tasks' Gesture Recognizer API for hand-gesture
classification. It does not open a webcam by itself. The caller must request
camera permission and provide an RGB image.

Install the optional dependencies from the project root:

```powershell
pip install -r requirements-vision.txt
```

Download a compatible `.task` gesture model from the official
[MediaPipe gesture-recognizer documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer)
and pass its local path to `recognize_image(image, model_path)`.

Camera processing is opt-in. Avoid always-on camera loops, and do not map
gestures to destructive system actions without explicit confirmation.
