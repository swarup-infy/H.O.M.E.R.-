"""Browser safety and validation tests; never launch a real browser."""
from app.tools import browser_control


def test_only_allowlisted_https_domains_are_allowed():
    assert browser_control._allowed_url("https://www.youtube.com/")
    assert browser_control._allowed_url("https://open.spotify.com/")
    assert browser_control._allowed_url("https://github.com/")
    assert not browser_control._allowed_url("http://youtube.com/")
    assert not browser_control._allowed_url("https://youtube.com.evil.example/")
    assert not browser_control._allowed_url("file:///C:/Users/test.txt")
    assert not browser_control._allowed_url("javascript:alert(1)")


def test_invalid_browser_action_does_not_start_playwright(monkeypatch):
    called = []
    monkeypatch.setattr(browser_control, "_ensure_browser", lambda: called.append(True))
    result = browser_control.browser_action("run_arbitrary_js")
    assert result["ok"] is False
    assert called == []


def test_navigation_requires_allowlisted_https(monkeypatch):
    monkeypatch.setattr(browser_control, "_ensure_browser", lambda: (_ for _ in ()).throw(AssertionError("browser should not launch")))
    result = browser_control.browser_action("navigate", url="https://evil.example/")
    assert result["ok"] is False
    assert "allowlisted HTTPS" in result["error"]


def test_volume_range_is_validated_before_browser_launch(monkeypatch):
    class FakePage:
        pass
    monkeypatch.setattr(browser_control, "_page", lambda index: FakePage())
    monkeypatch.setattr(browser_control, "_lock", __import__("threading").RLock())
    result = browser_control.browser_action("volume", volume=101)
    assert result["ok"] is False


def test_media_controls_follow_the_selected_tab(monkeypatch):
    class FakePage:
        def __init__(self, label):
            self.label = label
        def bring_to_front(self):
            pass
        def title(self):
            return self.label
        def evaluate(self, _script, _args):
            return {"ok": True, "page": self.label}

    first = FakePage("first")
    second = FakePage("second")
    monkeypatch.setattr(browser_control, "_ensure_browser", lambda: None)
    monkeypatch.setattr(browser_control, "_pages", [first, second])
    monkeypatch.setattr(browser_control, "_active_index", 0)
    monkeypatch.setattr(browser_control, "_context", object())

    selected = browser_control.browser_action("select_tab", tab_index=1)
    assert selected["ok"] is True
    assert browser_control._active_index == 1

    result = browser_control.browser_action("play")
    assert result == {"ok": True, "page": "second"}


def test_playwright_calls_are_serialized_on_one_browser_thread(monkeypatch):
    import threading

    thread_ids = []
    def fake_action(*_args):
        thread_ids.append(threading.get_ident())
        return {"ok": True}

    monkeypatch.setattr(browser_control, "_browser_action_impl", fake_action)
    assert browser_control.browser_action("tabs")["ok"] is True
    assert browser_control.browser_action("tabs")["ok"] is True
    assert len(set(thread_ids)) == 1
    assert thread_ids[0] != threading.get_ident()
