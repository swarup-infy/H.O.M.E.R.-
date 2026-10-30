"""Animated native HOMER voice-assistant interface."""

from __future__ import annotations

import math
import os
import sys
import threading
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

API_BASE_URL = os.getenv("HOMER_API_URL", "http://127.0.0.1:8000")


class AnimatedHomerCore(QWidget):
    """Paint an animated energy core around the user's HOMER logo."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.phase = 0.0
        self.mode = "READY"
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.logo = QPixmap(str(Path(__file__).parent / "assets" / "homer_core.png"))

    def set_mode(self, mode: str) -> None:
        self.mode = mode.upper()
        self.update()

    @Slot()
    def _tick(self) -> None:
        self.phase = (self.phase + 1.25) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#080d19"))

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 4
        radius = min(w, h) * 0.34
        pulse = 1.0 + 0.025 * math.sin(math.radians(self.phase * 2.0))
        glow_radius = radius * 1.65 * pulse

        glow = QRadialGradient(cx, cy, glow_radius)
        glow.setColorAt(0.0, QColor(0, 176, 255, 48))
        glow.setColorAt(0.48, QColor(0, 111, 255, 18))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(cx - glow_radius, cy - glow_radius, glow_radius * 2, glow_radius * 2))

        # Thin rotating orbital rings.
        for index, factor in enumerate((1.0, 1.18, 1.38)):
            ring_radius = radius * factor * pulse
            hue = QColor("#42e8ff") if index != 1 else QColor("#8b7bff")
            hue.setAlpha(170 if index == 0 else 100)
            pen = QPen(hue, 1.4 if index == 0 else 1.0)
            pen.setStyle(Qt.PenStyle.DashLine if index == 1 else Qt.PenStyle.SolidLine)
            pen.setDashPattern([3.0, 7.0] if index == 1 else [1.0, 1.0])
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(self.phase * (1 if index % 2 == 0 else -0.65))
            painter.drawEllipse(QRectF(-ring_radius, -ring_radius, ring_radius * 2, ring_radius * 2))
            # Orbit nodes.
            for angle in (0, 120, 240) if index == 0 else (45, 225):
                painter.save()
                painter.rotate(angle)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#b7faff") if index == 0 else QColor("#a79aff"))
                painter.drawEllipse(QRectF(ring_radius - 3, -3, 6, 6))
                painter.restore()
            painter.restore()

        # Subtle circuit traces extending away from the core.
        trace_pen = QPen(QColor(42, 205, 255, 78), 1.2)
        painter.setPen(trace_pen)
        for direction in (-1, 1):
            for offset in (0.0, 20.0, 40.0):
                start_x = cx + direction * (radius * 1.05)
                end_x = cx + direction * (radius * 1.65)
                y = cy + offset - 20
                path = QPainterPath()
                path.moveTo(start_x, y)
                path.lineTo(start_x + direction * 18, y)
                path.lineTo(start_x + direction * 31, y + direction * 13)
                path.lineTo(end_x, y + direction * 13)
                painter.drawPath(path)
                painter.setBrush(QColor("#43dfff"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(end_x - 2, y + direction * 11, 4, 4))
                painter.setPen(trace_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        # Logo is kept crisp and contained inside the innermost ring.
        logo_size = radius * 1.42
        logo_rect = QRectF(cx - logo_size / 2, cy - logo_size / 2, logo_size, logo_size)
        if not self.logo.isNull():
            pixmap = self.logo.scaled(
                int(logo_size), int(logo_size),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                int(cx - pixmap.width() / 2),
                int(cy - pixmap.height() / 2),
                pixmap,
            )
        else:
            painter.setPen(QPen(QColor("#57eaff"), 2))
            painter.setBrush(QColor(10, 25, 48, 220))
            painter.drawEllipse(logo_rect)
            painter.setPen(QColor("#b9f8ff"))
            painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
            painter.drawText(logo_rect, Qt.AlignmentFlag.AlignCenter, "H")

        # Moving waveform bars below the core.
        bar_y = min(h - 24, cy + radius * 1.62)
        for i in range(31):
            x = cx - 93 + i * 6.2
            wave = abs(math.sin(math.radians(self.phase * 2 + i * 13)))
            height = 3 + wave * (8 if self.mode == "LISTENING" else 5)
            color = QColor("#55e9ff")
            color.setAlpha(210 - int(abs(15 - i) * 5))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, bar_y - height / 2, 3, height), 1.5, 1.5)

        painter.end()


class VoiceTask(QObject):
    """Run voice and API work in a worker thread."""

    state = Signal(str)
    transcript = Signal(str)
    reply = Signal(str)
    error = Signal(str)
    finished = Signal()
    mode_command = Signal(str)

    def __init__(self, mode: str, text: str = "", speak_reply: bool = True):
        super().__init__()
        self.mode = mode
        self.text = text
        self.speak_reply = speak_reply
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def _ask(self, message: str) -> str:
        response = httpx.post(f"{API_BASE_URL}/chat", json={"message": message}, timeout=90.0)
        response.raise_for_status()
        return str(response.json().get("reply", "")).strip() or "I received an empty response."

    def _speak(self, answer: str) -> None:
        if self.speak_reply:
            self.state.emit("SPEAKING")
            from app.voice.speaker import speak
            speak(answer)

    @Slot()
    def run(self) -> None:
        try:
            if self.mode == "always_listen":
                self._run_always_listen()
            else:
                message = self.text.strip()
                if self.mode == "listen":
                    message = self._listen_once()
                    self.transcript.emit(message)
                if not message:
                    raise RuntimeError("Type a message or use the microphone first.")
                self.state.emit("THINKING")
                answer = self._ask(message)
                self.reply.emit(answer)
                self._speak(answer)
        except httpx.ConnectError:
            self.error.emit("Cannot reach HOMER's API. Start the FastAPI server on 127.0.0.1:8000.")
        except httpx.TimeoutException:
            self.error.emit("HOMER took too long to respond. Please try again.")
        except httpx.HTTPStatusError as exc:
            self.error.emit(f"The HOMER API returned HTTP {exc.response.status_code}. Check the server terminal.")
        except Exception as exc:
            self.error.emit(str(exc) or "An unexpected voice-assistant error occurred.")
        finally:
            self.state.emit("READY")
            self.finished.emit()

    def _recognizer(self):
        try:
            import speech_recognition as sr
        except ImportError as exc:
            raise RuntimeError("Install voice support: python -m pip install -r requirements-voice.txt") from exc
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8
        return sr, recognizer

    def _listen_once(self) -> str:
        sr, recognizer = self._recognizer()
        self.state.emit("LISTENING")
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.4)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=18)
            self.state.emit("THINKING")
            return recognizer.recognize_google(audio, language="en-IN").strip()
        except sr.WaitTimeoutError as exc:
            raise RuntimeError("I didn't hear anything. Try again.") from exc
        except sr.UnknownValueError as exc:
            raise RuntimeError("I couldn't understand that. Please speak clearly.") from exc
        except sr.RequestError as exc:
            raise RuntimeError("Speech recognition service is unavailable. Check your internet connection.") from exc

    @staticmethod
    def _parse_mode_command(message: str) -> str | None:
        """Recognize explicit navigation commands without calling the LLM."""
        import re
        phrase = re.sub(r"[^a-z0-9 ]+", " ", message.lower())
        phrase = " ".join(phrase.split())
        text_commands = {
            "switch to text mode", "open text mode", "go to text mode",
            "text mode", "open text assistant", "switch to typing mode",
        }
        gesture_commands = {
            "switch to gesture mode", "open gesture mode", "go to gesture mode",
            "gesture mode", "enable gesture controls", "open gesture controls",
        }
        if phrase in text_commands:
            return "text"
        if phrase in gesture_commands:
            return "gesture"
        return None

    def _run_always_listen(self) -> None:
        sr, recognizer = self._recognizer()
        self.state.emit("LISTENING")
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                while not self._stop_event.is_set():
                    try:
                        audio = recognizer.listen(source, timeout=1, phrase_time_limit=12)
                    except sr.WaitTimeoutError:
                        continue
                    if self._stop_event.is_set():
                        break
                    self.state.emit("THINKING")
                    try:
                        message = recognizer.recognize_google(audio, language="en-IN").strip()
                    except sr.UnknownValueError:
                        self.state.emit("LISTENING")
                        continue
                    except sr.RequestError as exc:
                        raise RuntimeError("Speech recognition service is unavailable. Check your internet connection.") from exc
                    if not message:
                        self.state.emit("LISTENING")
                        continue
                    self.transcript.emit(message)
                    command = self._parse_mode_command(message)
                    if command:
                        self.mode_command.emit(command)
                        return
                    answer = self._ask(message)
                    self.reply.emit(answer)
                    self._speak(answer)
                    if not self._stop_event.is_set():
                        self.state.emit("LISTENING")
        finally:
            self.state.emit("READY")


class VoiceAssistantWindow(QMainWindow):
    """Full-screen-feeling, animated HOMER voice experience."""

    mode_switch = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.thread: QThread | None = None
        self.worker: VoiceTask | None = None
        self._auto_listen_started = False
        self.setWindowTitle("HOMER | Voice Interface")
        self.resize(1120, 780)
        self.setMinimumSize(820, 650)
        self.setStyleSheet("""
            QMainWindow, QWidget#voiceRoot { background: #080d19; color: #edf7ff; }
            QLabel { background: transparent; }
            QLabel#eyebrow { color: #4ee7ff; font-size: 11px; font-weight: 700; letter-spacing: 3px; }
            QLabel#title { color: #f1f8ff; font-size: 34px; font-weight: 700; letter-spacing: 5px; }
            QLabel#subtitle { color: #8398b8; font-size: 12px; }
            QLabel#state { color: #55edff; font-size: 12px; font-weight: 700; letter-spacing: 3px; }
            QLabel#transcript { color: #c4d8f3; font-size: 13px; }
            QFrame#panel { background: #0d1728; border: 1px solid #203653; border-radius: 18px; }
            QLineEdit { background: #101e32; border: 1px solid #294765; border-radius: 13px; padding: 14px 16px; color: #f4f9ff; selection-background-color: #147ca7; }
            QLineEdit:focus { border: 1px solid #3bdcf4; }
            QPushButton { background: #11263b; border: 1px solid #2b526d; border-radius: 12px; padding: 12px 17px; color: #d9f7ff; font-weight: 600; }
            QPushButton:hover { background: #173751; border-color: #42dff7; }
            QPushButton:disabled { color: #62758e; background: #111a28; border-color: #1c2a3b; }
            QPushButton#mic { background: #073b52; border: 1px solid #35def4; color: #e8fdff; font-size: 14px; padding: 15px 22px; }
            QPushButton#mic:hover { background: #0b526c; }
            QPushButton#close { color: #8da1bd; background: transparent; border: 1px solid #24364d; padding: 7px 12px; }
            QCheckBox { color: #9fb4d0; spacing: 8px; }
            QCheckBox::indicator { width: 15px; height: 15px; }
        """)

        root = QWidget()
        root.setObjectName("voiceRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)

        header = QHBoxLayout()
        brand = QLabel("H O M E R")
        brand.setObjectName("eyebrow")
        self.connection = QLabel("● LOCAL API ASSISTANT")
        self.connection.setObjectName("subtitle")
        close_button = QPushButton("←  BACK")
        close_button.setObjectName("close")
        close_button.clicked.connect(self.close)
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(self.connection)
        header.addSpacing(18)
        header.addWidget(close_button)
        layout.addLayout(header)

        title = QLabel("VOICE INTERFACE")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("ALWAYS-ON VOICE MODE • MICROPHONE STATUS ALWAYS VISIBLE")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.core = AnimatedHomerCore()
        layout.addWidget(self.core, 1)

        self.state_label = QLabel("●  READY")
        self.state_label.setObjectName("state")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label = QLabel("Tap the microphone and speak to HOMER.")
        self.transcript_label.setObjectName("transcript")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setWordWrap(True)
        layout.addWidget(self.state_label)
        layout.addWidget(self.transcript_label)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(10)

        self.reply_label = QLabel("HOMER's response will appear here.")
        self.reply_label.setWordWrap(True)
        self.reply_label.setMinimumHeight(28)
        self.reply_label.setMaximumHeight(72)
        self.reply_label.setStyleSheet("color: #b4c9e4; font-size: 12px;")
        panel_layout.addWidget(self.reply_label)

        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Or type a message to HOMER...")
        self.input.returnPressed.connect(self.send_text)
        self.send_button = QPushButton("SEND  ↗")
        self.send_button.clicked.connect(self.send_text)
        self.mic_button = QPushButton("◉  LISTEN ONCE")
        self.mic_button.setObjectName("mic")
        self.mic_button.clicked.connect(self.listen)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(self.send_button)
        panel_layout.addLayout(input_row)

        controls = QHBoxLayout()
        self.always_button = QPushButton("◉  START ALWAYS LISTENING")
        self.always_button.setObjectName("mic")
        self.always_button.clicked.connect(self.toggle_always_listening)
        self.voice_reply = QCheckBox("Speak replies aloud")
        self.voice_reply.setChecked(True)
        self.voice_reply.setToolTip("Use your installed Windows text-to-speech voice.")
        self.clear_button = QPushButton("CLEAR DISPLAY")
        self.clear_button.clicked.connect(self.clear_display)
        controls.addWidget(self.mic_button)
        controls.addWidget(self.always_button)
        controls.addWidget(self.voice_reply)
        controls.addStretch()
        controls.addWidget(self.clear_button)
        panel_layout.addLayout(controls)

        layout.addWidget(panel)

        footer = QLabel("HOMER CORE  /  GROQ INTELLIGENCE  /  LOCAL DESKTOP")
        footer.setObjectName("eyebrow")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("font-size: 9px; color: #526b89;")
        layout.addWidget(footer)

    def _start_task(self, mode: str, text: str = "") -> None:
        if self.thread is not None and self.thread.isRunning():
            return

        self.input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.mic_button.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.always_button.setEnabled(True)
        self._set_state("LISTENING" if mode in ("listen", "always_listen") else "THINKING")

        self.thread = QThread(self)
        self.worker = VoiceTask(mode, text, self.voice_reply.isChecked())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.state.connect(self._set_state)
        self.worker.mode_command.connect(self._on_mode_command)
        self.worker.transcript.connect(self._show_transcript)
        self.worker.reply.connect(self._show_reply)
        self.worker.error.connect(self._show_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._task_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def toggle_always_listening(self) -> None:
        """Start or stop continuous microphone listening."""
        if self.worker is not None and self.thread is not None and self.thread.isRunning():
            if self.worker.mode == "always_listen":
                self.worker.stop()
                self.always_button.setText("STOPPING…")
                self.always_button.setEnabled(False)
            return
        self.always_button.setText("■  STOP LISTENING")
        self.transcript_label.setText(
            "Always-listening is active. Click STOP LISTENING to pause microphone capture."
        )
        self._start_task("always_listen")

    @Slot(str)
    def _on_mode_command(self, mode: str) -> None:
        """Pause voice capture and hand navigation to the desktop shell."""
        self.transcript_label.setText(f"Switching to {mode} mode…")
        if self.worker is not None:
            self.worker.stop()
        self.mode_switch.emit(mode)

    def listen(self) -> None:
        self.transcript_label.setText("Microphone is opening… speak after the listening indicator appears.")
        self._start_task("listen")

    def send_text(self) -> None:
        message = self.input.text().strip()
        if not message:
            return
        self.transcript_label.setText(f"YOU  ›  {message}")
        self.input.clear()
        self._start_task("text", message)

    @Slot(str)
    def _set_state(self, state: str) -> None:
        self.core.set_mode(state)
        self.state_label.setText(f"●  {state}")
        color = {
            "READY": "#55edff",
            "LISTENING": "#ff668e",
            "THINKING": "#a89bff",
            "SPEAKING": "#73f6b0",
        }.get(state, "#55edff")
        self.state_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700; letter-spacing: 3px;")

    @Slot(str)
    def _show_transcript(self, text: str) -> None:
        self.transcript_label.setText(f"YOU  ›  {text}")

    @Slot(str)
    def _show_reply(self, text: str) -> None:
        self.reply_label.setText(f"HOMER  ›  {text}")
        self.transcript_label.setText("Message processed. HOMER has responded.")

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self.reply_label.setText(f"NOTICE  ›  {message}")
        self.transcript_label.setText("Check the message above and try again.")
        self._set_state("READY")

    @Slot()
    def _task_finished(self) -> None:
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.mic_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.always_button.setEnabled(True)
        self.always_button.setText("◉  START ALWAYS LISTENING")
        if self.state_label.text().endswith("THINKING") or self.state_label.text().endswith("SPEAKING") or self.state_label.text().endswith("LISTENING"):
            self._set_state("READY")
        self.input.setFocus()
        self.worker = None
        self.thread = None

    def clear_display(self) -> None:
        self.transcript_label.setText("HOMER is ready.")
        self.reply_label.setText("HOMER's response will appear here.")
        self._set_state("READY")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._auto_listen_started:
            self._auto_listen_started = True
            QTimer.singleShot(900, self.toggle_always_listening)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None:
            self.worker.stop()
        if self.thread is not None and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(1500)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("HOMER Voice Assistant")
    window = VoiceAssistantWindow()
    window.show()
    sys.exit(app.exec())
