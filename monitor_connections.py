#!/usr/bin/env python3
"""
Monitor PostgreSQL connections in real-time to debug connection pool usage.
"""

import time
import psycopg2
import os
from datetime import datetime

def get_connection_stats():
    """Get current PostgreSQL connection statistics."""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=os.environ.get('POSTGRES_DB', 'localknowledge'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', ''),
            host=os.environ.get('POSTGRES_HOST', 'localhost'),
            port=os.environ.get('POSTGRES_PORT', '5432')
        )
        
        cursor = conn.cursor()
        
        # Get active connections
        cursor.execute("""
        SELECT 
            count(*) as total_connections,
            count(*) FILTER (WHERE state = 'active') as active_connections,
            count(*) FILTER (WHERE state = 'idle') as idle_connections,
            count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
        FROM pg_stat_activity 
        WHERE datname = %s
        """, (os.environ.get('POSTGRES_DB', 'localknowledge'),))
        
        stats = cursor.fetchone()
        
        # Get detailed connection info
        cursor.execute("""
        SELECT 
            pid,
            usename,
            application_name,
            client_addr,
            state,
            query_start,
            state_change,
            substring(query, 1, 50) as query_snippet
        FROM pg_stat_activity 
        WHERE datname = %s
        ORDER BY state_change DESC
        """, (os.environ.get('POSTGRES_DB', 'localknowledge'),))
        
        connections = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return {
            'total': stats[0],
            'active': stats[1], 
            'idle': stats[2],
            'idle_in_transaction': stats[3],
            'connections': connections
        }
        
    except Exception as e:
        print(f"Error getting connection stats: {e}")
        return None

def monitor_connections(interval=2):
    """Monitor connections continuously."""
    print("PostgreSQL Connection Monitor")
    print("=" * 60)
    print(f"Database: {os.environ.get('POSTGRES_DB', 'localknowledge')}")
    print(f"Monitoring every {interval} seconds...")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        while True:
            stats = get_connection_stats()
            if stats:
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                print(f"\r[{timestamp}] Total: {stats['total']:2d} | "
                      f"Active: {stats['active']:2d} | "
                      f"Idle: {stats['idle']:2d} | "
                      f"Idle-in-tx: {stats['idle_in_transaction']:2d}", end="")
                
                # Show detailed info if there are active connections
                if stats['active'] > 1:  # More than just our monitoring connection
                    print()
                    print("Active connections:")
                    for conn in stats['connections']:
                        if conn[4] == 'active' and 'pg_stat_activity' not in str(conn[7]):
                            pid, user, app, addr, state, query_start, state_change, query = conn
                            print(f"  PID {pid}: {app} - {query}")
                    print()
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor PostgreSQL connections')
    parser.add_argument('--interval', type=int, default=2, help='Monitoring interval in seconds')
    parser.add_argument('--once', action='store_true', help='Show stats once and exit')
    
    args = parser.parse_args()
    
    if args.once:
        stats = get_connection_stats()
        if stats:
            print(f"Total connections: {stats['total']}")
            print(f"Active connections: {stats['active']}")
            print(f"Idle connections: {stats['idle']}")
            print(f"Idle in transaction: {stats['idle_in_transaction']}")
            
            if stats['connections']:
                print("\nConnection details:")
                for conn in stats['connections']:
                    pid, user, app, addr, state, query_start, state_change, query = conn
                    print(f"  PID {pid}: {user}@{addr} [{state}] {app} - {query}")
    else:
        monitor_connections(args.interval)
