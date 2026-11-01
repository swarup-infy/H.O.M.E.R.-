"""HOMER native Windows desktop application."""

import sys
import html
import base64
import io

import httpx

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QInputDialog,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


API_BASE_URL = "http://127.0.0.1:8000"


class ChatWorker(QObject):
    """Send a message to the HOMER API in a background thread."""

    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    @Slot()
    def run(self):
        try:
            response = httpx.post(
                f"{API_BASE_URL}/chat",
                json={"message": self.message},
                timeout=90.0,
            )

            response.raise_for_status()
            data = response.json()

            reply = data.get("reply", "").strip()

            if not reply:
                reply = "I received an empty response from the AI provider."

            self.succeeded.emit(reply)

        except httpx.ConnectError:
            self.failed.emit(
                "Cannot connect to HOMER's API.\n\n"
                "Make sure the FastAPI server is running on port 8000."
            )

        except httpx.TimeoutException:
            self.failed.emit(
                "The request timed out. Please try again."
            )

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status == 503:
                message = (
                    "The AI provider is not configured correctly. "
                    "Check your server configuration."
                )
            elif status == 502:
                message = (
                    "The AI provider request failed. "
                    "Check the server terminal for details."
                )
            else:
                message = f"The API returned HTTP {status}."

            self.failed.emit(message)

        except Exception:
            self.failed.emit(
                "An unexpected error occurred while contacting HOMER."
            )

        finally:
            self.finished.emit()


class MessageBubble(QFrame):
    """A simple chat message card."""

    def __init__(self, speaker: str, message: str):
        super().__init__()

        is_user = speaker == "You"

        self.setObjectName(
            "userBubble" if is_user else "assistantBubble"
        )

        self.setMaximumWidth(760)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 13, 18, 13)
        layout.setSpacing(7)

        name_label = QLabel(speaker)
        name_label.setObjectName(
            "userName" if is_user else "assistantName"
        )

        message_label = QLabel(message)
        message_label.setObjectName("messageText")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout.addWidget(name_label)
        layout.addWidget(message_label)


