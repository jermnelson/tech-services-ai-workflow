#!/usr/bin/env python3
"""MCP stdio-to-HTTP proxy for the Blue Core API.

Bridges Claude Code's stdio MCP transport to the Blue Core HTTP MCP server,
injecting a Keycloak Bearer token obtained via get_token().
"""

import asyncio
import json
import sys
import os

import httpx


BLUECORE_URL = os.environ.get("BLUECORE_URL", "http://localhost")
BLUECORE_USER = os.environ.get("BLUECORE_USER", "developer")
BLUECORE_PASSWORD = os.environ.get("BLUECORE_PASSWORD", "123456")

def get_token(url=BLUECORE_URL, username=BLUECORE_PASSWORD, password=BLUECORE_PASSWORD):
    keycloak_token = httpx.post(f"{url}/keycloak/realms/bluecore/protocol/openid-connect/token",
                      data={
                          "client_id": "bluecore_api",
                          "username": username,
                          "password": password,
                          "grant_type": "password",
                      })
    
    keycloak_token.raise_for_status()
    return keycloak_token.json().get('access_token')

MCP_URL = f"{BLUECORE_URL}/api/mcp"


async def proxy() -> None:
    token = get_token()
    session_id: str | None = None

    async with httpx.AsyncClient(timeout=60.0) as client:

        async def send(message: dict) -> None:
            nonlocal session_id

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if session_id:
                headers["Mcp-Session-Id"] = session_id

            response = await client.post(MCP_URL, json=message, headers=headers)

            if sid := response.headers.get("Mcp-Session-Id"):
                session_id = sid

            if response.status_code == 202:
                return  # notification accepted, no body

            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" in content_type:
                for line in response.text.splitlines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data and data != "[DONE]":
                            sys.stdout.write(data + "\n")
                            sys.stdout.flush()
            elif response.text.strip():
                sys.stdout.write(response.text.strip() + "\n")
                sys.stdout.flush()

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
        )

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break
            line = line_bytes.decode().strip()
            if not line:
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            try:
                await send(message)
            except httpx.HTTPStatusError as exc:
                msg_id = message.get("id")
                if msg_id is not None:
                    err = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(exc)},
                    }
                    sys.stdout.write(json.dumps(err) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                sys.stderr.write(f"blue_core_mcp proxy error: {exc}\n")
                sys.stderr.flush()


if __name__ == "__main__":
    asyncio.run(proxy())
