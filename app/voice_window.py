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
        asset_dir = Path(__file__).parent / "assets"
        # Prefer the newer artwork; fall back to the original filename.
        logo_path = asset_dir / "Homer 4.png"
        if not logo_path.is_file():
            logo_path = asset_dir / "homer_core.png"
        self.logo = QPixmap(str(logo_path))

    def set_mode(self, mode: str) -> None:
        self.mode = mode.upper()
        self.update()

    @Slot()
    def _tick(self) -> None:
        self.phase = (self.phase + (2.8 if self.mode == "SPEAKING" else 1.25)) % 360
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

        # Electric arcs overlap the core while HOMER is speaking.
        if self.mode in ("SPEAKING", "LISTENING"):
            intensity = 1.0 if self.mode == "SPEAKING" else 0.4
            for arc_index in range(9 if intensity == 1.0 else 4):
                angle = self.phase * (1.4 + arc_index * 0.13) + arc_index * 47
                arc_radius = radius * (0.43 + (arc_index % 4) * 0.14)
                painter.save()
                painter.translate(cx, cy)
                painter.rotate(angle)
                path = QPainterPath()
                path.moveTo(arc_radius * 0.5, 0)
                for step in range(1, 8):
                    distance = arc_radius * (0.5 + step * 0.075)
                    jitter = math.sin(math.radians(self.phase * 5 + arc_index * 67 + step * 53)) * radius * 0.08
                    path.lineTo(distance, jitter)
                painter.setPen(QPen(QColor(90, 238, 255, int(220 * intensity)), 1.2 + intensity))
                painter.drawPath(path)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(180, 250, 255, int(230 * intensity)))
                painter.drawEllipse(QRectF(arc_radius * 1.06 - 2, -2, 4, 4))
                painter.restore()

            if self.mode == "SPEAKING":
                # Short, branching lightning bolts flash across the logo itself.
                for bolt in range(12):
                    angle = math.radians(bolt * 30 + self.phase * 2.8)
                    inner = radius * (0.12 + 0.08 * (bolt % 3))
                    outer = radius * (0.48 + 0.14 * (bolt % 2))
                    x1, y1 = cx + math.cos(angle) * inner, cy + math.sin(angle) * inner
                    x2, y2 = cx + math.cos(angle) * outer, cy + math.sin(angle) * outer
                    bolt_path = QPainterPath()
                    bolt_path.moveTo(x1, y1)
                    for segment in range(1, 5):
                        t = segment / 5
                        bx = x1 + (x2 - x1) * t + math.sin(math.radians(self.phase * 7 + bolt * 31 + segment * 83)) * radius * 0.07
                        by = y1 + (y2 - y1) * t + math.cos(math.radians(self.phase * 6 + bolt * 43 + segment * 61)) * radius * 0.07
                        bolt_path.lineTo(bx, by)
                    bolt_path.lineTo(x2, y2)
                    painter.setPen(QPen(QColor(0, 130, 255, 105), 5))
                    painter.drawPath(bolt_path)
                    painter.setPen(QPen(QColor(145, 250, 255, 235), 1.5))
                    painter.drawPath(bolt_path)

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

        # Animated starfield and holographic floor rings fill the widescreen scene.
        for i in range(58):
            seed_x = (i * 137.5) % max(1, w)
            seed_y = (i * 83.7) % max(1, h)
            drift = (self.phase * (0.16 + (i % 4) * 0.07))
            px = (seed_x + drift * (1 if i % 2 else -1)) % max(1, w)
            py = (seed_y + math.sin(math.radians(self.phase + i * 19)) * 9) % max(1, h)
            alpha = 70 + int(100 * abs(math.sin(math.radians(self.phase * 1.7 + i * 23))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(45, 198, 255, alpha))
            size = 1.2 + (i % 3) * 0.55
            painter.drawEllipse(QRectF(px, py, size, size))

        floor_y = h * 0.83
        painter.save()
        painter.translate(cx, floor_y)
        for i in range(7):
            floor_width = min(w * 0.82, radius * (2.7 + i * 0.48))
            floor_height = 12 + i * 5
            floor_color = QColor("#19cfff" if i % 2 == 0 else "#e9a94b")
            floor_color.setAlpha(max(24, 95 - i * 9))
            painter.setPen(QPen(floor_color, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(-floor_width / 2, -floor_height / 2, floor_width, floor_height))
        painter.restore()

        # A softly animated scanning beam sweeps through the core.
        scan_y = cy - radius + (2 * radius) * ((self.phase % 180) / 180.0)
        scan_color = QColor(50, 225, 255, 34)
        painter.setPen(QPen(scan_color, 2.0))
        painter.drawLine(int(cx - radius * 0.88), int(scan_y), int(cx + radius * 0.88), int(scan_y))

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

    def _speak(self, answer: str, listen_for_stop: bool = False) -> str | None:
        """Speak a reply while listening for stop and response-length commands."""
        self.state.emit("SPEAKING")
        monitor_stop = threading.Event()
        interruption = {"command": None}
        monitor_thread = None

        # Reset cancellation BEFORE the microphone monitor starts. Previously
        # speak() cleared this flag after the monitor started, which could erase
        # a fast "stop" command before the TTS worker saw it.
        from app.voice.speaker import reset_stop_request
        reset_stop_request()

        if listen_for_stop:
            def monitor_for_stop() -> None:
                try:
                    import speech_recognition as sr
                    stop_recognizer = sr.Recognizer()
                    stop_recognizer.dynamic_energy_threshold = True
                    stop_recognizer.pause_threshold = 0.35
                    # Open the microphone separately while the speech engine is playing.
                    with sr.Microphone() as stop_source:
                        stop_recognizer.adjust_for_ambient_noise(stop_source, duration=0.2)
                        while not monitor_stop.is_set() and not self._stop_event.is_set():
                            try:
                                clip = stop_recognizer.listen(
                                    stop_source, timeout=0.35, phrase_time_limit=2
                                )
                            except sr.WaitTimeoutError:
                                continue
                            if monitor_stop.is_set() or self._stop_event.is_set():
                                break
                            try:
                                phrase = stop_recognizer.recognize_google(
                                    clip, language="en-IN"
                                ).strip().lower()
                            except (sr.UnknownValueError, sr.RequestError):
                                continue
                            normalized = " ".join(phrase.replace("-", " ").split())
                            words = set(normalized.split())
                            command = None
                            if "stop" in words or normalized in {"homer stop", "stop speaking", "be quiet"}:
                                command = "stop"
                            elif "short" in words and ("answer" in words or "response" in words):
                                command = "short"
                            elif "summarize" in words or "summary" in words or "give me a summary" in normalized:
                                command = "summary"
                            elif ("in detail" in normalized or "detailed answer" in normalized
                                  or "long answer" in normalized or "explain more" in normalized):
                                command = "detail"
                            if command:
                                interruption["command"] = command
                                labels = {"stop": "Stop command detected.", "short": "Switching to a short answer.",
                                          "summary": "Preparing a summary.", "detail": "Preparing a detailed answer."}
                                self.transcript.emit(labels[command])
                                from app.voice.speaker import stop_speaking
                                stop_speaking()
                                break
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "HOMER's stop-word listener could not access the microphone."
                    )

            monitor_thread = threading.Thread(
                target=monitor_for_stop, name="HOMER-Stop-Listener", daemon=True
            )
            monitor_thread.start()

        try:
            from app.voice.speaker import speak
            speak(answer)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("HOMER could not speak this reply")
            self.error.emit(
                "I received the answer, but voice playback failed. "
                "Check Windows text-to-speech voices and the server terminal."
            )
        finally:
            monitor_stop.set()
            if monitor_thread is not None:
                monitor_thread.join(timeout=1.0)
        return interruption["command"]

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
        if phrase in text_commands or (
            "text mode" in phrase
            or "text assistant" in phrase
            or "typing mode" in phrase
        ):
            return "text"
        if phrase in gesture_commands or (
            "gesture mode" in phrase
            or "gesture controls" in phrase
        ):
            return "gesture"
        return None

    def _run_always_listen(self) -> None:
        sr, recognizer = self._recognizer()
        self.state.emit("LISTENING")
        try:
            while not self._stop_event.is_set():
                # Close the command-listening microphone before opening the stop-word
                # listener during playback; this avoids competing microphone streams.
                try:
                    with sr.Microphone() as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.25)
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
                interruption = self._speak(answer, listen_for_stop=True)
                # Spoken control commands can interrupt the current reply and request
                # a different length without making the user repeat the original question.
                while interruption in {"short", "summary", "detail"} and not self._stop_event.is_set():
                    instruction = {
                        "short": "Answer my previous question in 1–3 short sentences. Be direct.",
                        "summary": "Summarize your previous answer in a few concise sentences, keeping only the key points.",
                        "detail": "Now give me a more detailed explanation of my previous question, with useful examples and clear steps where appropriate.",
                    }[interruption]
                    self.state.emit("THINKING")
                    answer = self._ask(f"{instruction} My original question was: {message}")
                    self.reply.emit(answer)
                    interruption = self._speak(answer, listen_for_stop=True)
                if not self._stop_event.is_set():
                    self.state.emit("LISTENING")
        finally:
            self.state.emit("READY")


