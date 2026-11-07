"""Browser safety and validation tests; never launch a real browser."""
import pytest

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


def test_sensitive_browser_fields_are_never_auto_typed():
    class FakePage:
        def evaluate(self, _script):
            return "password current-password"
    assert browser_control._active_field_is_sensitive(FakePage()) is True


def test_sensitive_browser_field_inspection_fails_closed():
    class BrokenPage:
        def evaluate(self, _script):
            raise RuntimeError("page not ready")
    assert browser_control._active_field_is_sensitive(BrokenPage()) is True


def test_browser_blocks_submit_clicks(monkeypatch):
    class FakePage:
        pass
    monkeypatch.setattr(browser_control, "_page", lambda _index: FakePage())
    result = browser_control.browser_action("click_text", text="Submit")
    assert result["ok"] is False
    assert "manually" in result["error"]


def test_browser_channel_defaults_to_isolated_chromium(monkeypatch):
    monkeypatch.delenv("HOMER_BROWSER_CHANNEL", raising=False)
    selected, options = browser_control._browser_configuration()
    assert selected == "chromium"
    assert options == {}


def test_browser_channel_supports_installed_chrome_and_edge(monkeypatch):
    monkeypatch.setenv("HOMER_BROWSER_CHANNEL", "chrome")
    assert browser_control._browser_configuration() == ("chrome", {"channel": "chrome"})
    monkeypatch.setenv("HOMER_BROWSER_CHANNEL", "msedge")
    assert browser_control._browser_configuration() == ("msedge", {"channel": "msedge"})


def test_browser_channel_rejects_unknown_engine(monkeypatch):
    monkeypatch.setenv("HOMER_BROWSER_CHANNEL", "opera")
    with pytest.raises(RuntimeError, match="HOMER_BROWSER_CHANNEL"):
        browser_control._browser_configuration()


def test_browser_status_does_not_launch_browser(monkeypatch):
    monkeypatch.setenv("HOMER_BROWSER_CHANNEL", "chromium")
    result = browser_control.browser_status()
    assert result["ok"] is True
    assert result["dedicated_profile"] is True
    assert "profile_path" in result


def test_browser_rejects_embedded_credentials_and_nonstandard_ports():
    assert not browser_control._allowed_url("https://user:password@youtube.com/")
    assert not browser_control._allowed_url("https://youtube.com:8443/")
    assert not browser_control._allowed_url(None)


def test_browser_allowlist_includes_common_productivity_and_messaging_sites():
    assert browser_control._allowed_url("https://web.whatsapp.com/")
    assert browser_control._allowed_url("https://drive.google.com/")
    assert browser_control._allowed_url("https://www.canva.com/")
    assert browser_control._allowed_url("https://huggingface.co/")
