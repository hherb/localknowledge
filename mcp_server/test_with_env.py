#!/usr/bin/env python3
"""
Test script that sets up environment variables and runs the MCP client test

This script ensures the database environment variables are properly set
before running the MCP client test.
"""

import os
import asyncio
import subprocess
import sys

def setup_environment():
    """Set up database environment variables"""
    # You may need to adjust these values for your setup
    env_vars = {
        'POSTGRES_DB': 'localknowledge',  # Adjust this to your database name
        'POSTGRES_USER': 'postgres',      # Adjust this to your username
        'POSTGRES_PASSWORD': '',          # Adjust this to your password
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432'
    }
    
    print("Setting up database environment variables...")
    for key, value in env_vars.items():
        if key not in os.environ:
            os.environ[key] = value
            print(f"  {key} = {value}")
        else:
            print(f"  {key} = {os.environ[key]} (already set)")

def test_database_connection():
    """Test if we can connect to the database"""
    try:
        # Import here to ensure environment variables are set first
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from localknowledge.db.connection_pool import get_cursor
        
        print("\n🔗 Testing database connection...")
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                print("✓ Database connection successful")
                return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def run_mcp_test():
    """Run the MCP client test"""
    print("\n" + "=" * 60)
    print("Running MCP Client Test...")
    print("=" * 60)
    
    # Import and run the test client
    from proper_mcp_client_test import LocalKnowledgeTestClient
    
    client = LocalKnowledgeTestClient()
    await client.test_all_tools()

def main():
    """Main function"""
    print("LocalKnowledge MCP Server Test with Environment Setup")
    print("=" * 60)
    
    # Set up environment
    setup_environment()
    
    # Test database connection
    if not test_database_connection():
        print("\n❌ Cannot proceed without database connection.")
        print("Please check your database configuration and try again.")
        print("\nYou may need to:")
        print("1. Start your PostgreSQL server")
        print("2. Create the localknowledge database")
        print("3. Update the environment variables in this script")
        return
    
    # Run MCP test
    try:
        asyncio.run(run_mcp_test())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
