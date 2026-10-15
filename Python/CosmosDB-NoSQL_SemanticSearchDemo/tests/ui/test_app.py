from pathlib import Path
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import search_demo

APP = Path(__file__).resolve().parents[2] / "src/app/cosmos-app.py"


def fake_services(monkeypatch):
    container = Mock()
    container.query_items.return_value = [
        {"id": "a", "title": "Space rescue", "text": "An orbital rescue."},
        {"id": "b", "title": "Garden", "text": "A peaceful garden."},
    ]
    inference = Mock()
    inference.semantic_rerank.return_value = {
        "scores": [{"index": 0, "score": 0.9}, {"index": 1, "score": 0.1}]
    }
    monkeypatch.setattr(search_demo, "get_container", lambda name: container)
    monkeypatch.setattr(search_demo, "get_inference_client", lambda: inference)
    monkeypatch.setattr(search_demo, "embed_text", lambda text: [1.0] + [0.0] * 1535)
    return container, inference


def test_startup_does_not_create_clients_or_write(monkeypatch):
    for name in ("get_container", "get_inference_client", "embed_text"):
        monkeypatch.setattr(search_demo, name, Mock(side_effect=AssertionError(name)))
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert len(app.button) == 4
    assert len(app.selectbox) == 1
    assert len(app.checkbox) == 1
    assert len(app.radio) == 1
    assert all(button.disabled for button in app.button)


@pytest.mark.parametrize("button", ["location_search", "full_text_search",
                                    "full_text_ranking", "hybrid_search"])
@pytest.mark.parametrize("enabled", [False, True])
def test_ui_all_buttons(monkeypatch, button, enabled):
    container, inference = fake_services(monkeypatch)
    app = AppTest.from_file(str(APP)).run()
    app.text_input(key="user_query").set_value("space rescue")
    app.checkbox(key="use_reranker").set_value(enabled)
    app.run()
    app.button(key=button).click().run()
    assert not app.exception and not app.error
    assert len(app.table) == 1
    assert len(app.table[0].value) == 2
    assert ("rerank_score" in app.table[0].value.columns) is enabled
    assert inference.semantic_rerank.call_count == int(enabled)
    container.query_items.assert_called_once()


def test_visible_error_no_stale_success(monkeypatch):
    _, inference = fake_services(monkeypatch)
    app = AppTest.from_file(str(APP)).run()
    app.text_input(key="user_query").set_value("rescue").run()
    app.button(key="full_text_ranking").click().run()
    assert len(app.table) == 1
    inference.semantic_rerank.side_effect = RuntimeError("private endpoint secret")
    app.checkbox(key="use_reranker").check().run()
    app.button(key="full_text_ranking").click().run()
    assert not app.exception
    assert len(app.error) == 1 and "Reranking failed" in app.error[0].value
    assert "private endpoint" not in app.error[0].value
    assert len(app.table) == 0


def test_ui_any_keywords_and_diskann_selection(monkeypatch):
    container, _ = fake_services(monkeypatch)
    get_container = Mock(return_value=container)
    monkeypatch.setattr(search_demo, "get_container", get_container)
    app = AppTest.from_file(str(APP)).run()
    app.selectbox(key="index_selection").select("DiskANN & Full Text Search Index")
    app.radio(key="full_text_search_type").set_value("any keywords")
    app.text_input(key="user_query").set_value("orbital rescue").run()
    app.button(key="full_text_search").click().run()
    assert not app.exception and not app.error
    get_container.assert_called_once_with("search_diskann")
    assert "FullTextContainsAny" in container.query_items.call_args.args[0]


def test_missing_openai_visible(monkeypatch):
    fake_services(monkeypatch)
    monkeypatch.setattr(search_demo, "embed_text", Mock(side_effect=search_demo.SearchError(
        "Set AZURE_OPENAI_EMBEDDING_DEPLOYMENT for vector and hybrid search.")))
    app = AppTest.from_file(str(APP)).run()
    app.text_input(key="user_query").set_value("rescue").run()
    app.button(key="location_search").click().run()
    assert "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" in app.error[0].value
