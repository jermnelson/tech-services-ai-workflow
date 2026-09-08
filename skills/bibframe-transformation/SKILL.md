---
name: bibframe-transformation
description: Take a FOLIO JSON Inventory Instance and Holdings records, generate BIBFRAME Work and Instance JSON-LD
---
## Background
With existing JSON records for a FOLIO inventory Instance and Holdings records, reverse the mappings found
at `https://github.com/blue-core-lod/bluecore-workflows/blob/main/ils_middleware/tasks/folio/mappings/bf_instance.py`
and `https://github.com/blue-core-lod/bluecore-workflows/blob/main/ils_middleware/tasks/folio/mappings/bf_work.py` to
generate a BIBFRAME Work RDF and a BIBFRAME Instance RDF record.

Those two files are SPARQL query templates that *read* BIBFRAME properties back out of an RDF graph (originally
written for the Sinopia BF→plain-value direction). "Reversing" them means: for each query, take the triple pattern
it uses to select a BF property, and instead *write* a triple in that same shape from the corresponding FOLIO field.
The mapping below is the result of doing that reversal once, by hand — use it directly instead of re-fetching and
re-reading `bf_instance.py`/`bf_work.py` from scratch.

## Prerequisites

- Resolving several FOLIO fields (`instanceTypeId`, `modeOfIssuanceId`, `instanceFormatIds`, `contributorNameTypeId`,
  `contributorTypeId`, `identifierTypeId`, `instanceNoteTypeId`, `alternativeTitleTypeId`) requires FOLIO reference
  data, not just the Instance/Holdings JSON. Use the same authenticated `FolioClient` from the
  `folio-inventory-retrieval` skill and its cached reference-data properties (each is a list of `{"id": ..., "name": ...}`):
  - `instance_types`, `modes_of_issuance`, `instance_formats`, `contrib_name_types`, `contributor_types`,
    `alt_title_types`, `identifier_types`, `instance_note_types`, `locations`, `electronic_access_relationships`
  - Look up a label with `next(x["name"] for x in fc.<property> if x["id"] == target_id)`.
- Contributor records already carry a human-readable role in `contributorTypeText` (e.g. `"instrumentalist."`) —
  prefer that over resolving `contributorTypeId` when both are present.

## JSON-LD conventions used

```json
"@context": {
  "bf": "http://id.loc.gov/ontologies/bibframe/",
  "bflc": "http://id.loc.gov/ontologies/bflc/",
  "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
  "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
}
```

- Controlled values that have no authority URI available locally (most FOLIO reference data — it has a label but
  not a linked-data URI) are written as blank nodes with `rdfs:label`, e.g. `{"rdfs:label": "single unit"}`. Only use
  an `{"@id": "..."}` reference when you actually have a resolvable authority/vocabulary URI (e.g. a Work's
  `bf:instanceOf` link to a real Blue Core Instance URI).
