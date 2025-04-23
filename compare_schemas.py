#!/usr/bin/env python3
"""
Script to compare the schema of the test database with the production database.
"""

import os
import sys
import psycopg2
import json
from dotenv import load_dotenv
from tabulate import tabulate

# Load environment variables
dotenv_file = os.environ.get('DOTENV_FILE', '.env')
if os.path.exists(dotenv_file):
    load_dotenv(dotenv_file)
else:
    load_dotenv()

# Production database connection parameters
prod_user = os.environ.get('POSTGRES_USER', 'postgres')
prod_password = os.environ.get('POSTGRES_PASSWORD', '')
prod_host = os.environ.get('POSTGRES_HOST', 'localhost')
prod_port = os.environ.get('POSTGRES_PORT', '5432')
prod_dbname = os.environ.get('POSTGRES_DB')

# Test database connection parameters
test_user = prod_user
test_password = prod_password
test_host = prod_host
test_port = prod_port
test_dbname = 'test_rwb'

def get_schema_info(dbname, user, password, host, port):
    """Get schema information from a database."""
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Get table details
        table_details = {}
        for table in tables:
            # Get columns
            cursor.execute(f"""
            SELECT column_name, data_type, character_maximum_length, 
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = '{table}'
            ORDER BY ordinal_position
            """)
            columns = [
                {
                    'name': row[0],
                    'type': row[1],
                    'length': row[2],
                    'nullable': row[3],
                    'default': row[4]
                }
                for row in cursor.fetchall()
            ]
            
            # Get constraints
            cursor.execute(f"""
            SELECT con.conname, con.contype, 
                   pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = '{table}'
            AND nsp.nspname = 'public'
            """)
            constraints = [
                {
                    'name': row[0],
                    'type': row[1],
                    'definition': row[2]
                }
                for row in cursor.fetchall()
            ]
            
            # Get indices
            cursor.execute(f"""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = '{table}'
            """)
            indices = [
                {
                    'name': row[0],
                    'definition': row[1]
                }
                for row in cursor.fetchall()
            ]
            
            table_details[table] = {
                'columns': columns,
                'constraints': constraints,
                'indices': indices
            }
        
        cursor.close()
        conn.close()
        
        return {
            'tables': tables,
            'table_details': table_details
        }
    except psycopg2.Error as e:
        print(f"Error connecting to database {dbname}: {e}")
        sys.exit(1)

