import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, Mock
from types import ModuleType
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("verify_browser", ROOT / "scripts/verify_browser.py")
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


@pytest.mark.parametrize("role,name,initial,target", [
    ("radio", "any keywords", False, True),
    ("checkbox", "Use Semantic Reranker", False, True),
    ("checkbox", "Use Semantic Reranker", True, False),
])
def test_styled_controls_click_visible_associated_text(role, name, initial, target):
    page = Mock()
    control = page.get_by_role.return_value
    control.is_checked.return_value = initial
    text = control.locator.return_value.get_by_text.return_value
    text.click.side_effect = lambda: setattr(control.is_checked, "return_value", target)

    browser.set_streamlit_checked(page, role, name, target)

    page.get_by_role.assert_called_once_with(role, name=name, exact=True)
    control.locator.assert_called_once_with("xpath=ancestor::label[1]")
    control.locator.return_value.get_by_text.assert_called_once_with(name, exact=True)
    text.click.assert_called_once_with()
    control.check.assert_not_called()
    control.set_checked.assert_not_called()
    assert control.is_checked.call_count == 2


def test_matching_state_is_not_toggled():
    page = Mock()
    page.get_by_role.return_value.is_checked.return_value = True
    browser.set_streamlit_checked(page, "radio", "all keywords", True)
    page.get_by_role.return_value.locator.assert_not_called()


def test_label_click_must_actually_change_input_state():
    page = Mock()
    page.get_by_role.return_value.is_checked.return_value = False
    with pytest.raises(AssertionError, match="checked state"):
        browser.set_streamlit_checked(page, "radio", "any keywords", True)


@pytest.mark.parametrize("capture_fails", [False, True])
def test_failure_capture_preserves_original_error(tmp_path, monkeypatch, capture_fails):
    class BrowserError(Exception):
        pass

    api = ModuleType("playwright.sync_api")
    api.Error = BrowserError
    api.expect = Mock()
    api.sync_playwright = MagicMock()
    instance = api.sync_playwright.return_value.__enter__.return_value.chromium.launch.return_value
    page = instance.new_page.return_value
    page.goto.side_effect = AssertionError("original browser failure")
    if capture_fails:
        page.screenshot.side_effect = BrowserError("capture failed")
    monkeypatch.setitem(sys.modules, "playwright", ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", api)
    monkeypatch.setattr(browser, "__file__", str(tmp_path / "scripts/verify_browser.py"))
    monkeypatch.setattr(sys, "argv", ["verify_browser.py"])
    monkeypatch.setenv("RUN_LIVE_TESTS", "1")

    with pytest.raises(AssertionError, match="original browser failure"):
        browser.main()

    page.screenshot.assert_called_once_with(
        path=str(tmp_path / ".local/validation/original-movies/"
                 "failure-python-qflat-Vector-true-rerank-False.png"),
        full_page=True, timeout=10_000)
    instance.close.assert_called_once_with()
