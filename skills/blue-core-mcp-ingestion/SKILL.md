---
name: blue-core-mcp-ingestion
description: Uses Blue Core MCP endpoint to add BIBFRAME Works and Instances to the Blue Core Datastore
---
Final stage of the pipeline: takes the BIBFRAME Work and Instance JSON-LD produced by
`bibframe-transformation` and checked by `bibframe-validation`, and creates them in a Blue
Core datastore.

## Variables for Blue Core
The Blue Core URL, username, and password should be set to the following environmental
variables `BLUECORE_URL`, `BLUECORE_USER`, and `BLUECORE_PASSWORD`. These variables
can also be present in a `.env` file in the root directory.

## MCP Endpoint
The Blue Core MCP endpoint is available at `$BLUECORE_URL/api/mcp` but a helper proxy
to use authenticated routes is available at `scripts/blue_core_mcp.py`. The proxy is a
stdio↔HTTP bridge: it obtains a Keycloak bearer token via `get_token()` and forwards
JSON-RPC messages read on stdin to the HTTP MCP server, tracking the `Mcp-Session-Id`.

Drive it by piping JSON-RPC lines in — `initialize`, then the
`notifications/initialized` notification, then `tools/list` or `tools/call`:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"cc","version":"1.0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | uv run python skills/blue-core-mcp-ingestion/scripts/blue_core_mcp.py
```

## Input

Everything is read from `output/{hrid}/`, where the argument is a FOLIO HRID or a path
ending in one (`output/a13616108`):

| File | Role |
|---|---|
| `bf_work.jsonld` | Work to create — this is the payload, not the `.ttl` |
| `bf_instance.jsonld` | Instance to create |

If either file is missing, stop and tell the user to run `bibframe-transformation` on that
HRID first. **Do not ingest without the user's explicit approval** of the RDF and the
`bibframe-validation` report — see `AGENTS.md`. A non-conformant graph is not automatically a
blocker, but the decision is the user's.

## The create tools cannot carry the payload

`tools/list` advertises `get_works` (which despite the name is `POST /works/` — "Create
Work") and `new_instance` (`POST /instances/`), but **both expose an empty `inputSchema`**.
Blue Core's OpenAPI spec types their request bodies as a bare `application/ld+json` object,
so the FastAPI→MCP wrapper derived no named parameters and there is nowhere to put the
JSON-LD in a `tools/call`.

So for the two create calls, import `get_token()` from the proxy and POST to the REST routes
the MCP endpoint fronts:

```python
import sys
sys.path.insert(0, "skills/blue-core-mcp-ingestion/scripts")
from blue_core_mcp import get_token

headers = {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/ld+json"}
httpx.post(f"{BLUECORE_URL}/api/works/", content=json.dumps(work), headers=headers)
```

The read/search tools (`get_work`, `get_instance`, `search`, ...) do take proper arguments
and work fine over `tools/call` — use them for lookups and verification.

## Order of operations

1. **Create the Work first.** `bibframe-transformation` deliberately omits `bf:hasInstance`
   from the Work; the API 500s if a Work references an Instance URI that doesn't exist yet.
2. **Repoint the Instance.** Overwrite the Instance's `bf:instanceOf` with the `uri` the
   server returned for the Work — the transformation only had a locally minted URI to guess
   with. Then create the Instance.
3. **Save both responses** to `output/{hrid}/work_create_response.json` and
   `output/{hrid}/instance_create_response.json`.

Both creates return `201` with a body carrying `id`, `uuid`, `uri`, and the stored `data`
graph; the Instance response also carries `work_id` linking it to the Work's numeric `id`.

The server **honors an `@id` you supply** and mints its own UUID only when `@id` is absent.
Keeping the transformation's deterministic `uuid5`-derived `@id` on both records makes a demo
re-runnable and idempotent-looking; dropping `@id` gets a fresh server UUID each run. Pick one
and apply it to Work and Instance alike so the two don't diverge.

## Verifying

Read the records back with the `get_work` / `get_instance` MCP tools, or over HTTP. Note that
those routes content-negotiate and **default to an HTML landing page** — request
`Accept: application/ld+json` to get the graph:

```python
httpx.get(f"{BLUECORE_URL}/api/works/{uuid}",
          headers={"Authorization": f"Bearer {token}", "Accept": "application/ld+json"})
```

Confirm the Instance's `instanceOf` resolves to the created Work's URI. Report the Work and
Instance URIs and numeric ids back to the user.