class HomerWindow(QMainWindow):
    """Main HOMER desktop window."""

    def __init__(self):
        super().__init__()

        self.thread = None
        self.worker = None
        self.voice_window = None
        self.conversation_messages = []

        self.setWindowTitle("HOMER | Desktop AI Assistant")
        self.resize(1100, 760)
        self.setMinimumSize(760, 560)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b1020;
            }

            QWidget {
                color: #e8edf8;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QFrame#sidebar {
                background-color: #0e1528;
                border-right: 1px solid #25314a;
            }

            QFrame#topbar {
                background-color: #0e1528;
                border-bottom: 1px solid #25314a;
            }

            QLabel#brand {
                color: #83c9ff;
                font-size: 27px;
                font-weight: 700;
                letter-spacing: 3px;
            }

            QLabel#subtitle {
                color: #8997b3;
                font-size: 12px;
            }

            QLabel#pageTitle {
                font-size: 20px;
                font-weight: 600;
            }

            QLabel#connection {
                color: #8de3b1;
                font-size: 12px;
            }

            QLabel#hint {
                color: #8997b3;
                font-size: 12px;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea QWidget {
                background: transparent;
            }

            QFrame#userBubble {
                background-color: #183b62;
                border: 1px solid #2a5a89;
                border-radius: 15px;
            }

            QFrame#assistantBubble {
                background-color: #151e33;
                border: 1px solid #283550;
                border-radius: 15px;
            }

            QLabel#userName {
                color: #9bd4ff;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#assistantName {
                color: #9ce8c0;
                font-size: 12px;
                font-weight: 700;
            }

            QLabel#messageText {
                color: #edf2ff;
                font-size: 14px;
            }

            QLineEdit {
                background-color: #131d32;
                border: 1px solid #2b3b59;
                border-radius: 12px;
                padding: 14px;
                color: #f0f4ff;
                selection-background-color: #287cc0;
            }

            QLineEdit:focus {
                border: 1px solid #63baff;
            }

            QPushButton {
                background-color: #1677b8;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 18px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #228bd0;
            }

            QPushButton:disabled {
                background-color: #34425b;
                color: #8997b3;
            }

            QPushButton#secondaryButton {
                background-color: #17223a;
                border: 1px solid #2b3b59;
                color: #b9c8e3;
                text-align: left;
            }

            QPushButton#secondaryButton:hover {
                background-color: #202f4b;
            }
        """)

        self.build_ui()
        self.add_message(
            "HOMER",
            "Hello! I'm HOMER, your desktop AI assistant.\n\n"
            "I'm connected to your local API, which uses Groq "
            "for AI responses. How can I help you today?",
        )

        self.check_api()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(235)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 28, 20, 20)
        sidebar_layout.setSpacing(15)

        brand = QLabel("HOMER")
        brand.setObjectName("brand")

        subtitle = QLabel("YOUR DESKTOP AI")
        subtitle.setObjectName("subtitle")

        new_chat_button = QPushButton("+  New conversation")
        new_chat_button.setObjectName("secondaryButton")
        new_chat_button.clicked.connect(self.new_conversation)

        export_button = QPushButton("⇩  Export conversation")
        export_button.setObjectName("secondaryButton")
        export_button.setToolTip("Save this conversation as a Markdown file.")
        export_button.clicked.connect(self.export_conversation)

        screen_button = QPushButton("▣  Ask about screen")
        screen_button.setObjectName("secondaryButton")
        screen_button.setToolTip("Capture one screenshot after confirmation and ask HOMER about it.")
        screen_button.clicked.connect(self.ask_about_screen)

        tools_title = QLabel("WORKSPACE")
        tools_title.setObjectName("subtitle")

        chat_button = QPushButton("●  AI Assistant")
        chat_button.setObjectName("secondaryButton")
        chat_button.setEnabled(False)

        future_button = QPushButton("◉  Voice assistant")
        future_button.setObjectName("secondaryButton")
        future_button.setToolTip(
            "Open the animated HOMER voice assistant."
        )
        future_button.clicked.connect(self.open_voice_assistant)

        vision_button = QPushButton("◇  Gesture controls")
        vision_button.setObjectName("secondaryButton")
        vision_button.setToolTip(
            "Control the mouse pointer, click, and scroll with your hand."
        )
        vision_button.clicked.connect(self.open_gesture_controls)

        globe_button = QPushButton("◎  God's Eye View")
        globe_button.setObjectName("secondaryButton")
        globe_button.setToolTip("Open a local geospatial globe workspace.")
        globe_button.clicked.connect(self.open_gods_eye_view)

        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(18)
        sidebar_layout.addWidget(new_chat_button)
        sidebar_layout.addWidget(export_button)
        sidebar_layout.addWidget(screen_button)
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(tools_title)
        sidebar_layout.addWidget(chat_button)
        sidebar_layout.addWidget(future_button)
        sidebar_layout.addWidget(vision_button)
        sidebar_layout.addWidget(globe_button)
        sidebar_layout.addStretch()

        footer = QLabel("HOMER DESKTOP\nVersion 0.1.0")
        footer.setObjectName("subtitle")
        sidebar_layout.addWidget(footer)

        # Main panel
        main_panel = QWidget()
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("topbar")

        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(26, 20, 26, 20)

        page_title = QLabel("AI Assistant")
        page_title.setObjectName("pageTitle")

        self.connection_label = QLabel("● Checking API...")
        self.connection_label.setObjectName("connection")

        topbar_layout.addWidget(page_title)
        topbar_layout.addStretch()
        topbar_layout.addWidget(self.connection_label)

        # Scrollable conversation
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(24, 24, 24, 24)
        self.chat_layout.setSpacing(18)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)

        # Input panel
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(24, 16, 24, 22)
        input_layout.setSpacing(10)

        self.status_label = QLabel(
            "Ready when you are."
        )
        self.status_label.setObjectName("hint")

        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText(
            "Ask HOMER anything..."
        )
        self.message_input.setClearButtonEnabled(True)
        self.message_input.returnPressed.connect(self.send_message)

        self.send_button = QPushButton("Send  ➤")
        self.send_button.setMinimumWidth(105)
        self.send_button.clicked.connect(self.send_message)

        input_row.addWidget(self.message_input, 1)
        input_row.addWidget(self.send_button)

        hint = QLabel(
            "Enter to send  ·  Responses are provided by your configured AI API"
        )
        hint.setObjectName("hint")

        input_layout.addWidget(self.status_label)
        input_layout.addLayout(input_row)
        input_layout.addWidget(hint)

        main_layout.addWidget(topbar)
        main_layout.addWidget(self.scroll_area, 1)
        main_layout.addWidget(input_panel)

        root.addWidget(sidebar)
        root.addWidget(main_panel, 1)

    def open_voice_assistant(self):
        """Open the dedicated animated voice-assistant window."""
        from app.voice_window import VoiceAssistantWindow

        if self.voice_window is None:
            self.voice_window = VoiceAssistantWindow(self)

        self.voice_window.mode_switch.connect(self.handle_voice_mode_switch)
        self.voice_window.screen_request.connect(self.handle_voice_screen_request)
        self.voice_window.showMaximized()
        self.voice_window.raise_()
        self.voice_window.activateWindow()

    def handle_voice_screen_request(self, spoken_request: str):
        """Route a spoken screen-awareness request through the explicit-consent flow."""
        if self.voice_window is not None:
            self.voice_window.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.set_status("Screen analysis requested. Confirm before sharing a screenshot.")
        self.ask_about_screen()

    def open_gesture_controls(self):
        """Open the opt-in webcam air-mouse controller."""
        try:
            from app.vision.mouse_control import GestureMouseWindow

            if not hasattr(self, "gesture_window") or self.gesture_window is None:
                self.gesture_window = GestureMouseWindow(self)
            self.gesture_window.show()
            self.gesture_window.raise_()
            self.gesture_window.activateWindow()
            self.set_status("Hand mouse active. Close its window to release the camera.")
        except ImportError as exc:
            self.set_status(
                "Gesture dependencies are missing. Run: "
                "python -m pip install -r requirements-vision.txt"
            )
            self.add_message("HOMER", str(exc))
        except Exception as exc:
            self.set_status(f"Could not start hand controls: {exc}")
            self.add_message("HOMER", f"Could not start hand controls: {exc}")

    def open_gods_eye_view(self):
        """Open the optional local God’s Eye View service."""
        import os
        import webbrowser
        from urllib.parse import urlparse

        url = os.getenv("HOMER_GLOBE_URL", "http://127.0.0.1:4173").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            self.set_status("Invalid HOMER_GLOBE_URL. Use a local HTTP(S) URL.")
            return
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            self.set_status("For safety, the globe launcher only opens localhost URLs.")
            return

        webbrowser.open(url)
        self.set_status(
            "Opening the local globe in your browser. Start the globe service first."
        )

    def handle_voice_mode_switch(self, mode: str):
        """Route explicit voice commands to the requested desktop mode."""
        if mode == "text":
            if self.voice_window is not None:
                self.voice_window.hide()
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.set_status("Text mode activated. Type a message to HOMER.")
        elif mode == "gesture":
            if self.voice_window is not None:
                self.voice_window.hide()
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.open_gesture_controls()

    def add_message(self, speaker: str, message: str):
        self.conversation_messages.append((speaker, message))
        bubble = MessageBubble(speaker, message)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)

        if speaker == "You":
            row.addStretch()
            row.addWidget(bubble, 0)
        else:
            row.addWidget(bubble, 0)
            row.addStretch()

        # Insert before the permanent stretch at the bottom.
        self.chat_layout.insertLayout(
            self.chat_layout.count() - 1,
            row,
        )

        from PySide6.QtCore import QTimer
        QTimer.singleShot(
            0,
            lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ),
        )

    def set_status(self, text: str):
        self.status_label.setText(text)

    def check_api(self):
        try:
            response = httpx.get(
                f"{API_BASE_URL}/health",
                timeout=3.0,
            )
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "ok":
                self.connection_label.setText("● API online")
                self.connection_label.setStyleSheet(
                    "color: #8de3b1;"
                )
                self.set_status(
                    f"Connected to {data.get('provider', 'AI')}."
                )
            else:
                self.show_api_offline()

        except Exception:
            self.show_api_offline()

    def show_api_offline(self):
        self.connection_label.setText("● API offline")
        self.connection_label.setStyleSheet(
            "color: #ff8f9b;"
        )
        self.set_status(
            "Start the FastAPI server to chat with HOMER."
        )

    @Slot()
    def send_message(self):
        message = self.message_input.text().strip()

        if not message:
            return

        if self.thread is not None:
            if self.thread.isRunning():
                return

        self.add_message("You", message)
        self.message_input.clear()

        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.set_status("HOMER is thinking...")

        self.thread = QThread(self)
        self.worker = ChatWorker(message)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.succeeded.connect(self.handle_reply)
        self.worker.failed.connect(self.handle_error)
        self.worker.finished.connect(self.thread.quit)

        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.request_finished)

        self.thread.start()

    @Slot(str)
    def handle_reply(self, reply: str):
        self.add_message("HOMER", reply)
        self.set_status("Response received.")

    @Slot(str)
    def handle_error(self, message: str):
        self.add_message("HOMER", message)
        self.set_status("The request could not be completed.")

    @Slot()
    def request_finished(self):
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.message_input.setFocus()

        self.worker = None
        self.thread = None


    def ask_about_screen(self):
        """Capture a single screenshot only after explicit consent, then send it for analysis."""
        consent = QMessageBox.question(
            self,
            "Share screenshot with HOMER?",
            "HOMER will capture one screenshot of your screen and send it to your configured Groq vision model for analysis. The image may contain private information. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if consent != QMessageBox.StandardButton.Yes:
            self.set_status("Screenshot cancelled; nothing was captured or sent.")
            return

        prompt, accepted = QInputDialog.getText(
            self,
            "Ask about your screen",
            "What should HOMER look for?",
            text="Describe what is visible on my screen and help me with it.",
        )
        if not accepted or not prompt.strip():
            self.set_status("Screen question cancelled.")
            return

        try:
            import pyautogui
            from PIL import Image

            screenshot = pyautogui.screenshot()
            screenshot.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            screenshot.convert("RGB").save(buffer, format="JPEG", quality=75, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            image_data_url = "data:image/jpeg;base64," + encoded
            if len(buffer.getvalue()) > 5_000_000:
                self.set_status("Screenshot is too large to send safely. Try a lower screen resolution.")
                return
        except Exception as exc:
            self.set_status(f"Could not capture screenshot: {exc}")
            return

        self.add_message("You", "[Screenshot shared for this question] " + prompt.strip())
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.set_status("HOMER is analyzing the screenshot...")

        try:
            response = httpx.post(
                f"{API_BASE_URL}/screen/ask",
                json={"prompt": prompt.strip(), "image_data_url": image_data_url},
                timeout=90.0,
            )
            response.raise_for_status()
            reply = response.json().get("reply", "").strip()
            self.add_message("HOMER", reply or "The vision model returned an empty response.")
            self.set_status("Screenshot analysis complete. The image was not saved by HOMER.")
        except httpx.HTTPStatusError as exc:
            self.add_message("HOMER", f"Screen analysis failed (HTTP {exc.response.status_code}). Check the API terminal and vision model configuration.")
            self.set_status("Screen analysis failed.")
        except httpx.HTTPError as exc:
            self.add_message("HOMER", f"Could not reach HOMER's API: {exc}")
            self.set_status("Screen analysis failed.")
        finally:
            self.message_input.setEnabled(True)
            self.send_button.setEnabled(True)
            self.message_input.setFocus()

    def export_conversation(self):
        """Export the visible conversation to a Markdown file."""
        if not self.conversation_messages:
            self.set_status("There is no conversation to export yet.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export HOMER conversation",
            "homer-conversation.md",
            "Markdown files (*.md);;Text files (*.txt)",
        )
        if not path:
            return

        lines = ["# HOMER Conversation", ""]
        for speaker, message in self.conversation_messages:
            lines.extend([f"## {speaker}", "", message, ""])

        try:
            with open(path, "w", encoding="utf-8", newline="\n") as file:
                file.write("\n".join(lines))
            self.set_status(f"Conversation exported to {path}")
        except OSError as exc:
            self.set_status(f"Could not export conversation: {exc}")

    def new_conversation(self):
        # Clear visible chat and short-term AI context.
        try:
            response = httpx.post(f"{API_BASE_URL}/chat/reset", timeout=3.0)
            response.raise_for_status()
        except httpx.HTTPError:
            self.set_status("Could not reset AI context; check that the API is online.")
            return

        self.conversation_messages.clear()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)

            if item.layout() is not None:
                layout = item.layout()

                while layout.count():
                    child = layout.takeAt(0)
                    widget = child.widget()

                    if widget is not None:
                        widget.deleteLater()

                layout.deleteLater()

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.add_message(
            "HOMER",
            "New conversation started. What would you like to do?",
        )
        self.set_status("Ready when you are.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("HOMER")
    app.setOrganizationName("HOMER Project")
    app.setFont(QFont("Segoe UI", 10))

    window = HomerWindow()
    # Start directly in the animated voice interface on app launch.
    window.showMinimized()
    QTimer.singleShot(150, window.open_voice_assistant)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()