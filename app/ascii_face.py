"""Reusable animated ASCII face for the native HOMER desktop UI.

The widget uses a small timer and plain text only: no images, audio analysis,
network access, or additional dependencies are required.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


_FACE_FRAMES: dict[str, tuple[tuple[str, ...], ...]] = {
    "IDLE": (
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |     \\___/     | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  -       -  \\  ",
            " |       ^       | ",
            " |     \\___/     | ",
            "  '-------------'  ",
        ),
    ),
    "LISTENING": (
        (
            "   .-----------.   ",
            "  /  O       O  \\  ",
            " |       ^       | ",
            " |     \\___/     | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |     \\___/     | ",
            "  '-------------'  ",
        ),
    ),
    "THINKING": (
        (
            "   .-----------.   ",
            "  /  o>      <o \\  ",
            " |       ^       | ",
            " |      . .      | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  <o      o> \\  ",
            " |       ^       | ",
            " |       ...     | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |        .      | ",
            "  '-------------'  ",
        ),
    ),
    "RESPONDING": (
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |      \\_/      | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |      \\___/    | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |      (___)    | ",
            "  '-------------'  ",
        ),
    ),
    "SPEAKING": (
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |       ___     | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |      (___)    | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |       ---     | ",
            "  '-------------'  ",
        ),
        (
            "   .-----------.   ",
            "  /  o       o  \\  ",
            " |       ^       | ",
            " |      \\___/    | ",
            "  '-------------'  ",
        ),
    ),
    "ERROR": (
        (
            "   .-----------.   ",
            "  /  x       x  \\  ",
            " |       ^       | ",
            " |      _____    | ",
            "  '-------------'  ",
        ),
    ),
    "OFFLINE": (
        (
            "   .-----------.   ",
            "  /  -       -  \\  ",
            " |       .       | ",
            " |      _____    | ",
            "  '-------------'  ",
        ),
    ),
}

_STATE_LABELS = {
    "IDLE": "H O M E R  /  STANDBY",
    "READY": "H O M E R  /  STANDBY",
    "LISTENING": "H O M E R  /  LISTENING",
    "THINKING": "H O M E R  /  THINKING",
    "RESPONDING": "H O M E R  /  RESPONDING",
    "SPEAKING": "H O M E R  /  SPEAKING",
    "ERROR": "H O M E R  /  ATTENTION",
    "OFFLINE": "H O M E R  /  OFFLINE",
}


def normalize_face_state(state: str) -> str:
    """Map public UI states to a supported ASCII-face state."""
    normalized = str(state or "IDLE").strip().upper()
    if normalized in {"READY", "STANDBY"}:
        return "IDLE"
    if normalized in _FACE_FRAMES:
        return normalized
    return "IDLE"


def render_ascii_face(state: str = "IDLE", frame_index: int = 0) -> str:
    """Return one deterministic ASCII animation frame for a given state."""
    normalized = normalize_face_state(state)
    frames = _FACE_FRAMES[normalized]
    try:
        index = int(frame_index)
    except (TypeError, ValueError):
        index = 0
    return "\n".join(frames[index % len(frames)])


class AsciiHomerFace(QWidget):
    """A lightweight animated ASCII face driven by HOMER's real UI state."""

    def __init__(self, parent: QWidget | None = None, *, compact: bool = False):
        super().__init__(parent)
        self.compact = compact
        self.current_state = "IDLE"
        self._frame_tick = 0

        self.setObjectName("asciiHomerFace")
        self.setMinimumSize(130, 66) if compact else self.setMinimumSize(300, 190)
        self.setStyleSheet(
            "QWidget#asciiHomerFace {"
            "background: #0b1424;"
            "border: 1px solid #24364d;"
            "border-radius: 14px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5) if compact else layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(2 if compact else 10)

        self.face_label = QLabel()
        self.face_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setBold(True)
        font.setPointSize(8 if compact else 17)
        self.face_label.setFont(font)
        self.face_label.setStyleSheet(
            "color: #b9e9f5; background: transparent; border: none;"
        )
        layout.addWidget(self.face_label, 1)

        self.state_label = QLabel()
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setStyleSheet(
            "color: #77cfe4; font-size: 8px; letter-spacing: 1px;"
            "background: transparent; border: none;"
        )
        if not compact:
            self.state_label.setStyleSheet(
                "color: #77cfe4; font-size: 10px; letter-spacing: 2px;"
                "background: transparent; border: none;"
            )
        layout.addWidget(self.state_label)

        self._timer = QTimer(self)
        self._timer.setInterval(140)
        self._timer.timeout.connect(self._advance_frame)
        self._timer.start()
        self._render()

    def set_state(self, state: str) -> None:
        """Change the face animation to match a real assistant state."""
        normalized = normalize_face_state(state)
        if normalized != self.current_state:
            self.current_state = normalized
            self._frame_tick = 0
        self._render()

    def _advance_frame(self) -> None:
        self._frame_tick += 1
        self._render()

    def _render(self) -> None:
        if self.current_state == "IDLE":
            # Hold the open-eye frame, then blink briefly every few seconds.
            frame_index = 1 if self._frame_tick % 24 in (0, 1) else 0
        elif self.current_state == "LISTENING":
            frame_index = (self._frame_tick // 3) % len(_FACE_FRAMES["LISTENING"])
        else:
            frame_index = self._frame_tick // 2
        self.face_label.setText(render_ascii_face(self.current_state, frame_index))
        self.state_label.setText(_STATE_LABELS[self.current_state])

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(150, 70) if self.compact else QSize(420, 260)
