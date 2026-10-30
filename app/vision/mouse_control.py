"""Camera-based hand tracking mouse for the HOMER desktop app.

Controls:
- Move the index fingertip to move the pointer.
- Pinch thumb and index finger to click once.
- Hold index + middle fingers up and move vertically to scroll.
- Use the Pause/Resume button or close this window to stop tracking.
"""
from __future__ import annotations

import math
import time

import cv2
import mediapipe as mp
import pyautogui
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget
)


class GestureMouseWindow(QMainWindow):
    """Opt-in webcam hand tracking that controls the system mouse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HOMER | Hand Mouse")
        self.setMinimumSize(800, 620)
        self.resize(960, 760)
        self._capture = None
        self._hands = None
        self._paused = False
        self._pinch_down = False
        self._last_scroll_y = None
        self._last_cursor = None
        self._last_frame_time = 0.0
        self._smooth = 0.32
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

        title = QLabel("HOMER / AIR MOUSE")
        title.setObjectName("title")
        subtitle = QLabel(
            "Index finger = move pointer   •   Thumb + index pinch = click   •   "
            "Index + middle fingers = scroll"
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
        self._timer.setInterval(15)
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
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.65,
                min_tracking_confidence=0.6,
            )
            self._timer.start()
            self.status.setText("Camera active. Keep your hand visible; close this window to stop.")
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

    def _move_pointer(self, landmark, frame_width, frame_height):
        screen_width, screen_height = pyautogui.size()
        # Ignore the outer 10% of the camera view to make edge control easier.
        margin = 0.10
        nx = min(1.0, max(0.0, (landmark.x - margin) / (1 - 2 * margin)))
        ny = min(1.0, max(0.0, (landmark.y - margin) / (1 - 2 * margin)))
        target = (int(nx * (screen_width - 1)), int(ny * (screen_height - 1)))
        if self._last_cursor is None:
            self._last_cursor = target
        else:
            self._last_cursor = (
                int(self._last_cursor[0] + self._smooth * (target[0] - self._last_cursor[0])),
                int(self._last_cursor[1] + self._smooth * (target[1] - self._last_cursor[1])),
            )
        pyautogui.moveTo(*self._last_cursor, duration=0)

    def _process_frame(self):
        if self._capture is None or not self._capture.isOpened():
            return
        ok, frame = self._capture.read()
        if not ok:
            self.status.setText("Could not read webcam frame.")
            return
        frame = cv2.flip(frame, 1)
        frame_height, frame_width = frame.shape[:2]
        hand_label = "No hand detected"

        if not self._paused and self._hands is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._hands.process(rgb)
            if result.multi_hand_landmarks:
                hand = result.multi_hand_landmarks[0]
                points = hand.landmark
                mp.solutions.drawing_utils.draw_landmarks(
                    frame, hand, mp.solutions.hands.HAND_CONNECTIONS
                )
                index_tip = points[8]
                thumb_tip = points[4]
                index_up = self._finger_up(points, 8, 6)
                middle_up = self._finger_up(points, 12, 10)
                ring_up = self._finger_up(points, 16, 14)
                pinch_distance = self._distance(thumb_tip, index_tip)
                pinching = pinch_distance < 0.045

                # Pinch is edge-triggered: one click per pinch, not repeated clicks.
                if pinching and not self._pinch_down:
                    pyautogui.click()
                self._pinch_down = pinching

                if index_up and middle_up and not ring_up and not pinching:
                    if self._last_scroll_y is not None:
                        delta = self._last_scroll_y - points[12].y
                        if abs(delta) > 0.008:
                            pyautogui.scroll(int(max(-4, min(4, delta * 100))))
                    self._last_scroll_y = points[12].y
                    hand_label = "SCROLL MODE"
                else:
                    self._last_scroll_y = None
                    if index_up and not pinching:
                        self._move_pointer(index_tip, frame_width, frame_height)
                        hand_label = "POINTER ACTIVE"
                    if pinching:
                        hand_label = "CLICK"
                cv2.circle(
                    frame,
                    (int(index_tip.x * frame_width), int(index_tip.y * frame_height)),
                    10, (255, 240, 80), -1
                )
            else:
                self._pinch_down = False
                self._last_scroll_y = None
        elif self._paused:
            hand_label = "TRACKING PAUSED"

        cv2.putText(
            frame, hand_label, (18, 32), cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (110, 230, 255), 2, cv2.LINE_AA
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
                f"{hand_label}  •  Pinch thumb and index to click. "
                f"Camera {self._camera_index}."
            )

    def toggle_pause(self):
        self._paused = not self._paused
        self._pinch_down = False
        self._last_scroll_y = None
        self.pause_button.setText("▶  Resume tracking" if self._paused else "Ⅱ  Pause tracking")
        self.status.setText("Tracking paused." if self._paused else "Tracking resumed.")

    def _release_camera(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self._hands is not None:
            self._hands.close()
            self._hands = None

    def closeEvent(self, event):
        self._timer.stop()
        self._release_camera()
        super().closeEvent(event)
