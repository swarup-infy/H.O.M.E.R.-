"""Camera-based, opt-in gesture controls for the HOMER desktop app.

Gestures (one hand, palm facing the camera):
- Index finger only: move the pointer.
- Thumb + index pinch: click once per pinch.
- Index + middle + ring fingers: smooth vertical scrolling.
- Index + middle fingers: pinch/spread to zoom in/out (Ctrl + wheel).
- Pause or close this window to stop all gesture actions.
"""
from __future__ import annotations

import ctypes
import math
import sys
import time

import cv2
import mediapipe as mp
import pyautogui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
)

from app.vision.gesture_logic import classify_gesture, smooth_point, wheel_delta


class GestureMouseWindow(QMainWindow):
    """Opt-in webcam hand tracking that controls the system mouse."""

    WHEEL_EVENT = 0x0800  # MOUSEEVENTF_WHEEL; Windows wheel delta is 120/notch.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HOMER | Gesture Controls")
        self.setMinimumSize(800, 620)
        self.resize(960, 760)
        self._capture = None
        self._hands = None
        self._paused = False
        self._pinch_down = False
        self._last_scroll_y = None
        self._last_zoom_distance = None
        self._last_cursor = None
        self._last_pointer_time = None
        self._last_frame_time = 0.0
        self._scroll_motion = 0.0
        self._zoom_motion = 0.0
        self._cursor_time_constant = 0.045
        self._camera_index = 0

        root = QWidget()
        root.setStyleSheet("""
            QWidget { background: #050b16; color: #e8f7ff; font-family: 'Segoe UI'; }
            QLabel#title { color: #73e5ff; font-size: 21px; font-weight: 700; }
            QLabel#status { color: #9eb7cc; font-size: 13px; }
            QPushButton { background: #12304a; border: 1px solid #26769b;
                border-radius: 9px; padding: 10px 18px; color: #e8f7ff; font-weight: 600; }
            QPushButton:hover { background: #174565; }
            QLabel#preview { background: #02050b; border: 1px solid #1d4057; border-radius: 10px; }
        """)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("HOMER / GESTURE CONTROLS")
        title.setObjectName("title")
        subtitle = QLabel(
            "Index = pointer  •  Thumb + index pinch = click  •  "
            "3 fingers = scroll  •  2 fingers = zoom"
        )
        subtitle.setObjectName("status")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.preview = QLabel("Camera is starting…")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(640, 400)
        layout.addWidget(self.preview, 1)

        self.status = QLabel("Starting camera…")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.addStretch(1)
        self.pause_button = QPushButton("Ⅱ  Pause tracking")
        self.pause_button.clicked.connect(self.toggle_pause)
        stop_button = QPushButton("■  Stop and close")
        stop_button.clicked.connect(self.close)
        row.addWidget(self.pause_button)
        row.addWidget(stop_button)
        layout.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._process_frame)
        self._start_camera()

    def _start_camera(self):
        try:
            self._capture = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not self._capture.isOpened():
                self._capture.release()
                self._capture = cv2.VideoCapture(self._camera_index)
            if not self._capture.isOpened():
                raise RuntimeError(
                    "HOMER could not open your webcam. Close apps using the camera "
                    "and check Windows Camera permissions."
                )
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # Avoid building a queue of stale frames when inference is slower than capture.
            if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.65,
                min_tracking_confidence=0.65,
            )
            self._timer.start()
            self.status.setText(
                "Camera active. Three fingers scroll; two fingers zoom. "
                "Close this window to stop."
            )
        except Exception as exc:
            self.status.setText(str(exc))
            self.preview.setText("Camera unavailable")
            self._release_camera()

    @staticmethod
    def _distance(a, b):
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _finger_up(landmarks, tip, pip):
        return landmarks[tip].y < landmarks[pip].y

    def _reset_gesture_state(self):
        self._pinch_down = False
        self._last_scroll_y = None
        self._last_zoom_distance = None
        self._scroll_motion = 0.0
        self._zoom_motion = 0.0
        self._last_cursor = None
        self._last_pointer_time = None

    def _move_pointer(self, landmark, now):
        screen_width, screen_height = pyautogui.size()
        # Ignore the outer 8% of the camera view to make edge control easier.
        margin = 0.08
        nx = min(1.0, max(0.0, (landmark.x - margin) / (1 - 2 * margin)))
        ny = min(1.0, max(0.0, (landmark.y - margin) / (1 - 2 * margin)))
        target = (nx * (screen_width - 1), ny * (screen_height - 1))
        dt = 1 / 30 if self._last_pointer_time is None else now - self._last_pointer_time
        self._last_cursor = smooth_point(
            self._last_cursor, target, dt, self._cursor_time_constant
        )
        self._last_pointer_time = now
        pyautogui.moveTo(
            int(round(self._last_cursor[0])),
            int(round(self._last_cursor[1])),
            duration=0,
            _pause=False,
        )

    def _send_wheel_delta(self, delta, *, zoom=False):
        """Send sub-notch wheel deltas on Windows for smoother movement."""
        if not delta:
            return
        if zoom:
            pyautogui.keyDown("ctrl", _pause=False)
        try:
            if sys.platform == "win32":
                ctypes.windll.user32.mouse_event(self.WHEEL_EVENT, 0, 0, int(delta), 0)
            else:
                # Fallback for development/testing on non-Windows systems.
                clicks = int(round(delta / 120))
                if clicks:
                    pyautogui.scroll(clicks, _pause=False)
        finally:
            if zoom:
                pyautogui.keyUp("ctrl", _pause=False)

    def _handle_hand(self, points, now):
        index_tip = points[8]
        thumb_tip = points[4]
        index_up = self._finger_up(points, 8, 6)
        middle_up = self._finger_up(points, 12, 10)
        ring_up = self._finger_up(points, 16, 14)
        pinky_up = self._finger_up(points, 20, 18)
        pinching = self._distance(thumb_tip, index_tip) < 0.045

        mode = classify_gesture(
            index_up=index_up,
            middle_up=middle_up,
            ring_up=ring_up,
            pinky_up=pinky_up,
            pinching=pinching,
        )

        if mode == "scroll":
            # Average three fingertips to reduce landmark jitter.
            scroll_y = (points[8].y + points[12].y + points[16].y) / 3
            if self._last_scroll_y is not None:
                movement = self._last_scroll_y - scroll_y
                self._scroll_motion = 0.55 * self._scroll_motion + 0.45 * movement
                delta = wheel_delta(
                    self._scroll_motion,
                    sensitivity=1800,
                    deadzone=0.0015,
                    max_delta=42,
                )
                self._send_wheel_delta(delta)
            self._last_scroll_y = scroll_y
            self._last_zoom_distance = None
            self._zoom_motion = 0.0
            self._pinch_down = False
            return "SCROLL • 3 FINGERS"

        if mode == "zoom":
            # Spreading index and middle fingertips zooms in; pinching them zooms out.
            separation = self._distance(points[8], points[12])
            if self._last_zoom_distance is not None:
                movement = separation - self._last_zoom_distance
                self._zoom_motion = 0.55 * self._zoom_motion + 0.45 * movement
                delta = wheel_delta(
                    self._zoom_motion,
                    sensitivity=2200,
                    deadzone=0.0018,
                    max_delta=36,
                )
                self._send_wheel_delta(delta, zoom=True)
            self._last_zoom_distance = separation
            self._last_scroll_y = None
            self._scroll_motion = 0.0
            self._pinch_down = False
            return "ZOOM • 2 FINGERS"

        self._last_scroll_y = None
        self._last_zoom_distance = None
        self._scroll_motion = 0.0
        self._zoom_motion = 0.0

        if mode == "click":
            # Edge-triggered: one click until the hand releases the pinch.
            if not self._pinch_down:
                pyautogui.click(_pause=False)
            self._pinch_down = True
            return "CLICK • RELEASE TO RESET"

        self._pinch_down = False
        if mode == "pointer":
            self._move_pointer(index_tip, now)
            return "POINTER • INDEX FINGER"
        return "HAND READY"

    def _process_frame(self):
        if self._capture is None or not self._capture.isOpened():
            return
        ok, frame = self._capture.read()
        if not ok:
            self.status.setText("Could not read webcam frame. Check camera connection.")
            self._reset_gesture_state()
            return

        frame = cv2.flip(frame, 1)
        frame_height, frame_width = frame.shape[:2]
        hand_label = "NO HAND DETECTED"

        if not self._paused and self._hands is not None:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = self._hands.process(rgb)
                if result.multi_hand_landmarks:
                    hand = result.multi_hand_landmarks[0]
                    points = hand.landmark
                    mp.solutions.drawing_utils.draw_landmarks(
                        frame, hand, mp.solutions.hands.HAND_CONNECTIONS
                    )
                    hand_label = self._handle_hand(points, time.perf_counter())
                    index_tip = points[8]
                    cv2.circle(
                        frame,
                        (int(index_tip.x * frame_width), int(index_tip.y * frame_height)),
                        9, (255, 240, 80), -1
                    )
                else:
                    self._reset_gesture_state()
            except pyautogui.FailSafeException:
                self._paused = True
                self._reset_gesture_state()
                self.pause_button.setText("▶  Resume tracking")
                hand_label = "PAUSED • FAILSAFE CORNER REACHED"
                self.status.setText(
                    "Tracking paused by PyAutoGUI safety failsafe. Move the mouse away "
                    "from the screen corner, then resume."
                )
            except Exception as exc:
                self._paused = True
                self._reset_gesture_state()
                self.pause_button.setText("▶  Resume tracking")
                hand_label = "PAUSED • INPUT ERROR"
                self.status.setText(f"Gesture control paused after an input error: {exc}")
        elif self._paused:
            hand_label = "TRACKING PAUSED"

        cv2.putText(
            frame, hand_label, (18, 32), cv2.FONT_HERSHEY_SIMPLEX,
            0.62, (110, 230, 255), 2, cv2.LINE_AA
        )
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb_frame.data, frame_width, frame_height,
            rgb_frame.strides[0], QImage.Format.Format_RGB888
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(image).scaled(
                self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        if not self._paused:
            self.status.setText(
                f"{hand_label}  •  3 fingers: scroll  •  2 fingers: zoom  •  "
                f"Pinch thumb/index: click  •  Camera {self._camera_index}"
            )

    def showEvent(self, event):
        super().showEvent(event)
        # Reopening the window should restart the webcam after it was released.
        if self._capture is None:
            self._start_camera()

    def toggle_pause(self):
        self._paused = not self._paused
        self._reset_gesture_state()
        self.pause_button.setText(
            "▶  Resume tracking" if self._paused else "Ⅱ  Pause tracking"
        )
        self.status.setText(
            "Tracking paused. No mouse actions will be sent."
            if self._paused else "Tracking resumed. Show your hand to HOMER."
        )

    def _release_camera(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._hands is not None:
            self._hands.close()
            self._hands = None
        self._reset_gesture_state()

    def closeEvent(self, event):
        self._timer.stop()
        self._release_camera()
        super().closeEvent(event)
