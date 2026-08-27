---
name: folio-inventory-retrieval
description: Retrieve FOLIO JSON Inventory Instance and Holdings records from the FOLIO API
---

## Setup
Create an instance of the `FolioClient` to interact with the FOLIO API of the system.
The environmental variables are either set manually or available in an `.env` file 
in the root directory.

```python
import os
from folioclient import FolioClient

GATEWAY_URL = os.environ["GATEWAY_URL"]
TENANT = os.environ["TENANT"]
FOLIO_USER = os.environ["FOLIO_USER"]
FOLIO_PASSWORD = os.environ["FOLIO_PASSWORD"]

folio_client = FolioClient(GATEWAY_URL, 
                           TENANT,
                           FOLIO_USER,
                           FOLIO_PASSWORD)
``` 

The FOLIO API documentation:
- [Inventory module](https://s3.amazonaws.com/foliodocs/api/mod-inventory/p/inventory.html)
- [Search](https://s3.amazonaws.com/foliodocs/api/mod-search/s/mod-search.html)

## Workflow
Prompt the user for either an Instance UUID or an HRID. Use the Inventory API to retrieve the instance
and parse and then retrieve any holdings records. 

If the user doesn't know either, prompt them for a title and author and use the Search API to retrieve 
a list of matches and ask the user to choose.
