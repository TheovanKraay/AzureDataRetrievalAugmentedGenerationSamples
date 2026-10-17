"""Only the azd postup hook writes this bounded, original, real-embedding dataset."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from openai import APIStatusError

from container_setup import validate_policy
from load_data import upsert_with_retry
from search_demo import (
    DIMENSIONS, Settings, get_cosmos_client, get_embedding_client, load_environment,
    validate_vector,
)

SOURCE = "original-movies-v1"
PYTHON_CONTAINERS = ("search_qflat", "search_diskann")
DOTNET_CONTAINERS = ("reranker_dotnet_qflat", "reranker_dotnet_diskann")


def validate_source(rows):
    if not isinstance(rows, list) or not 8 <= len(rows) <= 12:
        raise ValueError("Original movie source must contain 8-12 records.")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"id", "title", "text"}
                or any(not isinstance(row[k], str) or not row[k].strip() for k in row)
                or not row["id"].startswith(SOURCE + "-")
                or any(c in row["id"] for c in "/\\?#")
                or len(row["id"]) > 100 or row["id"] in seen
                or len(row["text"]) > 2000 or len(row["title"]) > 100):
            raise ValueError("Invalid original movie namespace, shape or size.")
        seen.add(row["id"])
    return rows


def read_source():
    path = Path(__file__).resolve().parents[1] / "sample-data/movies.original.json"
    return validate_source(json.loads(path.read_text(encoding="utf-8")))


def wait_for_role(operation):
    """Retry only explicit authorization propagation, bounded to two minutes."""
    for attempt in range(13):
        try:
            return operation()
        except (CosmosHttpResponseError, APIStatusError) as error:
            if error.status_code != 403 or attempt == 12:
                raise
            print("Waiting for data-plane role propagation (403); retrying in 10 seconds.", flush=True)
            time.sleep(10)


def seed(containers, rows, client, deployment, model, version):
    rows = validate_source(rows)
    allowed = (*PYTHON_CONTAINERS, *DOTNET_CONTAINERS)
    if not containers or any(name not in allowed for name in containers):
        raise ValueError("Only dedicated sample containers may be seeded.")
    if not all(isinstance(value, str) and value.strip() for value in (deployment, model, version)):
        raise ValueError("Embedding deployment, model and version provenance are required.")
    # Validate ALL containers and ownership before embedding charges or any writes.
    for name, container in containers.items():
        policy = wait_for_role(container.read)
        if policy.get("id") != name:
            raise ValueError("Container response does not match the selected target.")
        alias = "search_qflat" if name.endswith("qflat") else "search_diskann"
        validate_policy({**policy, "id": alias}, alias)
        for row in rows:
            try:
                existing = container.read_item(item=row["id"], partition_key=row["id"])
            except CosmosResourceNotFoundError:
                continue
            if existing.get("sample_source") != SOURCE:
                raise ValueError("Refusing to overwrite a document not owned by this seed.")
    response = wait_for_role(lambda: client.embeddings.create(
        input=[row["text"] for row in rows], model=deployment, dimensions=DIMENSIONS))
    if len(response.data) != len(rows):
        raise ValueError("Embedding response count does not match the bounded source.")
    vectors = {}
    for entry in response.data:
        if type(entry.index) is not int or not 0 <= entry.index < len(rows) or entry.index in vectors:
            raise ValueError("Invalid or duplicate embedding response index.")
        vectors[entry.index] = validate_vector(entry.embedding)
    prepared = [{
        **row, "sample_source": SOURCE, "embedding": vectors[index],
        "embedding_provenance": {
            "provider": "azure-openai", "deployment": deployment,
            "model": model, "version": version, "dimensions": DIMENSIONS,
            "text_sha256": hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
        },
    } for index, row in enumerate(rows)]
    for name, container in containers.items():
        for row in prepared:
            upsert_with_retry(container, row)
        print(f"{name}: upserted {len(prepared)} original movies with real embeddings.", flush=True)
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-dotnet", action="store_true")
    parser.add_argument("--confirm-write", required=True, action="store_true")
    args = parser.parse_args()
    load_environment()
    settings = Settings.from_env()
    database = get_cosmos_client(settings.endpoint).get_database_client(settings.database)
    names = (*PYTHON_CONTAINERS, *(DOTNET_CONTAINERS if args.include_dotnet else ()))
    seed({name: database.get_container_client(name) for name in names},
         read_source(), get_embedding_client(),
         os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
         os.environ["AZURE_OPENAI_EMBEDDING_MODEL"],
         os.environ["AZURE_OPENAI_EMBEDDING_VERSION"])


if __name__ == "__main__":
    main()
