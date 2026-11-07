"""Animated native HOMER voice-assistant interface."""

from __future__ import annotations

import html
import math
import os
import sys
import threading
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QPropertyAnimation, QThread, QTimer, Signal, Slot, Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGraphicsOpacityEffect,
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


class WordRevealLabel(QLabel):
    """Reveal recognized speech and assistant replies one animated word at a time."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumHeight(34)
        self.setMaximumHeight(66)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet("color: #b9eaff; font-size: 11pt;")
        self._words: list[str] = []
        self._visible_words = 0
        self._timer = QTimer(self)
        self._timer.setInterval(82)
        self._timer.timeout.connect(self._reveal_next)
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation.setDuration(150)

    def reveal(self, text: str) -> None:
        self._timer.stop()
        self._animation.stop()
        self._words = str(text).split()
        self._visible_words = 0
        self.setText("")
        self._opacity.setOpacity(1.0)
        if not self._words:
            return
        self._timer.start()
        self._reveal_next()

    def clear_text(self) -> None:
        self._timer.stop()
        self._animation.stop()
        self._words = []
        self._visible_words = 0
        self.setText("")
        self._opacity.setOpacity(1.0)

    def _reveal_next(self) -> None:
        if self._visible_words >= len(self._words):
            self._timer.stop()
            return
        previous = " ".join(html.escape(word) for word in self._words[:self._visible_words])
        current = html.escape(self._words[self._visible_words])
        prefix = f"{previous} " if previous else ""
        self.setText(f'{prefix}<span style="color:#ffffff; font-size:13pt; font-weight:700;">{current}</span>')
        self._visible_words += 1
        self._opacity.setOpacity(0.28)
        self._animation.setStartValue(0.28)
        self._animation.setEndValue(1.0)
        self._animation.start()
        if self._visible_words >= len(self._words):
            self._timer.stop()


class AnimatedHomerCore(QWidget):
    """Paint an animated energy core around the user's HOMER logo."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.phase = 0.0
        self.mode = "READY"
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._tick)
        # Animate at a lighter idle cadence; use a faster cadence only when active.
        self.timer.start()
        asset_dir = Path(__file__).parent / "assets"
        # Prefer the newer artwork; fall back to the original filename.
        logo_path = asset_dir / "Homer 4.png"
        if not logo_path.is_file():
            logo_path = asset_dir / "homer_core.png"
        self.logo = QPixmap(str(logo_path))
        self.scaled_logo = QPixmap()
        self._refresh_scaled_logo()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_scaled_logo()

    def _refresh_scaled_logo(self) -> None:
        if self.logo.isNull():
            self.scaled_logo = QPixmap()
            return
        side = max(1, int(min(self.width(), self.height()) * 0.70))
        self.scaled_logo = self.logo.scaled(
            side, side,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def set_mode(self, mode: str) -> None:
        self.mode = mode.upper()
        self.timer.setInterval(28 if self.mode in {"SPEAKING", "RESPONDING"} else 45 if self.mode == "LISTENING" else 80)
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.timer.isActive():
            self.timer.start()

    def hideEvent(self, event) -> None:
        self.timer.stop()
        super().hideEvent(event)

    @Slot()
    def _tick(self) -> None:
        self.phase = (self.phase + (4.0 if self.mode in {"SPEAKING", "RESPONDING"} else 2.2 if self.mode == "LISTENING" else 0.8)) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 10
        unit = min(w, h)
        painter.fillRect(self.rect(), QColor("#02050b"))
        active = self.mode in {"SPEAKING", "RESPONDING"}
        listening = self.mode == "LISTENING"

        halo_radius = unit * (0.47 if active else 0.43)
        halo = QRadialGradient(cx, cy, halo_radius)
        halo.setColorAt(0.0, QColor(0, 115, 255, 25))
        halo.setColorAt(0.68, QColor(0, 80, 180, 12))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(cx-halo_radius, cy-halo_radius, halo_radius*2, halo_radius*2))

        pulse = 1.0 + (0.012 if active else 0.004) * math.sin(self.phase * 0.8)
        image_side = unit * 0.68 * pulse
        image_rect = QRectF(cx-image_side/2, cy-image_side/2, image_side, image_side)

        for factor, alpha in ((0.405, 65), (0.455, 35)):
            radius = unit * factor
            painter.setPen(QPen(QColor(38, 174, 255, alpha), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx-radius, cy-radius, radius*2, radius*2))

        # A radial spectrum responds whenever HOMER answers or speaks.
        if active or listening:
            count = 72
            base_radius = unit * 0.405
            for i in range(count):
                angle = (2 * math.pi * i / count) + self.phase * (0.10 if active else -0.035)
                harmonic = (0.48 + 0.24 * math.sin(self.phase * 1.7 + i * 0.37)
                            + 0.16 * math.sin(self.phase * 2.9 - i * 0.19)
                            + 0.12 * math.sin(self.phase * 4.1 + i * 0.73))
                envelope = max(0.08, min(1.0, harmonic))
                length = unit * (0.018 + envelope * (0.055 if active else 0.022))
                x1, y1 = cx + math.cos(angle)*base_radius, cy + math.sin(angle)*base_radius
                x2, y2 = cx + math.cos(angle)*(base_radius+length), cy + math.sin(angle)*(base_radius+length)
                alpha = int((175 if active else 95) * envelope)
                color = QColor(65, 220, 255, alpha) if i % 4 else QColor(255, 190, 75, alpha)
                painter.setPen(QPen(color, 2.0 if active else 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        if not self.scaled_logo.isNull():
            painter.drawPixmap(image_rect, self.scaled_logo, QRectF(self.scaled_logo.rect()))
        else:
            painter.setPen(QPen(QColor("#57eaff"), 2))
            painter.setBrush(QColor(10, 25, 48, 220))
            painter.drawEllipse(image_rect)
            painter.setPen(QColor("#b9f8ff"))
            painter.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "H")

        if active or listening:
            baseline = min(h - 24, cy + unit * 0.43)
            bar_count, spacing = 50, min(8.0, max(3.0, w / 110))
            bar_width, total = min(5.0, max(2.0, w / 180)), (bar_count - 1) * spacing
            for i in range(bar_count):
                wave = (0.18 + 0.42 * abs(math.sin(self.phase * 1.9 + i * 0.31))
                        + 0.28 * abs(math.sin(self.phase * 3.1 - i * 0.17)))
                bar_height = unit * (0.008 + wave * (0.035 if active else 0.014))
                x = cx - total/2 + i*spacing
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(75, 218, 255, 190 if active else 110))
                painter.drawRoundedRect(QRectF(x, baseline-bar_height/2, bar_width, bar_height), bar_width/2, bar_width/2)
        painter.end()


