# Agent boundaries

- Work only in this sample unless the requester explicitly expands scope.
- Read the root README and the applicable `cosmosdb-best-practices` skill before
  Cosmos SDK changes. No account/database provisioning, role changes or cleanup
  without explicit authorization.
- Keep the original Streamlit index selector, input, reranker checkbox, four search
  buttons, all/any radio, metadata table and timing displays.
- Use `azure.data.ai.InferenceClient` for reranking. Map lowercase `scores`,
  `index`, `score` by index. Reject invalid/duplicate indices. Never silently
  present retrieval results as successfully reranked.
- Import/startup must not connect or write. Use existing database/container clients.
  OpenAI is lazy and optional for full-text search and preembedded loading.
- Inference setup is explicit and read-only by default. Use the same Cosmos account
  name, GET before creation, and the returned endpoint. `--confirm-create` and
  `--assign-role` authorize separate actions. Never redeploy Cosmos or add keys.
- Preserve the Cosmos timeout regression: `connection_timeout=30` is seconds;
  never reintroduce legacy `request_timeout=30`, which is milliseconds.
- Offline tests allow loopback runtime IPC only. Keep external TCP, UDP and DNS
  blocked and keep service seams mocked.
- Never commit `.env`, virtual environments, private endpoints, subscription/account
  identifiers, tokens, private feeds, service logs or internal attachments.
- Fixtures are original MIT-licensed synthetic text and deterministic integration
  vectors. They do not measure embedding quality. Keep stable IDs.
- Test first. Do not claim live verification from mocks or HTTP health.

## Commands from the sample root

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
& .\.venv\Scripts\python.exe scripts/make-fixtures.py
& .\.venv\Scripts\python.exe -m pytest -q tests/unit tests/ui
& .\.venv\Scripts\python.exe -m streamlit run src/app/cosmos-app.py
```

The README covers explicit provisioning and confirmed fixture loading. Live tests
require private environment settings, `RUN_LIVE_TESTS=1`, and loaded fixtures.
Write tests additionally require `ALLOW_FIXTURE_UPSERT=1`. Enabled tests must fail,
not skip, when prerequisites are missing. Never execute cleanup as part of testing.
Do not commit or push unless explicitly asked. Return changed files, commands,
actual outputs, unverified gates and remaining limitations.
