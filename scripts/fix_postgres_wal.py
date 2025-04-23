#!/usr/bin/env python3
"""
Script to fix PostgreSQL WAL settings by directly editing configuration files.

This script:
1. Locates the PostgreSQL configuration files
2. Modifies the settings to fix WAL-related issues
3. Helps restart PostgreSQL safely
"""

import os
import sys
import argparse
import subprocess
import logging
import re
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Common PostgreSQL data directory locations
POSTGRES_DATA_DIRS = [
    '/var/lib/postgresql/data',
    '/usr/local/var/postgres',
    '/var/lib/pgsql/data',
    '/Library/PostgreSQL/*/data',
    '/opt/homebrew/var/postgres',
    '/opt/PostgreSQL/*/data'
]

def find_postgres_data_dir():
    """Find the PostgreSQL data directory."""
    # Try to get it from environment variable
    if 'PGDATA' in os.environ:
        data_dir = os.environ['PGDATA']
        if os.path.exists(data_dir):
            return data_dir
    
    # Try to get it from postgres command
    try:
        result = subprocess.run(
            ['postgres', '-D', ''],
            capture_output=True,
            text=True
        )
        # Parse the error message which contains the default data directory
        match = re.search(r'data directory "([^"]+)"', result.stderr)
        if match:
            data_dir = match.group(1)
            if os.path.exists(data_dir):
                return data_dir
    except Exception:
        pass
    
    # Try common locations
    for pattern in POSTGRES_DATA_DIRS:
        import glob
        for path in glob.glob(pattern):
            if os.path.exists(os.path.join(path, 'postgresql.conf')):
                return path
    
    return None

def find_postgresql_conf(data_dir=None):
    """Find the postgresql.conf file."""
    if not data_dir:
        data_dir = find_postgres_data_dir()
        if not data_dir:
            return None
    
    conf_path = os.path.join(data_dir, 'postgresql.conf')
    if os.path.exists(conf_path):
        return conf_path
    
    return None

def find_postgresql_auto_conf(data_dir=None):
    """Find the postgresql.auto.conf file."""
    if not data_dir:
        data_dir = find_postgres_data_dir()
        if not data_dir:
            return None
    
    conf_path = os.path.join(data_dir, 'postgresql.auto.conf')
    if os.path.exists(conf_path):
        return conf_path
    
    return None

def backup_file(file_path):
    """Create a backup of a file."""
    import shutil
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup of {file_path} at {backup_path}")
    return backup_path

def fix_wal_settings(conf_path, auto_conf_path=None):
    """Fix WAL settings in PostgreSQL configuration files."""
    if not conf_path:
        logger.error("No postgresql.conf file found")
        return False
    
    # Backup the configuration file
    backup_file(conf_path)
    
    # Read the configuration file
    with open(conf_path, 'r') as f:
        content = f.read()
    
    # Fix wal_level setting
    if 'wal_level' in content:
        content = re.sub(
            r'#?\s*wal_level\s*=\s*[\'"]?(\w+)[\'"]?',
            r"wal_level = 'replica'",
            content
        )
    else:
        content += "\n# Added by fix_postgres_wal.py\nwal_level = 'replica'\n"
    
    # Write the modified configuration
    with open(conf_path, 'w') as f:
        f.write(content)
    
    logger.info(f"Updated {conf_path} with wal_level = 'replica'")
    
    # Fix auto.conf if it exists
    if auto_conf_path and os.path.exists(auto_conf_path):
        # Backup the auto configuration file
        backup_file(auto_conf_path)
        
        # Read the auto configuration file
        with open(auto_conf_path, 'r') as f:
            auto_content = f.read()
        
        # Fix wal_level setting
        if 'wal_level' in auto_content:
            auto_content = re.sub(
                r'wal_level\s*=\s*[\'"]?(\w+)[\'"]?',
                r"wal_level = 'replica'",
                auto_content
            )
            
            # Write the modified auto configuration
            with open(auto_conf_path, 'w') as f:
                f.write(auto_content)
            
            logger.info(f"Updated {auto_conf_path} with wal_level = 'replica'")
    
    return True

