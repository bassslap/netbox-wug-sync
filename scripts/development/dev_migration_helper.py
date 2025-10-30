#!/usr/bin/env python3
"""
Development helper script for creating NetBox plugin migrations.

Usage:
    python3 scripts/development/dev_migration_helper.py

This script helps generate migrations when you make changes to your plugin models.
"""

import os
import sys
import django
from pathlib import Path

def setup_django():
    """Set up Django environment for the plugin"""
    # Add NetBox to Python path
    netbox_path = '/home/bryan/REPOS/netbox/netbox'
    if netbox_path not in sys.path:
        sys.path.insert(0, netbox_path)
    
    # Configure Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
    django.setup()

def create_migration(migration_name="auto_migration"):
    """
    Create a new migration file for the plugin.
    
    Since NetBox disables makemigrations for plugins, this function
    helps create migration files manually based on model changes.
    """
    setup_django()
    
    from django.db import models
    from django.db.migrations.writer import MigrationWriter
    from django.db.migrations.migration import Migration
    from django.db.migrations.state import ProjectState
    
    # Import your models
    from netbox_wug_sync.models import WUGConnection, WUGDevice, WUGSyncLog, NetBoxIPExport
    
    print("🔧 NetBox Plugin Migration Helper")
    print("=" * 40)
    print("Available models:", [WUGConnection.__name__, WUGDevice.__name__, 
                              WUGSyncLog.__name__, NetBoxIPExport.__name__])
    
    # Get the latest migration number
    migrations_dir = Path(__file__).parent / "netbox_wug_sync" / "migrations"
    existing_migrations = list(migrations_dir.glob("????_*.py"))
    
    if existing_migrations:
        latest_num = max(int(f.stem[:4]) for f in existing_migrations)
        next_num = f"{latest_num + 1:04d}"
    else:
        next_num = "0001"
    
    migration_filename = f"{next_num}_{migration_name}.py"
    
    print(f"Next migration: {migration_filename}")
    print("\n📝 To create a new migration:")
    print("1. Make your model changes")
    print("2. Run this script")
    print("3. The script will help generate the migration operations")
    print("\n💡 For complex changes, you may need to manually edit the migration file")
    
    return migration_filename

def get_model_diff():
    """
    Compare current models with database schema to detect changes.
    This is a simplified version - for production use a more robust solution.
    """
    setup_django()
    
    # This would require more complex introspection
    # For now, just show the current model state
    from netbox_wug_sync.models import WUGConnection
    
    print("\n📊 Current WUGConnection fields:")
    for field in WUGConnection._meta.get_fields():
        if hasattr(field, 'name') and not field.many_to_many:
            print(f"  - {field.name}: {type(field).__name__}")

if __name__ == "__main__":
    print("🚀 NetBox WUG Sync Plugin - Migration Helper")
    print()
    
    choice = input("What would you like to do?\n1. Create new migration\n2. Show model info\n3. Exit\nChoice (1-3): ")
    
    if choice == "1":
        name = input("Migration name (or press Enter for 'auto_migration'): ").strip()
        if not name:
            name = "auto_migration"
        create_migration(name)
    elif choice == "2":
        get_model_diff()
    else:
        print("Goodbye!")