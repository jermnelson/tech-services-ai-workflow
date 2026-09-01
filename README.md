# FOLIO to Blue Core Technical Services Workflow

A demonstration of using an AI agentic harness (e.g. Claude Code) to drive a library
technical services workflow: pulling a cataloging record out of a
[FOLIO](https://www.folio.org/) ILS, transforming it into
[BIBFRAME](https://www.loc.gov/bibframe/) linked-data records, and ingesting the
result into a [Blue Core](https://github.com/blue-core-lod) datastore.

This repo is presentation material, not a production application — the actual
workflow is defined as three agent **skills** in `skills/`, meant to be run in
sequence by an agent rather than as application code:

1. **`folio-inventory-retrieval`** — look up a FOLIO Instance (by UUID, HRID, or
   title/author search) and retrieve its Instance + Holdings JSON via the FOLIO
   Inventory and Search APIs.
2. **`bibframe-transformation`** — reverse the FOLIO→BIBFRAME field mappings used by
   the [bluecore-workflows](https://github.com/blue-core-lod/bluecore-workflows)
   project to turn that FOLIO JSON into BIBFRAME Work and Instance JSON-LD.
3. **`blue-core-mcp-ingestion`** — push the resulting BIBFRAME records into a Blue
   Core datastore via its MCP endpoint (`scripts/blue_core_mcp.py` bridges the
   agent's stdio MCP transport to Blue Core's HTTP MCP server, injecting a
   Keycloak bearer token).

## Workflow Diagram
```mermaid
flowchart LR
   PROMPT[User enters FOLIO Instance UUID or HRID] --> FOLIO[Retrieves FOLIO Inventory JSON Record]
   FOLIO --> BFTRANSFORM[Transform to BIBFRAME Work and Instance]
   BFTRANSFORM --> USER[User approval]
   USER --> BC_MCP[Ingest into Blue Core]
```
``

See `AGENTS.md` for setup instructions and guidance on how an agent should work
with this repo.
