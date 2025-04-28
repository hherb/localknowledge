#!/usr/bin/env python3
"""
Test database connection
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env_embedtest")
print(f"Loading environment from: {env_file}")
load_dotenv(env_file)

# Get database connection parameters
dbname = "rwb"  # Hardcoded for testing
user = "rwbadmin"
password = "rwb2025admin"
host = "localhost"
port = "5432"

print(f"Connecting to database: {dbname}@{host}:{port}")

try:
    # Connect to the database
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )

    # Create a cursor
    cursor = conn.cursor()

    # Execute a test query
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"Successfully connected to PostgreSQL: {version}")

    # Check if the chunks table exists
    try:
        cursor.execute("SELECT COUNT(*) FROM chunks")
        count = cursor.fetchone()[0]
        print(f"Found {count} rows in the chunks table")
    except Exception as e:
        print(f"Error querying chunks table: {e}")

        # Check if we need to create the table
        print("Checking if we need to create the chunks table...")
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER,
                chunking_strategy_id INTEGER,
                chunktype_id INTEGER,
                document_title TEXT,
                text TEXT,
                chunklength INTEGER,
                chunk_no INTEGER NOT NULL,
                page_start INTEGER DEFAULT 0,
                page_end INTEGER DEFAULT 0,
                metadata JSONB
            )
            """)
            conn.commit()
            print("Created chunks table")
        except Exception as e:
            print(f"Error creating chunks table: {e}")

    # Check the embeddings table
    try:
        cursor.execute("SELECT COUNT(*) FROM emb_768")
        count = cursor.fetchone()[0]
        print(f"Found {count} rows in the emb_768 table")

        # Get some sample embeddings
        cursor.execute("""
        SELECT e.id, e.chunk_id, e.model_id, c.document_id, c.document_title
        FROM emb_768 e
        JOIN chunks c ON e.chunk_id = c.id
        LIMIT 3
        """)

        print("\nSample embeddings:")
        for row in cursor.fetchall():
            print(f"  - ID: {row[0]}, Chunk ID: {row[1]}, Model ID: {row[2]}")
            print(f"    Document ID: {row[3]}, Title: {row[4][:50]}...")

    except Exception as e:
        print(f"Error querying emb_768 table: {e}")

    # Close the cursor and connection
    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error connecting to PostgreSQL: {e}")
