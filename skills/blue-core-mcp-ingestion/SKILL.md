---
name: blue-core-mcp-ingestion
description: Uses Blue Core MCP endpoint to add BIBFRAME Works and Instances to the Blue Core Datastore
---
## Variables for Blue Core
The Blue Core URL, username, and password should be set to the following environmental
variables `BLUECORE_URL`, `BLUECORE_USER`, and `BLUECORE_PASSWORD`. These variables
can also be present in a `.env` file in the root directory.

## MCP Endpoint
The Blue Core MCP endpoint is available at `$BLUECORE_URL/api/mcp` but a helper proxy 
to use authenticated routes is available at `scripts/blue_core_mcp.py`.