- Uncontrolled publication data (FOLIO's free-text `publication[]`) maps to `bflc:simpleAgent` / `bflc:simplePlace` /
  `bflc:simpleDate` on a `bf:Publication` node, per `bf_instance.py:publication`'s "simple" variant — don't invent
  `bf:agent`/`bf:place` typed nodes unless the source data is actually authority-controlled.
- Mint Work/Instance `@id` URIs deterministically for a demo (e.g. `uuid5` off the FOLIO instance UUID) — production
  Blue Core assigns its own UUID on ingestion and will return the real `@id` in the create response; don't treat the
  locally minted URI as final.
- **Do not set `bf:hasInstance` on the Work when generating these records.** The Blue Core ingestion API 500s if a
  Work references an Instance URI that doesn't exist yet (see `blue-core-mcp-ingestion`) — create the Work first,
  then set `bf:instanceOf` on the Instance to the Work URI the server actually returns. The forward link isn't
  needed for ingestion to succeed.

## BIBFRAME Work mapping (from `bf_work.py`)

| Work JSON-LD | FOLIO source | Notes |
|---|---|---|
| `bf:content` | `instanceTypeId` | Resolve via `fc.instance_types`; write as `{"rdfs:label": <name>}`, e.g. "performed music". **Omit the property entirely when the resolved label is a placeholder** (`"unspecified"`, `"Undefined"`, empty) rather than asserting it — FOLIO uses those as "no value recorded", and `bf:content "unspecified"` claims a content type the record does not actually have. Seen on `a11712006`. |
| `bf:title` (`bf:Title`) | `title` / `indexTitle` | `{"@type": "bf:Title", "bf:mainTitle": ...}` |
| `bf:title` (`bf:VariantTitle`) | `alternativeTitles[]` | One node per entry: `{"@type": "bf:VariantTitle", "bf:mainTitle": alternativeTitle}`. (`alternativeTitleTypeId` resolves to a label like "Variant title" if you need to record the subtype.) |
| `bf:editionStatement` | `editions[]` | Plain strings. |
| `bf:contribution` / `bf:PrimaryContribution` | `contributors[]` | Use `bf:PrimaryContribution` when `primary: true`, else `bf:Contribution`. `bf:role` = `{"rdfs:label": contributorTypeText title-cased}`. `bf:agent` type: `contributorNameTypeId` resolved via `fc.contrib_name_types` — "Personal name" → `bf:Person`, "Corporate name" → `bf:Organization`, otherwise `bf:Agent`; `rdfs:label` = `name`. |
| `bf:subject` | `subjects[]` | `{"rdfs:label": value}` — FOLIO subjects here are plain strings, not authority-linked. |
| `bf:genreForm` | *(not present in this record shape)* | Only populate if the source has real genre/form terms distinct from subjects; don't repurpose subject strings. |
| `bf:classification` | `classifications[]` | `{"@type": <resolved class, e.g. bf:ClassificationLcc>, "bf:classificationPortion": <value>}` when present. |
| `bf:language` | `languages[]` | `{"rdfs:label": <language code/name>}` per entry. |
| `bf:series_controlled` / uncontrolled | `series[]` | Controlled (has authority) → `bf:relation`/`bf:Relation`→`bf:Hub`; uncontrolled → `bf:relation`→`bf:Series`→`bf:title`. |
| `bf:summary` | notes with a "Summary" note type | `{"@type": "bf:Summary", "rdfs:label": note}`. |
| `bf:note` | `notes[]` (Work-level note types, e.g. "Participant or Performer note", "Formatted Contents Note") | `{"@type": "bf:Note", "bf:noteType": <resolved instanceNoteTypeId label>, "rdfs:label": note}`. Exclude "Source of Description note" — that belongs on the Instance (see below). |

## BIBFRAME Instance mapping (from `bf_instance.py`)

| Instance JSON-LD | FOLIO source | Notes |
|---|---|---|
| `bf:instanceOf` | — | Set to the real created Work's `@id`/URI (see prerequisites note above). |
| `bf:title` | same as Work's `bf:title` | Instances repeat the title node(s). |
| `bf:adminMetadata` | `catalogedDate` + FOLIO tenant | `{"@type": "bf:AdminMetadata", "bf:date": catalogedDate, "bf:assigner": {"@type": "bf:Organization", "bf:code": <MARC org code>, "rdfs:label": <library name>}}`. The assigner is required: `bibframe-validation`'s `big:AdminMetadata` shape has an `sh:or` demanding a date **and** an assigner/agent, so date alone is a `sh:Violation`. The Inventory JSON carries no MARC 040, so derive the agent from the `TENANT` env var via a small lookup (`sul` → `CSt` / "Stanford University Libraries"). **Flag this to the user**: it records which tenant the record was pulled from, not what the catalog says about who created the description, and it is asserted identically on every record from that tenant. The real 040 is available from SRS (`/source-storage/records`) if they want it grounded in the record. |
| `bf:identifiedBy` | `identifiers[]` | One node per `{identifierTypeId, value}` pair — resolve `identifierTypeId` via `fc.identifier_types` for both `bf:source` (the label) and the RDF `@type` (e.g. OCLC → `bf:Oclc`, ISMN → `bf:Ismn`, UPC → `bf:Upc`, System control number → `bf:Local`, everything else → generic `bf:Identifier`). `rdf:value` = `value`. **Don't dedupe across different `identifierTypeId`s that share the same value** — real FOLIO/MARC records can legitimately (if messily) tag one barcode-like value under three different identifier types; that's a data-quality fact about the record, not a mapping bug. |
| `bf:media` / `bf:carrier` | `instanceFormatIds[]` | Resolve via `fc.instance_formats` to a label like `"computer -- online resource"`, then split once on `" -- "` into media term / carrier term, each as `{"rdfs:label": ...}`. |
| `bf:issuance` | `modeOfIssuanceId` | Resolve via `fc.modes_of_issuance`; `{"rdfs:label": <name>}`. |
| `bf:extent` | `physicalDescriptions[]` | One `{"rdfs:label": ...}` node per string. |
| `bf:provisionActivity` | `publication[]` | Entry with `role == "Publication"` → `{"@type": "bf:Publication", "bflc:simpleAgent": publisher, "bflc:simplePlace": place, "bflc:simpleDate": dateOfPublication}`. Entry with `role == "Copyright notice date"` → `{"@type": "bf:CopyrightDate", "bflc:simpleDate": dateOfPublication}`. |
| `bf:electronicLocator` | `electronicAccess[]` | `{"rdf:value": uri, "rdfs:label": linkText, "bf:note": publicNote}`. (`relationshipId` resolves via `fc.electronic_access_relationships` if you need the relator label too.) |
| `bf:note` | `notes[]` with note type "Source of Description note" | `{"@type": "bf:Note", "bf:noteType": "Source of Description note", "rdfs:label": note}`. All other note types go on the Work (see above). |
| *(not modeled)* | Holdings record (location, call number, etc.) | This skill only covers Work + Instance. Holdings/Item-level BIBFRAME modeling is out of scope — the Holdings JSON is only used by `folio-inventory-retrieval` for context (e.g. confirming the record has available copies), not transformed here. |

## Saving the RDF

Write **four** files to `output/{hrid}/` — each graph in both serializations:

| File | Contents |
|---|---|
| `bf_work.jsonld` | Work, JSON-LD — the payload `blue-core-mcp-ingestion` POSTs |
| `bf_work.ttl` | Work, Turtle — what `bibframe-validation` reads |
| `bf_instance.jsonld` | Instance, JSON-LD |
| `bf_instance.ttl` | Instance, Turtle |

These names are not arbitrary: the two downstream stages read them literally. A single
`{hrid}.ttl`/`{hrid}.json` pair would be one filename for two graphs and would break stages 3 and 4.

Serialize the JSON-LD first and derive the Turtle from it, so the two cannot drift:

```python
from rdflib import Graph
for name, doc in [("bf_work", work), ("bf_instance", binst)]:
    (OUT / f"{name}.jsonld").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    g = Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    g.serialize(destination=str(OUT / f"{name}.ttl"), format="turtle")
```

Use `ensure_ascii=False` on every write — these records carry diacritics and non-Latin script
(e.g. `a13806931`'s Turkish title), and escaping them makes the artifacts unreadable for no benefit.

Note that `blue-core-mcp-ingestion` rewrites `bf_instance.jsonld` after ingestion, repointing
`bf:instanceOf` at the URI the server actually returned. It does not regenerate `bf_instance.ttl`,
so once a record has been ingested the `.jsonld` is the authoritative copy.