class VoiceTask(QObject):
    """Run voice and API work in a worker thread."""

    state = Signal(str)
    transcript = Signal(str)
    reply = Signal(str)
    error = Signal(str)
    finished = Signal()
    mode_command = Signal(str)
    screen_request = Signal(str)

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
                elif message:
                    # Typed prompts use the same animated user-message transcript.
                    self.transcript.emit(message)
                if not message:
                    raise RuntimeError("Type a message or use the microphone first.")
                self.state.emit("THINKING")
                answer = self._ask(message)
                self.reply.emit(answer)
                if self.speak_reply:
                    self._speak(answer)
                else:
                    self.state.emit("RESPONDING")
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
        recognizer.dynamic_energy_adjustment_damping = 0.15
        recognizer.dynamic_energy_ratio = 1.5
        recognizer.pause_threshold = 0.75
        recognizer.phrase_threshold = 0.25
        recognizer.non_speaking_duration = 0.5
        return sr, recognizer

    def _transcribe_audio(self, audio, recognizer, sr) -> str:
        """Prefer local Whisper transcription, with online fallback only if unavailable."""
        try:
            from app.voice.transcriber import transcribe_audio_data
            wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)
            transcript = transcribe_audio_data(wav_data, language=None)
            if transcript:
                return transcript.strip()
            raise sr.UnknownValueError()
        except ImportError:
            return recognizer.recognize_google(audio, language="en-IN").strip()
        except Exception as exc:
            from app.voice.transcriber import VoiceDependencyError
            if isinstance(exc, VoiceDependencyError):
                return recognizer.recognize_google(audio, language="en-IN").strip()
            raise

    def _listen_once(self) -> str:
        sr, recognizer = self._recognizer()
        self.state.emit("LISTENING")
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=1.0)
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=25)
            self.state.emit("THINKING")
            return self._transcribe_audio(audio, recognizer, sr)
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
            # Calibrate once per session; repeated calibration can swallow first words.
            with sr.Microphone() as calibration_source:
                recognizer.adjust_for_ambient_noise(calibration_source, duration=1.0)
            while not self._stop_event.is_set():
                # Release the microphone before TTS opens its optional stop listener.
                try:
                    with sr.Microphone() as source:
                        audio = recognizer.listen(source, timeout=2, phrase_time_limit=20)
                except sr.WaitTimeoutError:
                    continue
                if self._stop_event.is_set():
                    break
                self.state.emit("THINKING")
                try:
                    message = self._transcribe_audio(audio, recognizer, sr)
                except sr.UnknownValueError:
                    self.state.emit("LISTENING")
                    continue
                except sr.RequestError as exc:
                    raise RuntimeError("Speech recognition service is unavailable. Check your internet connection.") from exc
                if not message:
                    self.state.emit("LISTENING")
                    continue
                self.transcript.emit(message)
                normalized_message = " ".join(message.lower().replace("'", "").split())
                screen_phrases = (
                    "whats on my screen", "what is on my screen",
                    "look at my screen", "read my screen", "can you see my screen",
                    "analyze my screen", "describe my screen", "look at the screen",
                    "what do you see on my screen", "help me with this screen",
                )
                if any(phrase in normalized_message for phrase in screen_phrases):
                    self.screen_request.emit(message)
                    self.stop()
                    return
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
    screen_request = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("HOMER")
        self.setMinimumSize(760, 520)
        self.setStyleSheet("""
            QMainWindow, QWidget#voiceRoot { background: #030712; color: #edf8ff; }
            QLabel { background: transparent; }
            QPushButton#bottomControl {
                min-height: 60px; max-height: 72px; min-width: 225px;
                border-radius: 30px; padding: 10px 28px;
                color: #eafaff; background: rgba(8, 20, 38, 235);
                border: 1px solid rgba(71, 211, 255, 190);
                font-size: 14px; font-weight: 650;
            }
            QPushButton#bottomControl:hover {
                background: rgba(13, 45, 73, 245);
                border: 1px solid #8cf1ff;
            }
            QPushButton#bottomControl:pressed { background: rgba(12, 66, 91, 250); }
            QPushButton#listenControl { border-color: #45dfff; }
            QPushButton#listenControl[active="true"] {
                border: 1px solid #ff5d91; color: #fff0f5;
                background: rgba(63, 12, 36, 230);
            }
            QPushButton#chatControl { border-color: #a58aff; }
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

        # A restrained HUD header makes the voice state legible without clutter.
        self.state_label = QLabel("H O M E R   /   VOICE CORE")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setStyleSheet(
            "color: #78dfff; font-size: 11px; letter-spacing: 3px; padding: 8px;"
        )
        layout.addWidget(self.state_label)
        layout.addStretch(1)

        self.core = AnimatedHomerCore()
        layout.addWidget(self.core, 8)

        # Keep both sides of the conversation visible with word-by-word reveal.
        text_stack = QVBoxLayout()
        text_stack.setContentsMargins(34, 6, 34, 8)
        text_stack.setSpacing(2)
        user_heading = QLabel("YOU")
        user_heading.setStyleSheet("color:#70cfff; font-size:9px; letter-spacing:2px;")
        self.user_text_label = WordRevealLabel()
        assistant_heading = QLabel("HOMER")
        assistant_heading.setStyleSheet("color:#e9b65c; font-size:9px; letter-spacing:2px;")
        self.assistant_text_label = WordRevealLabel()
        text_stack.addWidget(user_heading)
        text_stack.addWidget(self.user_text_label)
        text_stack.addWidget(assistant_heading)
        text_stack.addWidget(self.assistant_text_label)
        layout.addLayout(text_stack)
        self.transcript_label = self.assistant_text_label

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
        self.worker.screen_request.connect(self.screen_request.emit)
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
        self.assistant_text_label.reveal(f"Switching to {mode}…")
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
        self.user_text_label.clear_text()
        self.assistant_text_label.clear_text()

    @Slot(str)
    def _set_state(self, state: str) -> None:
        # Keep an error visible briefly even when the worker immediately emits READY.
        if state == "READY" and self.core.mode == "ERROR":
            return
        if state == "READY" and self.core.mode == "RESPONDING":
            QTimer.singleShot(1100, self._finish_response_visual)
            return
        self.core.set_mode(state)
        labels = {
            "READY": "H O M E R   /   STANDBY",
            "LISTENING": "H O M E R   /   LISTENING",
            "THINKING": "H O M E R   /   THINKING",
            "SPEAKING": "H O M E R   /   SPEAKING",
            "RESPONDING": "H O M E R   /   RESPONDING",
            "ERROR": "H O M E R   /   ATTENTION",
        }
        self.state_label.setText(labels.get(state, f"H O M E R   /   {state}"))
        color = {"READY": "#78dfff", "LISTENING": "#ff789f",
                 "THINKING": "#b8a5ff", "RESPONDING": "#8df8d0",
                 "SPEAKING": "#8df8d0", "ERROR": "#ff8f9b"}.get(state, "#78dfff")
        self.state_label.setStyleSheet(
            f"color: {color}; font-size: 11px; letter-spacing: 3px; padding: 8px;"
        )

    def _finish_response_visual(self) -> None:
        if self.core.mode == "RESPONDING":
            self._set_state("READY")

    @Slot(str)
    def _show_transcript(self, text: str) -> None:
        self.user_text_label.reveal(text)

    @Slot(str)
    def _show_reply(self, text: str) -> None:
        self.assistant_text_label.reveal(text)
        self._set_state("RESPONDING")

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self.assistant_text_label.reveal(message)
        self._set_state("ERROR")
        QTimer.singleShot(2200, self._clear_error_state)

    def _clear_error_state(self) -> None:
        if self.core.mode == "ERROR":
            self.core.set_mode("READY")
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
