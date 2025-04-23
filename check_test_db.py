#!/usr/bin/env python3
"""
Script to check the structure of the test database.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load environment variables
dotenv_file = os.environ.get('DOTENV_FILE', '.env')
if os.path.exists(dotenv_file):
    load_dotenv(dotenv_file)
else:
    load_dotenv()

# Connection parameters
user = os.environ.get('POSTGRES_USER', 'postgres')
password = os.environ.get('POSTGRES_PASSWORD', '')
host = os.environ.get('POSTGRES_HOST', 'localhost')
port = os.environ.get('POSTGRES_PORT', '5432')
dbname = 'test_rwb'  # Use the test database

# Connect to the database
try:
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("""
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename
    """)
    tables = cursor.fetchall()

    print(f"Tables in database '{dbname}':")
    if tables:
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("  No tables found!")

    # Print database connection info
    print(f"\nDatabase connection info:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Database: {dbname}")
    print(f"  User: {user}")

    # Check if version table exists and has the initial record
    cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'version'
    )
    """)
    version_table_exists = cursor.fetchone()[0]

    if version_table_exists:
        cursor.execute("SELECT version, migration_success FROM version")
        version_records = cursor.fetchall()
        print("\nVersion records:")
        for record in version_records:
            print(f"  - Version {record[0]}, Success: {record[1]}")
    else:
        print("\nVersion table does not exist!")

    # Check if vector extension is installed
    cursor.execute("""
    SELECT extname, extversion
    FROM pg_extension
    WHERE extname = 'vector'
    """)
    vector_extension = cursor.fetchone()

    if vector_extension:
        print(f"\nVector extension installed: {vector_extension[0]} version {vector_extension[1]}")
    else:
        print("\nVector extension is NOT installed!")

    # Close connection
    cursor.close()
    conn.close()

except psycopg2.Error as e:
    print(f"Error connecting to database: {e}")
    sys.exit(1)
