# JustPhone MCP Server

Phone book MCP server for voice-controlled telephony. Provides CRUD operations on contacts via MCP protocol.

## Transports

The server exposes two MCP transports on a single port:

| Endpoint | Transport | Use with |
|----------|-----------|----------|
| `/mcp` | Streamable HTTP | VAPI, ElevenLabs, MCP Inspector |
| `/sse` | SSE | ElevenLabs, legacy MCP clients |

## Tools

| Tool | Description |
|------|-------------|
| `get_phone_book` | List all contacts or search by name |
| `add_contact` | Add a new contact (name + phone) |
| `update_contact` | Update name or phone of existing contact |
| `delete_contact` | Remove a contact by name |

## Run locally

```bash
pip install "fastmcp>=2.14.0,<3"
python server.py
```

Server starts on `http://localhost:8000`. Uses SQLite by default (creates `justphone.db`).

## Run with Docker

```bash
docker build -t justphone-mcp .
docker run --rm -p 8000:8000 justphone-mcp
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port |
| `DB_BACKEND` | `sqlite` | `sqlite` or `mysql` |
| `DB_PATH` | `justphone.db` | SQLite database path |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `root` | MySQL user |
| `MYSQL_PASSWORD` | (empty) | MySQL password |
| `MYSQL_DATABASE` | `justphone` | MySQL database name |

## Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Enter the server URL (e.g. `http://localhost:8000/mcp`) and test tool calls interactively.

## Production

Deployed on Zeabur with MySQL backend.
