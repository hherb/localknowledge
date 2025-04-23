#!/usr/bin/env python3
"""
Script to verify that we're connecting to the test database.
This script sets POSTGRES_DB=test_rwb and then tries to connect
to the database to verify it's using the correct one.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv

# Set the test database name
TEST_DB_NAME = 'test_rwb'

# Set environment variable for test database
os.environ['POSTGRES_DB'] = TEST_DB_NAME
print(f"Set POSTGRES_DB environment variable to '{TEST_DB_NAME}'")

# Load environment variables
dotenv_file = os.environ.get('DOTENV_FILE', '.env')
if os.path.exists(dotenv_file):
    load_dotenv(dotenv_file)
else:
    load_dotenv()

# Get connection parameters
user = os.environ.get('POSTGRES_USER', 'postgres')
password = os.environ.get('POSTGRES_PASSWORD', '')
host = os.environ.get('POSTGRES_HOST', 'localhost')
port = os.environ.get('POSTGRES_PORT', '5432')
dbname = os.environ.get('POSTGRES_DB')

print(f"Environment variables after loading .env:")
print(f"  POSTGRES_DB: {dbname}")
print(f"  POSTGRES_USER: {user}")
print(f"  POSTGRES_HOST: {host}")
print(f"  POSTGRES_PORT: {port}")

# Try to connect to the database
try:
    print(f"\nAttempting to connect to database '{dbname}'...")
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    cursor = conn.cursor()
    
    # Get database name from the connection
    cursor.execute("SELECT current_database()")
    current_db = cursor.fetchone()[0]
    
    print(f"Successfully connected to database: {current_db}")
    
    # Verify it's the test database
    if current_db == TEST_DB_NAME:
        print("✅ Connected to the correct test database!")
    else:
        print(f"❌ ERROR: Connected to '{current_db}' instead of '{TEST_DB_NAME}'!")
        print("This is a serious issue that could lead to data loss in the production database.")
    
    # Close connection
    cursor.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"Error connecting to database: {e}")
    if "does not exist" in str(e):
        print(f"\nThe test database '{TEST_DB_NAME}' doesn't exist yet. This is expected.")
        print("You need to create it first using the test_baseline_creation.py script.")
    sys.exit(1)
