---
name: bibframe-transformat
description: Take a FOLIO JSON Inventory Instance and Holdings records, generate BIBFRAME Work and Instance JSON-LD 
---
With an existing JSON records for a FOLIO inventory Instance and Holdings records, reverse the mappings found
at `https://github.com/blue-core-lod/bluecore-workflows/blob/main/ils_middleware/tasks/folio/mappings/bf_instance.py` 
and `https://github.com/blue-core-lod/bluecore-workflows/blob/main/ils_middleware/tasks/folio/mappings/bf_work.py` to
generate a BIBFRAME Work RDF and a BIBFRAME Instance RDF record.
