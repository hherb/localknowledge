#!/usr/bin/env python
"""
Script to check the document table structure.
"""

from localknowledge.db.connection_pool import get_cursor, initialize_pool

def main():
    """Main function to check the document table structure."""
    # Initialize the connection pool
    initialize_pool(min_connections=1, max_connections=2)

    # List all tables in the database
    with get_cursor() as cursor:
        cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
        """)
        tables = cursor.fetchall()
        print("Tables in database:", [table[0] for table in tables])

        # Check document table structure
        cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'document'
        ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print("\nDocument table columns:", [col[0] for col in columns])

        # Get a sample row
        cursor.execute("SELECT * FROM document LIMIT 1")
        row = cursor.fetchone()
        if row:
            print("\nSample document row:")
            for key, value in dict(row).items():
                print(f"  {key}: {value}")

        # Check if there's a pubmed_articles table
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'pubmed_articles'
        )
        """)
        has_pubmed = cursor.fetchone()[0]

        # Check if there's a preprints table
        cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'preprints'
        )
        """)
        has_preprints = cursor.fetchone()[0]

        print(f"\nHas pubmed_articles table: {has_pubmed}")
        print(f"Has preprints table: {has_preprints}")

        # Check the sources table
        cursor.execute("""
        SELECT * FROM sources
        """)
        sources = cursor.fetchall()
        if sources:
            print("\nSources table contents:")
            for source in sources:
                print(f"  {dict(source)}")

        # Check if source_id in document table corresponds to specific sources
        cursor.execute("""
        SELECT DISTINCT source_id FROM document
        """)
        source_ids = [row[0] for row in cursor.fetchall()]
        print(f"\nDistinct source_id values in document table: {source_ids}")

        # Get sample documents with different source_ids and join with sources
        cursor.execute("""
        SELECT d.id, d.title, d.source_id, s.name, s.url
        FROM document d
        JOIN sources s ON d.source_id = s.id
        ORDER BY d.source_id
        LIMIT 10
        """)
        docs = cursor.fetchall()
        if docs:
            print("\nSample documents with source information:")
            for doc in docs:
                print(f"  Document ID: {doc['id']}")
                print(f"  Title: {doc['title']}")
                print(f"  Source ID: {doc['source_id']}")
                print(f"  Source Name: {doc['name']}")
                print(f"  Source URL: {doc['url']}")
                print()

if __name__ == "__main__":
    main()
