"""JustPhone MCP Server — Phone Book for voice-controlled telephony."""

import asyncio
import logging
import os
import sys
import time
import json
import sqlite3

from fastmcp import FastMCP
from pydantic import Field

logger = logging.getLogger("justphone")
logging.basicConfig(
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
    level=logging.INFO,
    stream=sys.stderr,
)

# Database: SQLite for local/PoC, MySQL for production
DB_PATH = os.getenv("DB_PATH", "justphone.db")
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")  # "sqlite" or "mysql"


def get_connection():
    """Get database connection based on backend."""
    if DB_BACKEND == "mysql":
        import mysql.connector
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", os.getenv("MYSQL_USERNAME", "root")),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "justphone"),
        )
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """Create phone_book table and seed test data if empty."""
    conn = get_connection()
    cursor = conn.cursor()

    if DB_BACKEND == "mysql":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phone_book (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                phone VARCHAR(50) NOT NULL
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phone_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        """)

    cursor.execute("SELECT COUNT(*) FROM phone_book")
    row = cursor.fetchone()
    count = row[0] if isinstance(row, (tuple, list)) else row["COUNT(*)"] if isinstance(row, sqlite3.Row) else row[0]

    if count == 0:
        seed_data = [
            ("Mikhail Oskola", "+1-360-931-0000"),
            ("Anatoliy Babayev", "+1-786-253-8811"),
            ("Grigoriy", "+1-555-100-2000"),
            ("Bank of America", "+1-800-432-1000"),
            ("CVS Pharmacy", "+1-800-746-7287"),
        ]
        placeholder = "%s" if DB_BACKEND == "mysql" else "?"
        cursor.executemany(
            f"INSERT INTO phone_book (name, phone) VALUES ({placeholder}, {placeholder})",
            seed_data,
        )
        conn.commit()
        logger.info("Seeded %d contacts", len(seed_data))

    cursor.close()
    conn.close()


mcp = FastMCP("JustPhone")


def _query(sql, params=None):
    """Execute a SELECT query and return list of dicts."""
    start = time.perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    if DB_BACKEND == "mysql":
        sql = sql.replace("?", "%s")
    cursor.execute(sql, params or [])
    if DB_BACKEND == "mysql":
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
    else:
        results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    elapsed = (time.perf_counter() - start) * 1000
    logger.info("_query %.1fms rows=%d", elapsed, len(results))
    return results


def _execute(sql, params=None):
    """Execute an INSERT/UPDATE/DELETE and return (lastrowid, rowcount)."""
    start = time.perf_counter()
    conn = get_connection()
    cursor = conn.cursor()
    if DB_BACKEND == "mysql":
        sql = sql.replace("?", "%s")
    cursor.execute(sql, params or [])
    conn.commit()
    lastrowid = cursor.lastrowid
    rowcount = cursor.rowcount
    cursor.close()
    conn.close()
    elapsed = (time.perf_counter() - start) * 1000
    logger.info("_execute %.1fms rows_affected=%d", elapsed, rowcount)
    return lastrowid, rowcount


@mcp.tool()
def get_phone_book(
    search: str = Field(default="", description="Name to search for. Leave empty to get all contacts."),
) -> str:
    """Look up contacts in the phone book.

    Returns all contacts, or searches by name (case-insensitive).
    Use when the user asks to show contacts, find a number, or call someone.
    """
    logger.info("get_phone_book search=%r", search)
    if search:
        results = _query(
            "SELECT name, phone FROM phone_book WHERE name LIKE ? ORDER BY name",
            [f"%{search}%"],
        )
    else:
        results = _query("SELECT name, phone FROM phone_book ORDER BY name")

    if not results:
        return json.dumps({"message": f"No contacts found{' for: ' + search if search else ''}", "contacts": []})
    return json.dumps({"contacts": results, "count": len(results)})


@mcp.tool()
def add_contact(
    name: str = Field(description="Full name of the contact"),
    phone: str = Field(description="Phone number in any format"),
) -> str:
    """Add a new contact to the phone book.

    Use when the user wants to save a new number or remember a contact.
    """
    logger.info("add_contact name=%r phone=%r", name, phone)
    if not name.strip():
        raise ValueError("Name cannot be empty. Provide a contact name.")
    if not phone.strip():
        raise ValueError("Phone cannot be empty. Provide a phone number.")
    lastrowid, _ = _execute(
        "INSERT INTO phone_book (name, phone) VALUES (?, ?)",
        [name.strip(), phone.strip()],
    )
    return json.dumps({"message": f"Contact added: {name} — {phone}", "id": lastrowid})


@mcp.tool()
def update_contact(
    name: str = Field(description="Current name of the contact to update"),
    new_phone: str = Field(default="", description="New phone number (leave empty to keep current)"),
    new_name: str = Field(default="", description="New name (leave empty to keep current)"),
) -> str:
    """Update an existing contact's name or phone number.

    Use when the user wants to change a contact's details.
    """
    logger.info("update_contact name=%r new_phone=%r new_name=%r", name, new_phone, new_name)
    if not new_phone and not new_name:
        raise ValueError("Provide new_phone or new_name to update. At least one is required.")

    updates = []
    params = []
    if new_phone:
        updates.append("phone = ?")
        params.append(new_phone.strip())
    if new_name:
        updates.append("name = ?")
        params.append(new_name.strip())
    params.append(name)

    _, rowcount = _execute(
        f"UPDATE phone_book SET {', '.join(updates)} WHERE name = ?",
        params,
    )
    if rowcount == 0:
        raise ValueError(f"Contact '{name}' not found. Use get_phone_book to see available contacts.")
    return json.dumps({"message": f"Contact '{name}' updated.", "rows_affected": rowcount})


@mcp.tool()
def delete_contact(
    name: str = Field(description="Name of the contact to delete"),
) -> str:
    """Delete a contact from the phone book.

    Use when the user wants to remove someone from contacts.
    """
    logger.info("delete_contact name=%r", name)
    _, rowcount = _execute("DELETE FROM phone_book WHERE name = ?", [name])
    if rowcount == 0:
        raise ValueError(f"Contact '{name}' not found. Use get_phone_book to see available contacts.")
    return json.dumps({"message": f"Contact '{name}' deleted.", "rows_deleted": rowcount})


if __name__ == "__main__":
    import uvicorn
    from starlette.applications import Starlette

    init_db()
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    logger.info("Starting JustPhone MCP (%s) on 0.0.0.0:%d (SSE + streamable-http)", DB_BACKEND, port)

    # Combine both transports into one app:
    #   /mcp      — streamable-http (VAPI, ElevenLabs, MCP Inspector)
    #   /sse      — SSE (ElevenLabs, MCP Inspector, legacy clients)
    #   /messages — SSE message endpoint
    http_app = mcp.http_app(transport="streamable-http")
    sse_app = mcp.http_app(transport="sse")
    app = Starlette(
        routes=list(http_app.routes) + list(sse_app.routes),
        lifespan=http_app.lifespan,
    )

    uvicorn.run(app, host="0.0.0.0", port=port)
