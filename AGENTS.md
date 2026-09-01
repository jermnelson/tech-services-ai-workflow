# AGENTS.md — FOLIO to Blue Core Technical Services Workflow

This is a demonstration project showing how an AI agentic harness (e.g. Claude Code)
can drive a technical services workflow: pulling cataloging records out of a FOLIO
ILS, transforming them into BIBFRAME linked-data records, and ingesting them into a
Blue Core datastore. The actual work is defined as **skills** under `skills/`, not
as application code.

## Setup & Running

- Python 3.12+ is required (`.python-version` pins a specific interpreter).
- Use `uv` for all dependency management and execution.
  - Bootstrap venv: `uv sync`
- Dependencies (`pyproject.toml`): `folioclient`, `bluecore-client`.
- Secrets and endpoints are supplied via environment variables, optionally loaded
  from a `.env` file in the project root (gitignored, never commit it). Expected
  variables:
  - FOLIO: `GATEWAY_URL`, `TENANT`, `FOLIO_USER`, `FOLIO_PASSWORD`
  - Blue Core: `BLUECORE_URL`, `BLUECORE_USER`, `BLUECORE_PASSWORD`

## Project Structure

- `skills/` — the actual workflow, split into three skills meant to be run in
  sequence by an agent:
  1. `folio-inventory-retrieval` — look up a FOLIO Instance (by UUID, HRID, or
     title/author search) and retrieve its Instance + Holdings JSON.
  2. `bibframe-transformation` — reverse the mappings from the
     [bluecore-workflows](https://github.com/blue-core-lod/bluecore-workflows) repo
     to turn that FOLIO JSON into BIBFRAME Work and Instance RDF/JSON-LD.
  3. For any produced BIBFRAME RDF/JSON-LD, serialize the RDF as turtle and save a copy
     to an `output/{hrid}` directory and then require the user to view the RDF and explicitly
     approve ingesting into Blue Core using `blue-core-mcp-ingestion` step. If the user
     rejects, follow-up and adjust the RDF based on the user's feedback and exit the 
     workflow if the user requests to abort.
  4. `blue-core-mcp-ingestion` — push the resulting BIBFRAME records into a Blue
     Core datastore via its MCP endpoint, using `scripts/blue_core_mcp.py` as a
     stdio↔HTTP proxy that injects a Keycloak bearer token.
- No tests, no CI, no build scripts — this is a presentation/demo repo, not
  production code.

## Working with the skills

- Each skill directory has a `SKILL.md` with frontmatter (`name`, `description`)
  followed by instructions for an agent to follow — read it before acting on that
  part of the workflow rather than guessing at FOLIO/BIBFRAME/Blue Core specifics.
- Treat the three skills as pipeline stages: FOLIO record → BIBFRAME RDF → Blue
  Core ingestion. Don't skip a stage or invent shortcuts between them.
- FOLIO and BIBFRAME field mappings are authoritative in the external
  `bluecore-workflows` repo (`ils_middleware/tasks/folio/mappings/bf_instance.py`
  and `bf_work.py`) — consult that mapping rather than guessing at BIBFRAME shape.
- Never hardcode or print credentials; always read them from environment
  variables / `.env`, matching the variable names listed above.
- `.SKILL.md.swp` files under `skills/` are stray editor swap files, not part of
  the skill content — ignore them (and feel free to delete them if asked to
  clean up).

## Conventions

- Entry point: `main.py` → `def main()`.
- Virtual environment: `.venv/` (gitignored, created by `uv`).
- Since this repo backs live presentations, prefer minimal, demo-friendly changes
  over larger refactors unless asked otherwise.
