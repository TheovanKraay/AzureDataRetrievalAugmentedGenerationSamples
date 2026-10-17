"""Read-only live matrix. azd up supplies original text and real embeddings."""

import math

import pytest

from search_demo import RerankOptions, search, validate_vector
from seed_movies import SOURCE, read_source

pytestmark = pytest.mark.live


def test_original_movie_readback(live_containers):
    for container in live_containers.values():
        for row in read_source():
            actual = container.read_item(item=row["id"], partition_key=row["id"])
            assert all(actual[key] == value for key, value in row.items())
            assert actual["sample_source"] == SOURCE
            assert actual["embedding_provenance"]["provider"] == "azure-openai"
            validate_vector(actual["embedding"])


@pytest.mark.parametrize("mode,search_type", [
    ("vector", "all keywords"), ("fulltext", "all keywords"),
    ("fulltext", "any keywords"), ("ranking", "all keywords"),
    ("hybrid", "all keywords"),
])
@pytest.mark.parametrize("enabled", [False, True])
def test_real_embeddings_every_mode_and_toggle(live_containers, mode, search_type, enabled):
    for container in live_containers.values():
        # No embedder injection: this exercises the same real client as the UI.
        result = search(container, mode, "SPECTRE spy", use_reranker=enabled,
                        search_type=search_type)
        assert result.rows
        assert result.reranked is enabled
        assert len({row["id"] for row in result.rows}) == len(result.rows)
        assert result.ru is not None and result.ru > 0
        position = next((i for i, row in enumerate(result.rows)
                         if row["id"] == "original-movies-v1-spectre"), None)
        assert position is not None
        # Boolean matching has no ranking contract. Other modes need only a modest top-3 hit.
        if mode != "fulltext" or enabled:
            assert position < 3
        if mode in ("vector", "hybrid"):
            assert result.embedding_seconds > 0
        if enabled:
            assert all(math.isfinite(row["rerank_score"]) for row in result.rows)


@pytest.mark.parametrize("format,paths,k,diagnostics", [
    ("text", ("title", "text"), 1, False),
    ("text", ("title", "text"), 3, True),
    ("json", ("title",), 1, True),
    ("json", ("text",), 3, True),
    ("json", ("title", "text"), 10, True),
    ("json", ("title", "text"), 3, False),
])
def test_live_advanced_subsets(live_containers, format, paths, k, diagnostics):
    options = RerankOptions(format, paths, k, diagnostics)
    for container in live_containers.values():
        baseline = search(container, "vector", "SPECTRE spy")
        # Same real embedding/retrieval path, with no seed or other writes.
        off = search(container, "vector", "SPECTRE spy", rerank_options=options)
        assert [r["id"] for r in off.rows] == [r["id"] for r in baseline.rows]
        assert not off.reranked and not off.sentence_scores_requested
        result = search(container, "vector", "SPECTRE spy", use_reranker=True,
                        rerank_options=options)
        assert result.reranked
        assert len(result.rows) == min(k, result.retrieved_count)
        assert len({row["retrieval_index"] for row in result.rows}) == len(result.rows)
        for row in result.rows:
            original = baseline.rows[row["retrieval_index"]]
            assert all(row[key] == original[key] for key in ("id", "title", "text"))
            assert math.isfinite(row["rerank_score"])
            assert row["retrieval_rank"] == row["retrieval_index"] + 1
            if diagnostics:
                # Presence is service-dependent. Validate returned values without inventing text.
                for score in row["sentence_scores"] or []:
                    assert type(score["index"]) is int and score["index"] >= 0
                    assert math.isfinite(score["score"])
            else:
                assert "sentence_scores" not in row
