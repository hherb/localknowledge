import os
import psycopg2 as psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP

DOTENV_FILE="~/.env_mcp"

# Load environment variables from .env_mcp
load_dotenv(os.path.abspath(os.path.expanduser(DOTENV_FILE)))

# Retrieve database configuration from environment variables
DB_CONFIG = {
    "dbname": "knowledgebase", #os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", 5432))
}

print(f"initiating postgres read-only server with parameters: {DB_CONFIG}")

# Initialize the FastMCP server with auto-approval for all queries
mcp = FastMCP(
    name="PostgreSQL Read-Only MCP Server",
    auto_approve=True  # Auto-approve all queries without requiring user confirmation
)

@mcp.tool()
def query_postgres(sql: str, limit: int = 1000) -> str:
    """
    Execute a read-only SELECT query on the PostgreSQL database.

    Args:
        sql: The SQL query to execute
        limit: Maximum number of rows to return (default: 1000)

    Returns:
        Formatted query results
    """
    # Enforce read-only by allowing only SELECT statements
    sql_lower = sql.strip().lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("show") or
            sql_lower.startswith("explain") or sql_lower.startswith("with")):
        return "Error: Only read-only queries (SELECT, SHOW, EXPLAIN, WITH) are permitted."

    # Add LIMIT clause if not already present and if it's a SELECT query that returns rows
    if ("limit" not in sql_lower and
        not sql_lower.startswith("explain") and
        sql_lower.startswith("select") and
        not sql_lower.startswith("select current_database()") and
        not sql_lower.startswith("select version()") and
        not "pg_" in sql_lower):  # Skip system queries
        sql = f"{sql} LIMIT {limit}"

    try:
        # Connect to the database
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                # Execute the query
                cur.execute(sql)

                # Get column names
                column_names = [desc[0] for desc in cur.description] if cur.description else []

                # Fetch all rows
                rows = cur.fetchall()

                if not rows:
                    return "Query executed successfully, but no results were returned."

                # Format the result as a string with column headers
                if column_names:
                    # Calculate column widths
                    col_widths = [len(col) for col in column_names]
                    for row in rows:
                        for i, val in enumerate(row):
                            col_widths[i] = max(col_widths[i], len(str(val)))

                    # Format header
                    header = " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(column_names))
                    separator = "-" * len(header)
                    result = header + "\n" + separator + "\n"

                    # Format rows
                    for row in rows:
                        result += " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)) + "\n"

                    # Add row count and truncation notice if needed
                    result += f"\n({len(rows)} rows)"
                    if len(rows) == limit and "limit" not in sql_lower:
                        result += f" (Results limited to {limit} rows. Add LIMIT clause to change.)"
                else:
                    # Fallback to simple formatting if no column names
                    result = "\n".join(str(row) for row in rows)

                return result
    except Exception as e:
        return f"Error executing query: {e}"

if __name__ == "__main__":
    # Run the MCP server over standard input/output
    mcp.run(transport="stdio")