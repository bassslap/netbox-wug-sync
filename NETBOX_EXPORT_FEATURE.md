# NetBox to WhatsUp Gold Export Feature

## Overview

This document describes the newly implemented **bidirectional synchronization** feature that allows:

1. **Pull IPs from NetBox** - Extract IP addresses from NetBox devices
2. **Format them for WUG** - Prepare NetBox device data for WhatsUp Gold consumption  
3. **Trigger WUG scan or update device metadata** - Add devices to WUG monitoring or update existing devices

## New Components Added

### 1. Enhanced Models (`models.py`)

#### WUGConnection Model - New Fields
```python
# NetBox to WUG export settings
enable_netbox_export = models.BooleanField(default=False)
export_interval_minutes = models.PositiveIntegerField(default=180)  # 3 hours
last_export = models.DateTimeField(null=True, blank=True)
auto_scan_exported_ips = models.BooleanField(default=True)
```

#### New Model: NetBoxIPExport
Tracks NetBox IP addresses exported to WhatsUp Gold:
- IP address and source NetBox device
- Export status (pending, exported, scan_triggered, scan_completed, error)
- WUG scan ID and device discovery results
- Timestamps for export/scan lifecycle
- Error tracking and metadata

### 2. Enhanced WUG API Client (`wug_client.py`)

#### New Methods for NetBox Export:
- `scan_ip_address(ip, options)` - Trigger WUG scan for specific IP
- `scan_ip_range(range, options)` - Scan IP ranges efficiently
- `add_device_by_ip(ip, config)` - Add device to WUG by IP
- `update_device_metadata(device_id, metadata)` - Update WUG device with NetBox data
- `get_scan_results(scan_id)` - Get results of completed scans
- `bulk_add_ips(ip_list, config)` - Batch operations for multiple IPs

### 3. Utility Functions (`sync_utils.py`)

#### NetBox Device Selection:
- `get_netbox_devices_for_export()` - Get NetBox devices with filtering options
- `extract_device_ips_for_wug()` - Extract IPs and metadata from NetBox devices
- `format_ips_for_wug_scan()` - Format data for different WUG scan types

#### Data Transformation:
- `create_wug_device_config()` - Convert NetBox device to WUG device config
- `validate_ip_for_export()` - Validate IPs before export with warnings

### 4. Background Jobs (`jobs.py`)

#### NetBoxToWUGExportJob
Main export job that:
- Finds NetBox devices with IP addresses
- Validates IPs for export
- Attempts to add devices to WUG
- Falls back to triggering scans if device add fails
- Tracks export status and results

#### WUGScanStatusUpdateJob  
Monitors ongoing WUG scans:
- Checks status of triggered scans
- Updates export records when scans complete
- Identifies discovered devices
- Handles scan failures

### 5. Web Interface Enhancements (`views.py`)

#### New Views:
- `trigger_netbox_export_view()` - Manually trigger export for connection
- `netbox_export_status_view()` - Get export statistics and recent activity

## Usage Scenarios

### Scenario 1: New Device Discovered in NetBox
```python
# When a new device is added to NetBox with an IP address:
# 1. Device gets flagged for export during next sync cycle
# 2. Export job extracts IP and device metadata
# 3. Attempts to add device directly to WUG with NetBox metadata
# 4. If successful, device appears in WUG with NetBox context
```

### Scenario 2: IP Range Export for Discovery
```python
# Bulk export of NetBox devices for WUG discovery:
# 1. Select devices by site, role, or other criteria
# 2. Extract IP addresses and group by network ranges
# 3. Trigger WUG network scans for efficient discovery
# 4. Monitor scan results and link discovered devices
```

### Scenario 3: Metadata Synchronization
```python
# Keep WUG devices updated with NetBox information:
# 1. Export job identifies NetBox devices with WUG counterparts
# 2. Updates WUG device metadata with current NetBox data
# 3. Includes site, role, platform, custom fields, etc.
# 4. Maintains bi-directional data consistency
```

## Configuration Example

### Enable NetBox Export in Connection
```python
connection = WUGConnection.objects.get(name='Production WUG')
connection.enable_netbox_export = True
connection.export_interval_minutes = 180  # 3 hours
connection.auto_scan_exported_ips = True
connection.save()
```

### Manual Export Trigger
```python
from netbox_wug_sync.jobs import NetBoxToWUGExportJob

job = NetBoxToWUGExportJob()
result = job.run(
    connection_id=connection.id,
    export_type='manual',
    device_filters={
        'sites': [site1.id, site2.id],
        'device_roles': [server_role.id],
        'exclude_recent_exports': True
    }
)
```

## API Integration

### REST API Endpoints
- `POST /api/plugins/wug-sync/connections/{id}/export/` - Trigger export
- `GET /api/plugins/wug-sync/connections/{id}/export-status/` - Get export stats
- `GET /api/plugins/wug-sync/ip-exports/` - List IP export records
- `POST /api/plugins/wug-sync/ip-exports/bulk-export/` - Bulk IP export

### Example API Usage
```bash
# Trigger NetBox export for connection
curl -X POST -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_filters": {"sites": [1, 2]}}' \
  http://netbox.example.com/api/plugins/wug-sync/connections/1/export/

# Check export status  
curl -H "Authorization: Token YOUR_TOKEN" \
  http://netbox.example.com/api/plugins/wug-sync/connections/1/export-status/
```

## Data Flow

```
NetBox Devices (with IPs) 
    ↓
[Filter & Validate IPs]
    ↓
[Extract Device Metadata]
    ↓
[Format for WUG API]
    ↓
┌─────────────────┐    ┌─────────────────┐
│ Add Device to   │ OR │ Trigger WUG     │
│ WUG Directly    │    │ IP Scan         │
└─────────────────┘    └─────────────────┘
    ↓                        ↓
[Update WUG Device]    [Monitor Scan Status]
    ↓                        ↓
[Set NetBox Metadata]  [Link Discovered Device]
    ↓                        ↓
    └────── Success ─────────┘
```

## Benefits

1. **Automated Discovery**: NetBox becomes source of truth for device discovery in WUG
2. **Rich Metadata**: WUG devices get enhanced with NetBox context (site, role, etc.)
3. **Reduced Manual Work**: Eliminates manual device entry in WUG
4. **Consistency**: Ensures both systems track the same infrastructure
5. **Audit Trail**: Full tracking of export operations and status

## Next Steps

To fully implement this feature:

1. **Database Migration**: Run migration to add new model fields
2. **Configuration**: Enable NetBox export in WUG connections
3. **Job Scheduling**: Set up periodic export jobs
4. **Testing**: Validate with your specific WUG API endpoints
5. **Monitoring**: Set up alerts for export failures

The foundation is now in place for comprehensive bidirectional synchronization between NetBox and WhatsUp Gold!