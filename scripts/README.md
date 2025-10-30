# Scripts

This directory contains helper scripts for the NetBox WUG Sync plugin.

## Installation & Verification

### `verify_installation.py`
Verifies that the plugin is properly installed and configured in a NetBox environment.

**Usage:**
```bash
# From within NetBox Docker container or virtual environment
python scripts/verify_installation.py
```

**Features:**
- Tests plugin import and Django app registration
- Validates database tables and migrations
- Checks static files availability
- Provides troubleshooting guidance
- Safe to run in production environments

## Development Scripts

The `development/` subdirectory contains scripts used during plugin development and testing.

### `development/dev_migration_helper.py`
Helper script for creating NetBox plugin migrations during development.

**Usage:**
```bash
python scripts/development/dev_migration_helper.py
```

**Purpose:**
- Assists with Django migration generation for plugin models
- Sets up proper Django environment for migration commands
- Used during development when model changes are made

### `development/simple_wug_test.py`
Standalone test script for verifying WhatsUp Gold API connectivity and functionality.

**Usage:**
```bash
python scripts/development/simple_wug_test.py
```

**Features:**
- Tests WUG API authentication and basic connectivity
- Validates device retrieval and data parsing
- Includes comprehensive logging and error handling
- Useful for debugging WUG integration issues

### `development/test_updated_wug_client.py`
Test script specifically for the updated WUG client implementation.

**Usage:**
```bash
python scripts/development/test_updated_wug_client.py
```

**Purpose:**
- Tests specific WUG client functionality
- Validates API client changes and improvements
- Provides detailed output for debugging client issues

## Running Scripts

### In Docker Environment
```bash
# Copy script into container and run
docker cp scripts/verify_installation.py netbox:/opt/netbox/
docker exec netbox python verify_installation.py

# Or run directly with exec
docker exec netbox python -c "$(cat scripts/verify_installation.py)"
```

### In Virtual Environment
```bash
# Activate NetBox virtual environment first
source /opt/netbox/venv/bin/activate
python scripts/verify_installation.py
```

### Development Environment
```bash
# For development scripts, ensure proper Python path
export PYTHONPATH="/path/to/netbox:$PYTHONPATH"
python scripts/development/simple_wug_test.py
```

## Notes

- All scripts include proper error handling and informative output
- Development scripts may require additional dependencies or environment setup
- Verification scripts are designed to be safe for production use
- Scripts use proper logging and provide troubleshooting guidance