def optimize_wal_settings(conf_path, auto_conf_path=None):
    """Optimize WAL settings for large migrations."""
    if not conf_path:
        logger.error("No postgresql.conf file found")
        return False
    
    # Backup the configuration file
    backup_file(conf_path)
    
    # Read the configuration file
    with open(conf_path, 'r') as f:
        content = f.read()
    
    # Update WAL settings
    settings = {
        'wal_level': "'replica'",
        'wal_buffers': "'128MB'",
        'max_wal_size': "'64GB'",
        'checkpoint_timeout': "'2h'",
        'checkpoint_completion_target': '0.95',
        'archive_mode': 'off',
        'synchronous_commit': 'off',
        'commit_delay': '1000',
        'commit_siblings': '5'
    }
    
    # Apply settings
    for setting, value in settings.items():
        pattern = rf'#?\s*{setting}\s*=\s*[\'"]?([^\'"\s]+)[\'"]?'
        replacement = f"{setting} = {value}"
        
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
        else:
            content += f"\n# Added by fix_postgres_wal.py\n{replacement}\n"
    
    # Write the modified configuration
    with open(conf_path, 'w') as f:
        f.write(content)
    
    logger.info(f"Updated {conf_path} with optimized WAL settings")
    
    # Clear auto.conf if it exists
    if auto_conf_path and os.path.exists(auto_conf_path):
        # Backup the auto configuration file
        backup_file(auto_conf_path)
        
        # Clear the auto configuration file
        with open(auto_conf_path, 'w') as f:
            f.write("# Cleared by fix_postgres_wal.py\n")
        
        logger.info(f"Cleared {auto_conf_path}")
    
    return True

def restore_settings(conf_path, auto_conf_path=None):
    """Restore settings from backup files."""
    if not conf_path:
        logger.error("No postgresql.conf file found")
        return False
    
    backup_path = f"{conf_path}.bak"
    if os.path.exists(backup_path):
        import shutil
        shutil.copy2(backup_path, conf_path)
        logger.info(f"Restored {conf_path} from backup")
    
    if auto_conf_path and os.path.exists(auto_conf_path):
        backup_path = f"{auto_conf_path}.bak"
        if os.path.exists(backup_path):
            import shutil
            shutil.copy2(backup_path, auto_conf_path)
            logger.info(f"Restored {auto_conf_path} from backup")
    
    return True

def main():
    """Run the script."""
    parser = argparse.ArgumentParser(description='Fix PostgreSQL WAL settings')
    parser.add_argument('--fix', action='store_true', help='Fix WAL settings')
    parser.add_argument('--optimize', action='store_true', help='Optimize WAL settings for large migrations')
    parser.add_argument('--restore', action='store_true', help='Restore settings from backup')
    parser.add_argument('--data-dir', type=str, help='PostgreSQL data directory')
    args = parser.parse_args()
    
    # Find PostgreSQL data directory
    data_dir = args.data_dir or find_postgres_data_dir()
    if not data_dir:
        logger.error("Could not find PostgreSQL data directory")
        return 1
    
    logger.info(f"Using PostgreSQL data directory: {data_dir}")
    
    # Find configuration files
    conf_path = find_postgresql_conf(data_dir)
    auto_conf_path = find_postgresql_auto_conf(data_dir)
    
    if not conf_path:
        logger.error("Could not find postgresql.conf")
        return 1
    
    logger.info(f"Found postgresql.conf at {conf_path}")
    if auto_conf_path:
        logger.info(f"Found postgresql.auto.conf at {auto_conf_path}")
    
    # Perform requested action
    if args.fix:
        if fix_wal_settings(conf_path, auto_conf_path):
            logger.info("WAL settings fixed successfully")
            logger.info("You can now restart PostgreSQL")
        else:
            logger.error("Failed to fix WAL settings")
            return 1
    elif args.optimize:
        if optimize_wal_settings(conf_path, auto_conf_path):
            logger.info("WAL settings optimized successfully")
            logger.info("You can now restart PostgreSQL")
        else:
            logger.error("Failed to optimize WAL settings")
            return 1
    elif args.restore:
        if restore_settings(conf_path, auto_conf_path):
            logger.info("Settings restored successfully")
            logger.info("You can now restart PostgreSQL")
        else:
            logger.error("Failed to restore settings")
            return 1
    else:
        logger.info("No action specified. Use --fix, --optimize, or --restore")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
