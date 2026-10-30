# Gesture recognition and air mouse (optional)

HOMER can use a webcam to track one hand and control the Windows mouse. The
camera is opened only after you click **Gesture controls** in the desktop app
(or explicitly request gesture mode by voice). Closing the hand-mouse window
stops the camera and releases the MediaPipe tracker.

## Install

Use the same active Python 3.11 virtual environment as HOMER:

```powershell
python -m pip install -r requirements-vision.txt
```

## Controls

- **Move pointer:** hold your index finger up and move it around in the camera view.
- **Click:** briefly pinch your thumb and index fingertip together.
- **Scroll:** hold your index and middle fingers up while moving your hand vertically.
- **Pause:** click the Pause tracking button.
- **Stop:** close the window.

The camera preview is mirrored so hand movement feels natural. The pointer uses
smoothing to reduce jitter. Keep the hand visible and well lit. Tracking runs
locally; camera frames are not uploaded to the AI provider.

## Troubleshooting

- If the camera fails to open, close apps such as Camera, Zoom, or Teams that
  might be using it, then reopen Gesture controls.
- If Windows blocks camera access, allow desktop apps to access the camera in
  Windows Privacy & security settings.
- If MediaPipe installation fails, use a supported 64-bit Python 3.11
  environment and reinstall the optional requirements.
- If the cursor feels too sensitive, adjust the `_smooth` value in
  `app/vision/mouse_control.py` (smaller values mean smoother/slower movement).

This uses MediaPipe's hand landmarks and PyAutoGUI for pointer, click, and
scroll actions. Use Pause or close the window whenever you need normal mouse
control. PyAutoGUI's corner failsafe remains enabled.
