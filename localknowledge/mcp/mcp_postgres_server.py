#!/usr/bin/env python3

"""
MCP Server for PostgreSQL access using FastMCP and psycopg

This script creates an MCP server that allows querying a PostgreSQL database.
It uses the FastMCP library to create the server and psycopg for database connectivity.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

import psycopg
from fastmcp import MCPServer, Request, Response


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_postgres_server")


class PostgreSQLMCPServer(MCPServer):
    """MCP Server that provides access to a PostgreSQL database"""
    
    def __init__(self, connection_params: Dict[str, Any]):
        """
        Initialize the PostgreSQL MCP Server
        
        Args:
            connection_params: Dictionary with PostgreSQL connection parameters
                (host, port, dbname, user, password)
        """
        super().__init__()
        self.connection_params = connection_params
        self.conn = None
        
    def start(self) -> None:
        """Start the server and establish the database connection"""
        try:
            # Create connection string from parameters
            conn_string = " ".join([f"{k}={v}" for k, v in self.connection_params.items()])
            self.conn = psycopg.connect(conn_string)
            logger.info(f"Connected to PostgreSQL database at {self.connection_params.get('host', 'localhost')}")
            
            # Register handlers
            self.register_handler("query", self.handle_query)
            self.register_handler("tables", self.handle_tables)
            self.register_handler("schema", self.handle_schema)
            
            # Start the MCP server
            logger.info("Starting MCP Server...")
            super().start()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    def stop(self) -> None:
        """Stop the server and close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
        super().stop()
        logger.info("MCP Server stopped")
    
    async def handle_query(self, request: Request) -> Response:
        """
        Handle SQL query requests
        
        Args:
            request: The MCP request containing the SQL query to execute
            
        Returns:
            Response: The query results
        """
        try:
            # Extract SQL query from request
            sql_query = request.data.get("sql")
            params = request.data.get("params", [])
            
            if not sql_query:
                return Response(
                    success=False,
                    data={"error": "No SQL query provided"}
                )
            
            # Execute query
            logger.info(f"Executing SQL: {sql_query}")
            with self.conn.cursor() as cur:
                cur.execute(sql_query, params)
                
                # Fetch results if this is a SELECT query
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    results = cur.fetchall()
                    
                    # Convert to list of dictionaries
                    rows = []
                    for row in results:
                        rows.append(dict(zip(columns, row)))
                    
                    return Response(
                        success=True,
                        data={"results": rows, "count": len(rows)}
                    )
                else:
                    # For non-SELECT queries (INSERT, UPDATE, DELETE)
                    rowcount = cur.rowcount
                    self.conn.commit()
                    return Response(
                        success=True,
                        data={"rowcount": rowcount, "message": f"Query affected {rowcount} rows"}
                    )
                
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return Response(
                success=False,
                data={"error": str(e)}
            )
    
    async def handle_tables(self, request: Request) -> Response:
        """
        Handle request to list all tables in the database
        
        Args:
            request: The MCP request
            
        Returns:
            Response: List of tables in the database
        """
        try:
            with self.conn.cursor() as cur:
                # Query to get all tables in the current schema
                cur.execute("""
                    SELECT 
                        table_name 
                    FROM 
                        information_schema.tables 
                    WHERE 
                        table_schema = 'public'
                    ORDER BY 
                        table_name
                """)
                tables = [row[0] for row in cur.fetchall()]
                
                return Response(
                    success=True,
                    data={"tables": tables}
                )
                
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return Response(
                success=False,
                data={"error": str(e)}
            )
    
    async def handle_schema(self, request: Request) -> Response:
        """
        Handle request to get schema information for a specific table
        
        Args:
            request: The MCP request containing the table name
            
        Returns:
            Response: Schema information for the requested table
        """
        try:
            table_name = request.data.get("table")
            
            if not table_name:
                return Response(
                    success=False,
                    data={"error": "No table name provided"}
                )
            
            with self.conn.cursor() as cur:
                # Query to get column information for the table
                cur.execute("""
                    SELECT 
                        column_name, 
                        data_type, 
                        is_nullable, 
                        column_default
                    FROM 
                        information_schema.columns 
                    WHERE 
                        table_schema = 'public' AND 
                        table_name = %s
                    ORDER BY 
                        ordinal_position
                """, (table_name,))
                
                columns = []
                for row in cur.fetchall():
                    columns.append({
                        "name": row[0],
                        "type": row[1],
                        "nullable": row[2] == "YES",
                        "default": row[3]
                    })
                
                return Response(
                    success=True,
                    data={"table": table_name, "columns": columns}
                )
                
        except Exception as e:
            logger.error(f"Error getting schema: {e}")
            return Response(
                success=False,
                data={"error": str(e)}
            )


def main():
    """Main function to start the MCP server"""
    # Get database connection parameters from environment variables
    # or use default values
    connection_params = {
        "host": os.environ.get("PG_HOST", "localhost"),
        "port": os.environ.get("PG_PORT", "5432"),
        "dbname": os.environ.get("PG_DB", "postgres"),
        "user": os.environ.get("PG_USER", "postgres"),
        "password": os.environ.get("PG_PASSWORD", "")
    }
    
    # You can also hardcode these for testing, but it's not recommended for production
    # connection_params = {
    #     "host": "localhost",
    #     "port": "5432",
    #     "dbname": "your_database",
    #     "user": "your_username",
    #     "password": "your_password"
    # }
    
    # Create and start the server
    server = PostgreSQLMCPServer(connection_params)
    
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
