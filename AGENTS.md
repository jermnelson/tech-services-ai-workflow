# AGENTS.md — FOLIO to Blue Core Technical Services Workflow

This is a demonstration project showing how an AI agentic harness (e.g. Claude Code)
can drive a technical services workflow: pulling cataloging records out of a FOLIO
ILS, transforming them into BIBFRAME linked-data records, validating them, and
ingesting them into a Blue Core datastore. The actual work is defined as **skills**
under `skills/`, not as application code.

## Setup & Running

- Python 3.12+ is required; `.python-version` pins the interpreter (currently 3.14).
- Use `uv` for all dependency management and execution.
  - Bootstrap venv: `uv sync`
  - Run a skill script: `uv run python skills/<skill>/scripts/<script>.py`
- Dependencies (`pyproject.toml`): `folioclient`, `bluecore-client`, `bluecore-models`,
  `pyshacl` (which brings `rdflib`), `jupyterlab`.
- Secrets and endpoints are supplied via environment variables, optionally loaded
  from a `.env` file in the project root (gitignored, never commit it). Expected
  variables:
  - FOLIO: `GATEWAY_URL`, `TENANT`, `FOLIO_USER`, `FOLIO_PASSWORD`
  - Blue Core: `BLUECORE_URL`, `BLUECORE_USER`, `BLUECORE_PASSWORD`

## Project Structure

- `skills/` — the actual workflow, split into four skills meant to be run in
  sequence by an agent:
  1. `folio-inventory-retrieval` — look up a FOLIO Instance (by UUID, HRID, or
     title/author search) and retrieve its Instance + Holdings JSON.
  2. `bibframe-transformation` — reverse the mappings from the
     [bluecore-workflows](https://github.com/blue-core-lod/bluecore-workflows) repo
     to turn that FOLIO JSON into BIBFRAME Work and Instance RDF/JSON-LD, serialized
     as both JSON-LD and Turtle.
  3. `bibframe-validation` — validate the Work and Instance graphs separately against
     the BIBFRAME Interoperability Group (BIG) SHACL shapes in that skill's `assets/`,
     via `scripts/validation.py` (a CLI port of the BIG
     [bf-demo-validation-tool](https://github.com/bf-interop/bf-demo-validation-tool)).
  4. `blue-core-mcp-ingestion` — push the resulting BIBFRAME records into a Blue
     Core datastore, using `scripts/blue_core_mcp.py` as a stdio↔HTTP proxy that
     injects a Keycloak bearer token.
- Every stage reads and writes `output/{hrid}/` (gitignored), so a run's artifacts are
  inspectable: `instance.json` and `holdings.json` from stage 1, `bf_work.jsonld`/`.ttl`
  and `bf_instance.jsonld`/`.ttl` from stage 2, and `work_create_response.json` /
  `instance_create_response.json` from stage 4.
- Between stages 3 and 4, **show the user the RDF and the validation report and get
  their explicit approval before ingesting.** A non-conformant graph is not
  automatically a blocker — the BIG shapes describe interoperability expectations, not
  Blue Core ingestion requirements, and a Warning-level gap in a demo record is often
  the point being demonstrated. If the user rejects, follow up and adjust the RDF based
  on their feedback; exit the workflow if they ask to abort.
- No tests, no CI, no build scripts — this is a presentation/demo repo, not
  production code.

## Working with the skills

- `skills/` and `.claude/skills/` are **hardlinked to the same inodes**.
  `.claude/skills/` is what the harness discovers; `skills/` is what git tracks
  (`.claude/*` is gitignored). Editing either path edits both — so do not apply the
  same in-place edit (`sed -i`, a rewrite loop) to both paths in one pass, or it will
  be applied to the same file twice.
- Each skill directory has a `SKILL.md` with frontmatter (`name`, `description`)
  followed by instructions for an agent to follow — read it before acting on that
  part of the workflow rather than guessing at FOLIO/BIBFRAME/Blue Core specifics.
- Treat the four skills as pipeline stages: FOLIO record → BIBFRAME RDF → validation
  → Blue Core ingestion. Don't skip a stage or invent shortcuts between them. If a
  stage's inputs are missing from `output/{hrid}/`, say so and run (or offer to run)
  the earlier stage rather than improvising.
- FOLIO and BIBFRAME field mappings are authoritative in the external
  `bluecore-workflows` repo (`ils_middleware/tasks/folio/mappings/bf_instance.py`
  and `bf_work.py`) — consult that mapping rather than guessing at BIBFRAME shape.
  `bibframe-transformation/SKILL.md` already contains the reversed mapping, so use
  that table rather than re-fetching those files.
- Never hardcode or print credentials; always read them from environment
  variables / `.env`, matching the variable names listed above.

## Conventions
- Virtual environment: `.venv/` (gitignored, created by `uv`).
- Since this repo backs live presentations, prefer minimal, demo-friendly changes
  over larger refactors unless asked otherwise.
