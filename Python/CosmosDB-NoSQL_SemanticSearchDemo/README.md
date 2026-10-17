# Semantic search and standalone reranking

A local Streamlit movie-search sample using Azure Cosmos DB for NoSQL,
Azure OpenAI embeddings and the standalone `azure-data-ai` inference client.
The existing layout and search controls are preserved, with a collapsed
Advanced reranking section. See the [search guide](SEARCH_GUIDE.md) for manual
startup, feature walkthroughs, JSON targeting, result limits and sentence diagnostics.

## Prerequisites

Install Git, Azure CLI, azd (baseline 1.25.6), PowerShell 7 on every OS,
Python 3.10+ with venv/pip, and trusted public package/Azure network access.
Standalone Python needs neither .NET nor Docker.

Use the same Entra identity and subscription for `az login` and `azd auth login`.
You need resource creation and scoped role-assignment permissions, registered
DocumentDB/InferenceService/CognitiveServices providers, inference preview access,
Cosmos quota, and available OpenAI model quota.

Default embeddings: UKSouth, `text-embedding-3-small`, version `1`,
GlobalStandard capacity `30`, explicitly requested 1536 dimensions.
GlobalStandard can process globally, not exclusively in UKSouth.
This is pay-per-token usage, not provisioned OpenAI throughput. Budget for
two continuously billed 400 RU/s containers, storage, inference and embedding
tokens. See [all prerequisites](infra/azd/README.md#all-prerequisites).

## Deploy and run

From this directory:

```powershell
azd up
pwsh ./scripts/start.ps1
```

Choose a unique environment name, subscription and supported Cosmos/inference
region. Keep ignored `.azure/` state. Use different environments for the standalone
and combined projects. Tools and login are prerequisites, not installed by hooks.
No prior `azd init` or `azd env new` is required. Explicit environment,
subscription and location can be passed directly as `azd up` flags.

`preup` creates `.venv`, installs requirements, persists/reuses the GUID and
resets inference creation to `false`. This bootstrap does not authenticate or
call Azure. The service-free workflow then runs native `azd provision`, not
package/deploy steps. Mandatory `preprovision` uses azd's resolved subscription
and location for the authenticated inference GET; only HTTP 404 authorizes
creation. No hook guesses unresolved flags or falls back to the CLI's default
subscription.
`postprovision` only generates private `.env`
and `.local/azd-env.ps1`. `postup` sends the ten original records in
`sample-data/movies.original.json` to the real embedding deployment, validates
vectors and policies, then upserts stable namespaced IDs into both containers.
It preserves unrelated data and records model provenance. No corpus download,
fake embedding fallback or manual loader step.

Repeat `azd up` safely to regenerate embeddings and upsert the same records.
`azd provision` intentionally does not seed. A failed deployment/seed is not a
success and may leave paid resources; fix the error and retry. Never test with
`azd down`.

The foreground launcher loads generated config automatically and serves
<http://127.0.0.1:8501>. `-PythonPort` selects a different port.
Busy ports fail without stopping existing listeners. Ctrl+C stops only its
owned child process. Launching performs no data writes.

Try **SPECTRE spy**, **undercover agent satellite codes**, or **astronaut rescue**.
Exercise both indexes, all four search buttons, full-text all/any, and reranking
off/on. Query and seed embeddings use the same deployed model.

## Configuration and verification

Before `azd up`, `azd env set` can configure `AZURE_OPENAI_LOCATION` (uksouth),
`EMBEDDING_MODEL` (text-embedding-3-small), `EMBEDDING_VERSION` (1),
`EMBEDDING_DEPLOYMENT` (text-embedding-3-small), `EMBEDDING_SKU` (GlobalStandard),
and `EMBEDDING_CAPACITY` (30). `text-embedding-3-large` also uses 1536 dimensions.
Check model/version/SKU regional availability and quota first. No automatic
region fallback. Standard/DataZoneStandard are options only where supported.

```powershell
. ./.local/azd-env.ps1
$py = if ($IsWindows) { './.venv/Scripts/python.exe' } else { './.venv/bin/python' }
& $py -m pytest -q tests/unit tests/ui
$env:RUN_LIVE_TESTS = '1'
& $py -m pytest -q tests/live/test_original_movies.py
Remove-Item Env:RUN_LIVE_TESTS
```

The live matrix uses the actual embedder, both indexes, all modes and rerank
toggles. It is not a browser/UI test. Allow index propagation before checking.
The [advanced manual guide](README.manual.md) retains synthetic offline and
optional integration fixtures, existing-resource setup and browser checks.

For an actual browser matrix, leave the launcher running and use another terminal:

```powershell
& $py -m pip install -r requirements-browser.txt
& $py -m playwright install chromium
$env:RUN_LIVE_TESTS = '1'
& $py scripts/verify_browser.py
Remove-Item Env:RUN_LIVE_TESTS
```

The browser script tests all modes and toggles against the already-running app,
prints each passing case and stores screenshots only under
`.local/validation/original-movies/`. It does not manage app processes.
Add `--matrix advanced` to rerun only advanced cases, or `--matrix baseline`
for only the original cases. The default runs both.
