#!/bin/bash
# Script to create a test database and execute the schema.sql file

# Test database name
TEST_DB="test_rwb"

# Database user
DB_USER="rwbadmin"

# Drop the test database if it exists
echo "Dropping test database $TEST_DB if it exists..."
dropdb --if-exists -U $DB_USER $TEST_DB

# Create the test database
echo "Creating test database $TEST_DB..."
createdb -U $DB_USER $TEST_DB

# Create the vector extension
echo "Creating vector extension..."
psql -U $DB_USER -d $TEST_DB -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Execute the schema file
echo "Executing schema.sql..."
psql -U $DB_USER -d $TEST_DB -f modified_schema.sql

# Create and populate the version table
echo "Creating version table..."
psql -U $DB_USER -d $TEST_DB -c "
CREATE TABLE IF NOT EXISTS version (
    version INTEGER UNIQUE NOT NULL,
    migrated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    migration_success BOOLEAN NOT NULL
);

INSERT INTO version (version, migrated, migration_success)
VALUES (1, CURRENT_TIMESTAMP, TRUE)
ON CONFLICT (version) DO NOTHING;
"

echo "Done!"
