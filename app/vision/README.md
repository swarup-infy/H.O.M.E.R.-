# Gesture recognition and air mouse (optional)

HOMER uses one hand through your webcam to control the Windows pointer and
supported desktop applications. The camera starts only after you select
**Gesture controls** (or explicitly request gesture mode by voice). Closing
the gesture window releases the camera and MediaPipe tracker.

## Install

Use the same active Python 3.11 virtual environment as HOMER:

```powershell
python -m pip install -r requirements-vision.txt
```

## Gesture controls

Keep your palm facing the camera and your hand fully visible.

| Gesture | Action |
|---|---|
| Raise only the index finger | Move the pointer |
| Briefly pinch thumb + index finger | Click once; release before the next click |
| Raise index + middle + ring fingers (keep pinky down) | Scroll vertically by moving the hand up/down |
| Raise index + middle fingers only (keep ring/pinky down) | Zoom by spreading the two fingertips to zoom in and bringing them together to zoom out |
| Pause button | Immediately stop gesture input |
| Close window | Stop tracking and release the camera |

Three-finger scrolling uses small Windows mouse-wheel deltas and motion
filtering rather than coarse multi-notch jumps. Two-finger zoom sends
**Ctrl + mouse wheel**, which is supported by common browsers, image viewers,
and many desktop applications. An application that does not implement
Ctrl+wheel zoom may ignore this gesture.

Pointer movement uses time-based smoothing so it behaves consistently when
camera inference runs at different frame rates. The preview is mirrored, uses
a low-resolution camera stream for lower CPU load, and attempts to keep only
the newest camera frame to reduce latency.

## Privacy and safety

- Camera frames are processed locally by MediaPipe; they are not uploaded to
  the AI provider.
- The camera is never started in the background.
- PyAutoGUI's corner failsafe remains enabled. If triggered, gesture input is
  paused and you must move the mouse away from the corner before resuming.
- If a desktop input error occurs, HOMER pauses gesture input instead of
  repeatedly sending mouse or keyboard events.
- Use the Pause button or close the window whenever you need normal mouse
  control.

## Troubleshooting

- If the camera fails to open, close Camera, Zoom, Teams, or other apps that
  may be using it, then reopen Gesture controls.
- Allow desktop apps to access the camera in Windows Privacy & security.
- Use a well-lit background and keep the hand inside the camera frame.
- If tracking is jittery, move slightly farther from the camera and avoid
  rapid hand rotation.
- If MediaPipe installation fails, use a supported 64-bit Python 3.11
  environment and reinstall the optional requirements.
- If zoom does not work in an app, check whether that app supports Ctrl+wheel
  zoom. HOMER cannot force zoom in an application that does not expose it.
