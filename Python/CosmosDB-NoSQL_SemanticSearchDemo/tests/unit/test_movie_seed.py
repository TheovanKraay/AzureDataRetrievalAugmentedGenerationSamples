import copy
from types import SimpleNamespace

import pytest

import seed_movies as seed
from container_setup import container_resource


class Container:
    def __init__(self, name):
        self.name = name
        self.items = {"unrelated": {"id": "unrelated", "text": "leave me alone"}}
        self.writes = 0

    def read(self):
        return container_resource(self.name)

    def read_item(self, item, partition_key):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        if item not in self.items:
            raise CosmosResourceNotFoundError(status_code=404)
        return self.items[item]

    def upsert_item(self, body):
        self.writes += 1
        self.items[body["id"]] = copy.deepcopy(body)


def client(vector=None, count=10):
    class Embeddings:
        def create(self, **kwargs):
            assert kwargs["dimensions"] == 1536
            assert kwargs["model"] == "text-embedding-3-small"
            assert len(kwargs["input"]) == 10
            return SimpleNamespace(data=[
                SimpleNamespace(index=i, embedding=vector or [1.0] + [0.0] * 1535)
                for i in reversed(range(count))])
    return SimpleNamespace(embeddings=Embeddings())


def test_seed_bounded_repeat_and_unrelated_preserved():
    containers = {name: Container(name) for name in seed.PYTHON_CONTAINERS}
    rows = seed.read_source()
    seed.seed(containers, rows, client(), "text-embedding-3-small",
              "text-embedding-3-small", "1")
    original = copy.deepcopy(containers["search_qflat"].items)
    seed.seed(containers, rows, client(), "text-embedding-3-small",
              "text-embedding-3-small", "1")
    for container in containers.values():
        assert container.items == original
        assert container.writes == 20
        assert len(container.items) == 11
        assert container.items[rows[0]["id"]]["embedding_provenance"]["dimensions"] == 1536


@pytest.mark.parametrize("bad_client", [client([0.0] * 1536), client(count=9)])
def test_bad_embedding_response_writes_nothing(bad_client):
    containers = {name: Container(name) for name in seed.PYTHON_CONTAINERS}
    with pytest.raises(ValueError):
        seed.seed(containers, seed.read_source(), bad_client,
                  "text-embedding-3-small", "text-embedding-3-small", "1")
    assert all(c.writes == 0 for c in containers.values())


def test_namespace_collision_fails_before_any_write():
    containers = {name: Container(name) for name in seed.PYTHON_CONTAINERS}
    rows = seed.read_source()
    containers["search_diskann"].items[rows[0]["id"]] = {"id": rows[0]["id"]}
    with pytest.raises(ValueError, match="owned"):
        seed.seed(containers, rows, client(), "text-embedding-3-small",
                  "text-embedding-3-small", "1")
    assert all(c.writes == 0 for c in containers.values())


def test_invalid_namespace_or_oversized_source():
    rows = seed.read_source()
    with pytest.raises(ValueError):
        seed.validate_source(rows * 2)
    rows[0]["id"] = "someone-elses-document"
    with pytest.raises(ValueError):
        seed.validate_source(rows)


def test_duplicate_response_index_writes_nothing():
    containers = {name: Container(name) for name in seed.PYTHON_CONTAINERS}
    bad = client()
    bad.embeddings.create = lambda **kwargs: SimpleNamespace(data=[
        SimpleNamespace(index=0, embedding=[1.0] + [0.0] * 1535)] * 10)
    with pytest.raises(ValueError, match="duplicate"):
        seed.seed(containers, seed.read_source(), bad, "deployment", "model", "1")
    assert all(c.writes == 0 for c in containers.values())


def test_service_failure_does_not_fallback_or_write():
    containers = {name: Container(name) for name in seed.PYTHON_CONTAINERS}
    bad = client()
    def fail(**kwargs):
        raise TimeoutError("offline simulated service failure")
    bad.embeddings.create = fail
    with pytest.raises(TimeoutError):
        seed.seed(containers, seed.read_source(), bad, "deployment", "model", "1")
    assert all(c.writes == 0 for c in containers.values())


def test_role_propagation_retry_is_bounded(monkeypatch):
    from azure.cosmos.exceptions import CosmosHttpResponseError
    calls = []
    sleeps = []
    monkeypatch.setattr(seed.time, "sleep", sleeps.append)
    def denied():
        calls.append(1)
        raise CosmosHttpResponseError(status_code=403)
    with pytest.raises(CosmosHttpResponseError):
        seed.wait_for_role(denied)
    assert len(calls) == 13
    assert sleeps == [10] * 12