def compare_schemas(prod_schema, test_schema):
    """Compare production and test schemas."""
    # Compare tables
    prod_tables = set(prod_schema['tables'])
    test_tables = set(test_schema['tables'])
    
    missing_in_test = prod_tables - test_tables
    missing_in_prod = test_tables - prod_tables
    common_tables = prod_tables.intersection(test_tables)
    
    print(f"\n{'=' * 80}")
    print("TABLE COMPARISON")
    print(f"{'=' * 80}")
    print(f"Production database: {prod_dbname}")
    print(f"Test database: {test_dbname}")
    print(f"{'=' * 80}")
    
    print(f"\nTables in production but missing in test ({len(missing_in_test)}):")
    for table in sorted(missing_in_test):
        print(f"  - {table}")
    
    print(f"\nTables in test but missing in production ({len(missing_in_prod)}):")
    for table in sorted(missing_in_prod):
        print(f"  - {table}")
    
    print(f"\nCommon tables ({len(common_tables)}):")
    for table in sorted(common_tables):
        print(f"  - {table}")
    
    # Compare table details for common tables
    differences = []
    
    for table in sorted(common_tables):
        prod_details = prod_schema['table_details'][table]
        test_details = test_schema['table_details'][table]
        
        # Compare columns
        prod_columns = {col['name']: col for col in prod_details['columns']}
        test_columns = {col['name']: col for col in test_details['columns']}
        
        prod_col_names = set(prod_columns.keys())
        test_col_names = set(test_columns.keys())
        
        missing_cols_in_test = prod_col_names - test_col_names
        missing_cols_in_prod = test_col_names - prod_col_names
        common_cols = prod_col_names.intersection(test_col_names)
        
        if missing_cols_in_test:
            differences.append({
                'table': table,
                'type': 'missing_columns_in_test',
                'details': sorted(missing_cols_in_test)
            })
        
        if missing_cols_in_prod:
            differences.append({
                'table': table,
                'type': 'missing_columns_in_prod',
                'details': sorted(missing_cols_in_prod)
            })
        
        # Compare column details
        for col_name in common_cols:
            prod_col = prod_columns[col_name]
            test_col = test_columns[col_name]
            
            # Compare data type
            if prod_col['type'] != test_col['type']:
                differences.append({
                    'table': table,
                    'type': 'column_type_mismatch',
                    'details': f"Column '{col_name}': Production type '{prod_col['type']}', Test type '{test_col['type']}'"
                })
            
            # Compare nullability
            if prod_col['nullable'] != test_col['nullable']:
                differences.append({
                    'table': table,
                    'type': 'column_nullable_mismatch',
                    'details': f"Column '{col_name}': Production nullable '{prod_col['nullable']}', Test nullable '{test_col['nullable']}'"
                })
        
        # Compare constraints (simplified)
        prod_constraint_defs = {c['definition'] for c in prod_details['constraints']}
        test_constraint_defs = {c['definition'] for c in test_details['constraints']}
        
        missing_constraints_in_test = prod_constraint_defs - test_constraint_defs
        missing_constraints_in_prod = test_constraint_defs - prod_constraint_defs
        
        if missing_constraints_in_test:
            differences.append({
                'table': table,
                'type': 'missing_constraints_in_test',
                'details': sorted(missing_constraints_in_test)
            })
        
        if missing_constraints_in_prod:
            differences.append({
                'table': table,
                'type': 'missing_constraints_in_prod',
                'details': sorted(missing_constraints_in_prod)
            })
        
        # Compare indices (simplified)
        prod_index_defs = {i['definition'] for i in prod_details['indices']}
        test_index_defs = {i['definition'] for i in test_details['indices']}
        
        missing_indices_in_test = prod_index_defs - test_index_defs
        missing_indices_in_prod = test_index_defs - prod_index_defs
        
        if missing_indices_in_test:
            differences.append({
                'table': table,
                'type': 'missing_indices_in_test',
                'details': sorted(missing_indices_in_test)
            })
        
        if missing_indices_in_prod:
            differences.append({
                'table': table,
                'type': 'missing_indices_in_prod',
                'details': sorted(missing_indices_in_prod)
            })
    
    # Print differences
    print(f"\n{'=' * 80}")
    print("SCHEMA DIFFERENCES")
    print(f"{'=' * 80}")
    
    if not differences:
        print("\nNo schema differences found for common tables!")
    else:
        print(f"\nFound {len(differences)} differences:")
        
        # Group differences by table
        table_diffs = {}
        for diff in differences:
            table = diff['table']
            if table not in table_diffs:
                table_diffs[table] = []
            table_diffs[table].append(diff)
        
        for table, diffs in sorted(table_diffs.items()):
            print(f"\nTable: {table}")
            for diff in diffs:
                print(f"  - {diff['type']}:")
                if isinstance(diff['details'], list):
                    for detail in diff['details']:
                        print(f"      {detail}")
                else:
                    print(f"      {diff['details']}")

def main():
    """Main function."""
    print(f"Comparing schemas between production database '{prod_dbname}' and test database '{test_dbname}'...")
    
    # Get schema information
    print("Extracting production database schema...")
    prod_schema = get_schema_info(prod_dbname, prod_user, prod_password, prod_host, prod_port)
    
    print("Extracting test database schema...")
    test_schema = get_schema_info(test_dbname, test_user, test_password, test_host, test_port)
    
    # Compare schemas
    compare_schemas(prod_schema, test_schema)

if __name__ == "__main__":
    main()