class VoiceAssistantWindow(QMainWindow):
    """Immersive, full-screen HOMER interface with two bottom controls."""

    mode_switch = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("HOMER")
        self.setMinimumSize(760, 520)
        self.setStyleSheet("""
            QMainWindow, QWidget#voiceRoot { background: #020712; color: #eafaff; }
            QLabel { background: transparent; }
            QPushButton#bottomControl {
                min-height: 64px; max-height: 76px; min-width: 230px;
                border-radius: 34px; padding: 10px 30px;
                color: #eafaff; background: rgba(5, 24, 45, 225);
                border: 2px solid #18dfff; font-size: 15px; font-weight: 700;
            }
            QPushButton#bottomControl:hover { background: rgba(8, 62, 91, 240); }
            QPushButton#listenControl { border-color: #19dfff; }
            QPushButton#listenControl[active="true"] { border-color: #ff477e; color: #fff0f5; }
            QPushButton#chatControl { border-color: #9a6bff; }
        """)
        self.thread: QThread | None = None
        self.worker: VoiceTask | None = None
        self._auto_listen_started = False
        self._listening_requested = False

        root = QWidget()
        root.setObjectName("voiceRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.setSpacing(0)

        # The status remains visually subtle; no title or instructional text.
        self.state_label = QLabel("")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setStyleSheet("color: #55edff; font-size: 11px; letter-spacing: 4px;")
        layout.addWidget(self.state_label)
        layout.addStretch(1)

        self.core = AnimatedHomerCore()
        layout.addWidget(self.core, 8)

        self.transcript_label = QLabel("")
        self.transcript_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setMaximumHeight(42)
        self.transcript_label.setStyleSheet("color: #b9eaff; font-size: 12px;")
        layout.addWidget(self.transcript_label)
        layout.addStretch(1)

        controls = QHBoxLayout()
        controls.setSpacing(26)
        controls.addStretch(1)

        self.always_button = QPushButton("◉   LISTENING OFF")
        self.always_button.setObjectName("bottomControl")
        self.always_button.setProperty("active", False)
        self.always_button.setToolTip("Turn continuous listening on or off")
        self.always_button.clicked.connect(self.toggle_always_listening)

        self.chat_button = QPushButton("▢   SWITCH TO CHAT")
        self.chat_button.setObjectName("bottomControl")
        self.chat_button.setProperty("active", False)
        self.chat_button.setToolTip("Switch to the text chat interface")
        self.chat_button.clicked.connect(lambda: self.mode_switch.emit("text"))

        controls.addWidget(self.always_button)
        controls.addWidget(self.chat_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.input = QLineEdit()
        self.send_button = QPushButton()
        self.mic_button = QPushButton()
        self.clear_button = QPushButton()
        self.voice_reply = QCheckBox()
        self.voice_reply.setChecked(True)
        self.input.hide()
        self.send_button.hide()
        self.mic_button.hide()
        self.clear_button.hide()
        self.voice_reply.hide()

    def _start_task(self, mode: str, text: str = "") -> None:
        if self.thread is not None and self.thread.isRunning():
            return
        self._listening_requested = mode == "always_listen"
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
        """Use the single primary control to start or stop continuous listening."""
        if self.worker is not None and self.thread is not None and self.thread.isRunning():
            if self.worker.mode == "always_listen":
                self._listening_requested = False
                self.worker.stop()
                self.always_button.setText("◌   TURNING OFF")
                self.always_button.setEnabled(False)
            return
        self._listening_requested = True
        self.always_button.setText("■   LISTENING ON")
        self.always_button.setProperty("active", True)
        self.always_button.style().unpolish(self.always_button)
        self.always_button.style().polish(self.always_button)
        self._start_task("always_listen")

    @Slot(str)
    def _on_mode_command(self, mode: str) -> None:
        self.transcript_label.setText(f"Switching to {mode}…")
        if self.worker is not None:
            self.worker.stop()
        self.mode_switch.emit(mode)

    def listen(self) -> None:
        self._start_task("listen")

    def send_text(self) -> None:
        message = self.input.text().strip()
        if message:
            self.input.clear()
            self._start_task("text", message)

    def clear_display(self) -> None:
        self.transcript_label.clear()

    @Slot(str)
    def _set_state(self, state: str) -> None:
        self.core.set_mode(state)
        self.state_label.setText("• " + state + " •")
        color = {"READY": "#55edff", "LISTENING": "#ff668e",
                 "THINKING": "#a89bff", "SPEAKING": "#73f6b0"}.get(state, "#55edff")
        self.state_label.setStyleSheet(f"color: {color}; font-size: 11px; letter-spacing: 4px;")

    @Slot(str)
    def _show_transcript(self, text: str) -> None:
        self.transcript_label.setText(text)

    @Slot(str)
    def _show_reply(self, text: str) -> None:
        self.transcript_label.setText(text)

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self.transcript_label.setText(message)
        self._set_state("READY")

    @Slot()
    def _task_finished(self) -> None:
        self.input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.mic_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        self.always_button.setEnabled(True)
        if self._listening_requested:
            self.always_button.setText("■   LISTENING ON")
            self.always_button.setProperty("active", True)
        else:
            self.always_button.setText("◉   LISTENING OFF")
            self.always_button.setProperty("active", False)
            self._set_state("READY")
        self.always_button.style().unpolish(self.always_button)
        self.always_button.style().polish(self.always_button)
        self.worker = None
        self.thread = None

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
    app.setApplicationName("HOMER")
    window = VoiceAssistantWindow()
    window.showMaximized()
    sys.exit(app.exec())
