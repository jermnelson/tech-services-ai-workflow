---
name: bibframe-validation
description: Validate generated BIBFRAME Work and Instance RDF against BIBFRAME Interoperability SHACL shapes before ingestion
---
Third stage of the pipeline: takes the BIBFRAME Work and Instance RDF produced by
`bibframe-transformation` and validates it against the BIBFRAME Interoperability Group (BIG)
SHACL shapes in this skill's `assets/` directory, before the user is asked to approve
`blue-core-mcp-ingestion`.

## Input

The skill takes a single argument: a FOLIO **HRID** (e.g. `a13616108`), or a path that ends in
one (`output/a13616108`). Everything is read from `output/{hrid}/`:

| File | Role |
|---|---|
| `bf_work.ttl` | Work graph to validate |
| `bf_instance.ttl` | Instance graph to validate |
| `bf_work.jsonld` / `bf_instance.jsonld` | Same graphs in JSON-LD; only read if the `.ttl` is missing |

If the argument is a path, take the last path segment as the HRID; normalize to
`output/{hrid}` relative to the repo root. If either `bf_*.ttl` is missing, stop and tell the
user to run `bibframe-transformation` on that HRID first — don't try to regenerate the RDF here.

The Work and Instance graphs are validated separately: the shapes for the two are distinct, and
the Instance's `bf:instanceOf` points at a Work URI that isn't in the Instance graph. The FOLIO
`instance.json` is *not* needed — see shape selection below.

## Running the validation

`scripts/validation.py` is a CLI port of the BIG demo validation tool
([`bf-interop/bf-demo-validation-tool`](https://github.com/bf-interop/bf-demo-validation-tool),
`src/bf_demo_validation_tool/validation.py` and `data.py`). The `pyshacl.validate(...)` call and
the shape-summary SPARQL are kept as they are upstream; the Pyodide `js.document` rendering is
replaced with printing, and the shapes graph is built from the local `assets/*.ttl` instead of
Sinopia JSON-LD URLs.

```bash
uv run python .claude/skills/bibframe-validation/scripts/validation.py a13616108
uv run python .claude/skills/bibframe-validation/scripts/validation.py a13616108 --summarize
```

`rdflib` and `pyshacl` are both available under plain `uv run python` (`pyshacl` is a declared
project dependency and brings `rdflib` with it) — no `uv run --with ...` needed. Exit status is
`0` only when both graphs conform. `--summarize` additionally prints every node shape in the
loaded shapes graph with its target classes and property constraints.

## Shape selection

The BIG shapes pick their focus nodes by `sh:targetClass`, so all the shape files for one
resource kind can be merged into a single shapes graph — only the shapes whose target classes
actually appear in the data will fire. Nothing has to be chosen by mode of issuance or carrier:

| Kind | Shape files merged |
|---|---|
| Work | `work-monograph-text.ttl`, `work-serial-text.ttl`, `admin-metadata.ttl` |
| Instance | `instance-monograph-text.ttl`, `instance-serial-electronic.ttl`, `admin-metadata.ttl` |

Merging does mean the shared `big:ProvisionActivity` shape is declared twice, so its results are
reported twice. That's cosmetic and expected.

## Reading the results

Validation runs with `allow_warnings=True` (upstream's setting), so only `sh:Violation` results
make a graph non-conformant; `sh:Warning` and `sh:Info` results are advisory and still printed.
Most of the BIG property shapes are Warning or Info severity.

Two things about this shape set that make a bare "Conforms: True" misleading, both of which the
script reports explicitly:

- **Focus node count.** pyshacl returns `conforms=True` when a shapes graph selects no focus
  nodes at all. The script prints how many nodes the target classes actually selected and warns
  when that is zero — a vacuous pass, not a validated record.
- **The record-level shapes never fire on our output.** `big:Monograph:Work` targets
  `bf:Monograph`/`bf:Text` and `big:Monograph:Instance:Print` targets `bf:Print`, but
  `bibframe-transformation` types its nodes only `bf:Work` and `bf:Instance`. So the top-level
  shape has nothing to attach to and only the nested component shapes (Title, Agent,
  Contribution, AdminMetadata, ProvisionActivity...) are checked. The script prints a warning
  naming the missing classes. Fixing this means deriving those genre/carrier types from FOLIO
  (`modeOfIssuanceId` "single unit" → `bf:Monograph`, `instanceTypeId` "text" → `bf:Text`,
  carrier "volume" → `bf:Print`) in the transformation stage — out of scope here.

Expected findings on the `a13616108` demo record: the Work graph conforms (5 focus nodes), and the
Instance graph fails on one Violation — `big:AdminMetadata` has an `sh:or` requiring both a date
(`bf:creationDate`|`bf:date`) *and* an agent (`bf:assigner`|`bf:agent`), and the transformation
emits only `bf:date` from `catalogedDate`. The remaining results are Warnings on the
`bf:Publication` node, which wants authority-controlled `bf:agent`/`bf:place`/`bf:date` rather
than the `bflc:simpleAgent`/`simplePlace`/`simpleDate` the uncontrolled FOLIO `publication[]`
maps to.

## After validating

Show the user the validation report along with the RDF and let them decide. A non-conformant
graph is not automatically a blocker — these shapes describe BIG interoperability expectations,
not Blue Core ingestion requirements, and a Warning-level gap in a demo record is often the point
being demonstrated. Do not advance to `blue-core-mcp-ingestion` without the user's explicit
approval, and if they want the RDF changed first, go back to `bibframe-transformation`.
