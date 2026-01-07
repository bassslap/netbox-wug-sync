#!/usr/bin/env python
"""
List all WhatsUp Gold groups with their IDs and parent relationships.

This script displays the complete group hierarchy showing which groups are
top-level (can be assigned via API) and which are nested (require manual move).
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, '/opt/netbox/netbox')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from netbox_wug_sync.wug_client import WUGAPIClient
from netbox_wug_sync.models import WUGConnection


def main():
    """Display all WUG groups organized by parent."""
    
    # Get the first WUG connection
    conn = WUGConnection.objects.first()
    if not conn:
        print("ERROR: No WUG connection found in NetBox.")
        print("Please configure a WUG connection first.")
        sys.exit(1)
    
    # Build URL
    url = f'https://{conn.host}:{conn.port}' if conn.use_ssl else f'http://{conn.host}:{conn.port}'
    
    # Create client and get groups
    print(f"Connecting to WUG at {url}...")
    client = WUGAPIClient(url, conn.username, conn.password)
    groups = client.get_device_groups()
    
    # Sort by parent ID, then by name
    groups_sorted = sorted(groups, key=lambda g: (int(g.get('parentGroupId', 0) or 0), g.get('name', '')))
    
    # Display header
    print('\n' + '='*80)
    print(f'Total Groups: {len(groups_sorted)}')
    print('='*80 + '\n')
    
    # Display groups organized by parent
    current_parent = None
    for group in groups_sorted:
        gid = group.get('id')
        name = group.get('name')
        parent = group.get('parentGroupId', '')
        parent_int = int(parent) if parent and parent != '' else 0
        
        # Print section header when parent changes
        if parent_int != current_parent:
            current_parent = parent_int
            if parent_int == 0:
                print('\n--- TOP-LEVEL GROUPS (Parent: 0) - API Assignment Works ✅ ---')
            else:
                # Find parent name
                parent_name = 'Unknown'
                for pg in groups_sorted:
                    if int(pg.get('id')) == parent_int:
                        parent_name = pg.get('name')
                        break
                print(f'\n--- NESTED UNDER: {parent_name} (Parent ID: {parent_int}) - Manual Move Required ❌ ---')
        
        # Print group info
        print(f'  ID: {gid:4} | Parent: {str(parent):4} | Name: {name}')
    
    print('\n' + '='*80)
    print('\nLegend:')
    print('  ✅ TOP-LEVEL groups can be assigned via API')
    print('  ❌ NESTED groups require manual move in WUG UI after device creation')
    print('='*80 + '\n')


if __name__ == '__main__':
    main()
