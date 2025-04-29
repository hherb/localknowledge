#!/usr/bin/env python3
"""
Script to check constraints on the chunks table.
"""

import sys
from localknowledge.db.basic_infrastructure import load_environment
from localknowledge.db.connection_pool import get_cursor

def main():
    """Main function."""
    # Load environment variables
    load_environment()
    
    print("Checking constraints on the chunks table")
    
    try:
        with get_cursor() as cursor:
            # Get constraints on the chunks table
            query = """
            SELECT con.conname as constraint_name,
                   con.contype as constraint_type,
                   pg_get_constraintdef(con.oid) as constraint_definition
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = 'chunks'
            """
            
            # Execute the query
            cursor.execute(query)
            
            # Fetch all constraints
            constraints = cursor.fetchall()
            
            # Print results
            print(f"Found {len(constraints)} constraints:")
            for constraint in constraints:
                constraint_type = constraint['constraint_type']
                type_desc = ""
                if constraint_type == 'p':
                    type_desc = "PRIMARY KEY"
                elif constraint_type == 'u':
                    type_desc = "UNIQUE"
                elif constraint_type == 'f':
                    type_desc = "FOREIGN KEY"
                elif constraint_type == 'c':
                    type_desc = "CHECK"
                
                print(f"Constraint: {constraint['constraint_name']} ({type_desc})")
                print(f"  Definition: {constraint['constraint_definition']}")
                print()
            
            # Check if there's a unique constraint on document_id, chunking_strategy_id, and chunk_no
            unique_constraint_exists = False
            for constraint in constraints:
                if constraint['constraint_type'] == 'u' and 'document_id' in constraint['constraint_definition'] and 'chunking_strategy_id' in constraint['constraint_definition'] and 'chunk_no' in constraint['constraint_definition']:
                    unique_constraint_exists = True
                    break
            
            if not unique_constraint_exists:
                print("No unique constraint found on (document_id, chunking_strategy_id, chunk_no)")
                print("This could allow duplicate chunks to be inserted")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
