import os
import psycopg2 as psycopg
from dotenv import load_dotenv
from fastmcp import FastMCP

DOTENV_FILE="~/.env_mcp"

# Load environment variables from .env_mcp
load_dotenv(os.path.abspath(os.path.expanduser(DOTENV_FILE)))

# Retrieve database configuration from environment variables
DB_CONFIG = {
    "dbname": "knolwedgebase", #os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "host": os.getenv("POSTGRES_HOST"),
    "port": int(os.getenv("POSTGRES_PORT", 5432))
}

print(f"initiating postgres read-only server with parameters: {DB_CONFIG}")

# Initialize the FastMCP server
mcp = FastMCP(name="PostgreSQL Read-Only MCP Server")

@mcp.tool()
def query_postgres(sql: str) -> str:
    """
    Execute a read-only SELECT query on the PostgreSQL database.
    """
    # Enforce read-only by allowing only SELECT statements
    sql_lower = sql.strip().lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("show") or
            sql_lower.startswith("explain") or sql_lower.startswith("with")):
        return "Error: Only read-only queries (SELECT, SHOW, EXPLAIN, WITH) are permitted."

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

                # Get column names
                column_names = [desc[0] for desc in cur.description] if cur.description else []

                # Fetch all rows
                rows = cur.fetchall()

                if not rows:
                    return "Query executed successfully, but no results were returned."

                # Format the result as a string with column headers
                if column_names:
                    # Add column headers
                    result = " | ".join(column_names) + "\n"
                    result += "-" * len(result) + "\n"

                    # Add rows
                    for row in rows:
                        result += " | ".join(str(value) for value in row) + "\n"

                    # Add row count
                    result += f"\n({len(rows)} rows)"
                else:
                    # Fallback to simple formatting if no column names
                    result = "\n".join(str(row) for row in rows)

                return result
    except Exception as e:
        return f"Error executing query: {e}"

if __name__ == "__main__":
    # Run the MCP server over standard input/output
    mcp.run(transport="stdio")