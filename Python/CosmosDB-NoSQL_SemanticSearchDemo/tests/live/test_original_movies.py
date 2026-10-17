"""Read-only live matrix. azd up supplies original text and real embeddings."""

import math

import pytest

from search_demo import search, validate_vector
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
