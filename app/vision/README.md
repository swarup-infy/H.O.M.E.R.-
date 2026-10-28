# Gesture recognition (optional)

This component uses the MediaPipe Tasks Gesture Recognizer API to classify
hand gestures in a supplied RGB image. It does not open the webcam by itself.

Install the optional dependency:

```powershell
pip install -r requirements-vision.txt
```

Download a compatible `.task` gesture-recognizer model from the official
[MediaPipe documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer)
and pass its local path to `recognize_image(image, model_path)`.

Camera access must remain opt-in. This module only returns predictions; it
does not map gestures to desktop actions. Require explicit confirmation for
any future action that could change or delete data.
