"""Rendering and Qt smoke tests for HOMER's animated ASCII face."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ascii_face import AsciiHomerFace, normalize_face_state, render_ascii_face


def test_all_supported_states_render_a_five_line_face() -> None:
    for state in (
        "IDLE",
        "READY",
        "LISTENING",
        "THINKING",
        "RESPONDING",
        "SPEAKING",
        "ERROR",
        "OFFLINE",
    ):
        rendered = render_ascii_face(state)
        assert len(rendered.splitlines()) == 5
        assert "HOMER" not in rendered


def test_ready_and_standby_normalize_to_idle() -> None:
    assert normalize_face_state("READY") == "IDLE"
    assert normalize_face_state(" standby ") == "IDLE"


def test_unknown_state_falls_back_to_idle() -> None:
    assert normalize_face_state("unexpected-state") == "IDLE"
    assert render_ascii_face("unexpected-state") == render_ascii_face("IDLE")


def test_speaking_animation_changes_the_mouth() -> None:
    frames = {
        render_ascii_face("SPEAKING", index)
        for index in range(4)
    }
    assert len(frames) == 4


def test_thinking_animation_cycles_through_distinct_frames() -> None:
    frames = {
        render_ascii_face("THINKING", index)
        for index in range(3)
    }
    assert len(frames) == 3


def test_frame_index_wraps_and_invalid_index_is_safe() -> None:
    assert render_ascii_face("SPEAKING", 4) == render_ascii_face("SPEAKING", 0)
    assert render_ascii_face("SPEAKING", "not-a-number") == render_ascii_face(
        "SPEAKING", 0
    )


@pytest.fixture(scope="module")
def qt_app():
    """Create one offscreen Qt application for widget smoke tests."""
    return QApplication.instance() or QApplication([])


def test_widget_changes_animation_state_and_frame(qt_app) -> None:
    face = AsciiHomerFace(compact=True)
    face.set_state("THINKING")
    thinking_frame = face.face_label.text()

    face._advance_frame()
    assert face.face_label.text() != thinking_frame

    face.set_state("SPEAKING")
    assert face.current_state == "SPEAKING"
    assert "SPEAKING" in face.state_label.text()

    face._timer.stop()
    face.close()
    qt_app.processEvents()
