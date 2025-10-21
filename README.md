# NetBox WhatsUp Gold Sync Plugin

A NetBox plugin for synchronizing network devices between NetBox and WhatsUp Gold monitoring systems.

## Overview

This plugin provides automated bidirectional synchronization between NetBox and WhatsUp Gold, allowing you to:

- Import devices discovered in WhatsUp Gold into NetBox
- Keep device information synchronized between both systems
- Monitor sync status and troubleshoot sync issues
- Manage multiple WhatsUp Gold connections
- Automatically create NetBox sites, device types, and manufacturers from WUG data

## Features

### Core Functionality
- **Device Synchronization**: Automatic sync of devices from WhatsUp Gold to NetBox
- **Multiple Connections**: Support for multiple WhatsUp Gold servers
- **Scheduled Sync**: Configurable automatic sync intervals
- **Manual Sync**: On-demand synchronization via web UI or API
- **Selective Sync**: Enable/disable sync for individual devices

### Data Management
- **Auto-creation**: Automatically create NetBox sites, device types, and manufacturers
- **Data Mapping**: Intelligent mapping of WUG device properties to NetBox fields
- **Conflict Resolution**: Handle duplicate devices and naming conflicts
- **Status Tracking**: Monitor sync status and error handling

### Web Interface
- **Dashboard**: Overview of sync status and statistics
- **Connection Management**: Configure and test WUG connections
- **Device Management**: View and manage synced devices
- **Sync Logs**: Detailed logging and audit trails

### REST API
- **Full API Coverage**: Manage all plugin functionality via REST API
- **Bulk Operations**: Perform bulk sync operations
- **Status Monitoring**: Real-time sync status and statistics
- **Integration Ready**: Easy integration with external automation tools

## Requirements

- NetBox 4.0.0+
- Python 3.10+
- WhatsUp Gold with REST API access
- Network connectivity between NetBox and WhatsUp Gold servers

## Installation

### 1. Install the Plugin

```bash
# Install from PyPI (when published)
pip install netbox-wug-sync

# Or install from source
git clone https://github.com/yourusername/netbox-wug-sync.git
cd netbox-wug-sync
pip install -e .
```

### 2. Enable the Plugin

Add the plugin to your NetBox configuration in `configuration.py`:

```python
PLUGINS = [
  'netbox_wug_sync',
]

# Plugin configuration
PLUGINS_CONFIG = {
  'netbox_wug_sync': {
        # Required settings (configure via NetBox UI)
        'wug_host': None,           # Set via connection config
        'wug_username': None,       # Set via connection config  
        'wug_password': None,       # Set via connection config
        
        # Optional settings with defaults
        'wug_port': 9644,
        'wug_use_ssl': True,
        'wug_verify_ssl': False,
        'sync_interval_minutes': 60,
        'auto_create_sites': True,
        'auto_create_device_types': True,
        'default_device_role': 'server',
        'default_device_status': 'active',
        'sync_device_tags': True,
        'debug_mode': False,
    }
}
```

### 3. Run Database Migrations

```bash
cd /opt/netbox
python manage.py migrate netbox-wug-sync
```

### 4. Restart NetBox

```bash
# Restart NetBox services
sudo systemctl restart netbox netbox-rq
```

## Configuration

### WhatsUp Gold Connection Setup

1. Navigate to **Plugins > WhatsUp Gold Sync > Connections**
2. Click **Add Connection**
3. Configure the connection parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| Name | Friendly name for this connection | `Production WUG` |
| Host | WhatsUp Gold server hostname/IP | `wug.company.com` |
| Port | API port (default: 9644) | `9644` |
| Username | WUG API username | `netbox_sync` |
| Password | WUG API password | `secure_password` |
| Use SSL | Enable HTTPS (recommended) | `True` |
| Verify SSL | Verify SSL certificates | `False` (for self-signed) |

4. Test the connection using the **Test** button
5. Save the configuration

### Sync Configuration

Configure sync behavior in the connection settings:

- **Sync Interval**: How often to automatically sync (in minutes)
- **Auto-create Sites**: Create NetBox sites from WUG groups
- **Auto-create Device Types**: Create device types for unknown devices
- **Default Device Role**: Default role for synced devices

## Usage

### Web Interface

#### Dashboard
- Access: **Plugins > WhatsUp Gold Sync**
- View sync statistics and recent activity
- Quick access to connections and devices

#### Managing Connections
- **List**: View all configured WUG connections
- **Add**: Create new connection configurations
- **Test**: Verify connectivity and authentication
- **Sync**: Trigger manual synchronization

#### Managing Devices
- **List**: View all devices discovered from WUG
- **Filter**: Filter by connection, status, vendor, etc.
- **Enable/Disable**: Control sync for individual devices
- **Force Sync**: Trigger sync for specific devices

#### Sync Logs
- **View History**: See detailed sync operation logs
- **Troubleshoot**: Identify and resolve sync issues
- **Statistics**: Monitor sync performance and success rates

### REST API

The plugin provides a comprehensive REST API accessible at `/api/plugins/wug-sync/`.

#### Endpoints

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/plugins/wug-sync/connections/` | GET, POST | List/create connections |
| `/api/plugins/wug-sync/connections/{id}/` | GET, PUT, DELETE | Manage specific connection |
| `/api/plugins/wug-sync/connections/{id}/test/` | POST | Test connection |
| `/api/plugins/wug-sync/connections/{id}/sync/` | POST | Trigger sync |
| `/api/plugins/wug-sync/devices/` | GET | List synced devices |
| `/api/plugins/wug-sync/devices/{id}/sync-action/` | POST | Device sync actions |
| `/api/plugins/wug-sync/sync-logs/` | GET | View sync logs |
| `/api/plugins/wug-sync/status/` | GET | Plugin status overview |

#### Example API Usage

```bash
# Test connection
curl -X POST -H "Authorization: Token YOUR_TOKEN" \\
  http://netbox.example.com/api/plugins/wug-sync/connections/1/test/

# Trigger sync
curl -X POST -H "Authorization: Token YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"sync_type": "manual"}' \\
  http://netbox.example.com/api/plugins/wug-sync/connections/1/sync/

# Get plugin status
curl -H "Authorization: Token YOUR_TOKEN" \\
  http://netbox.example.com/api/plugins/wug-sync/status/
```

### Automation

#### Scheduled Sync
The plugin automatically schedules sync jobs based on the configured interval. Jobs run in the background using NetBox's job queue system.

#### Custom Sync Scripts
Create custom scripts for advanced sync scenarios:

```python
from netbox-wug-sync.models import WUGConnection
from netbox-wug-sync.jobs import WUGSyncJob

# Trigger sync for specific connection
connection = WUGConnection.objects.get(name='Production WUG')
job = WUGSyncJob()
result = job.run(connection_id=connection.id, sync_type='manual')
```

## Data Mapping

### WUG to NetBox Field Mapping

| WhatsUp Gold Field | NetBox Field | Notes |
|-------------------|--------------|-------|
| Device ID | WUGDevice.wug_id | Unique identifier |
| Device Name | Device.name | Cleaned for NetBox naming rules |
| Display Name | Device.comments | Additional display information |
| IP Address | IPAddress (primary) | Created as primary IP |
| MAC Address | Interface.mac_address | If interface created |
| Device Type | Custom field | Stored as custom field |
| Manufacturer | Manufacturer.name | Auto-created if needed |
| Model | DeviceType.model | Auto-created if needed |
| OS Version | Custom field | Operating system information |
| Group/Location | Site.name | Auto-created from WUG groups |
| Status | Device.status | Mapped to NetBox status choices |

### Status Mapping

| WUG Status | NetBox Status |
|------------|---------------|
| Up | Active |
| Down | Failed |
| Unknown | Offline |
| Maintenance | Planned |
| Disabled | Decommissioning |

## Troubleshooting

### Common Issues

#### Connection Problems
```
Error: Connection test failed: Connection refused
```
**Solution**: Check network connectivity, firewall rules, and WUG API service status.

#### Authentication Errors
```
Error: Authentication failed - check username and password
```
**Solution**: Verify WUG credentials and ensure API access is enabled for the user.

#### SSL Certificate Issues
```
Error: SSL certificate verification failed
```
**Solution**: Set "Verify SSL" to False for self-signed certificates, or install proper certificates.

#### Sync Failures
```
Error: Failed to create device: Duplicate name
```
**Solution**: Check NetBox device naming rules and handle conflicts in WUG data.

### Debug Mode

Enable debug mode for detailed logging:

```python
PLUGINS_CONFIG = {
  'netbox-wug-sync': {
        'debug_mode': True,
    }
}
```

### Log Files

Check NetBox logs for detailed error information:

```bash
# NetBox application log
tail -f /opt/netbox/logs/netbox.log

# Background job logs  
tail -f /opt/netbox/logs/rq_worker.log
```

## Development

### Setting up Development Environment

1. Clone the repository:
```bash
git clone https://github.com/yourusername/netbox-wug-sync.git
cd netbox-wug-sync
```

2. Create virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .[dev]
```

3. Run tests:
```bash
pytest
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run tests: `pytest`
5. Submit a pull request

### Code Style

The project uses:
- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting

Run code quality checks:
```bash
black netbox-wug-sync/
isort netbox-wug-sync/
flake8 netbox-wug-sync/
```

## Security Considerations

### Credentials Storage
- Passwords are stored encrypted in the NetBox database
- Use strong, unique passwords for WUG API accounts
- Regularly rotate API credentials

### Network Security
- Use HTTPS/SSL for WUG API connections when possible
- Restrict network access between NetBox and WUG servers
- Consider VPN or dedicated management networks

### Access Control
- Limit WUG API user permissions to read-only where possible
- Use NetBox's permission system to control plugin access
- Audit sync logs for security monitoring

## Performance Considerations

### Sync Optimization
- Adjust sync intervals based on network size and change frequency
- Use selective sync to exclude unnecessary devices
- Monitor sync duration and adjust batch sizes if needed

### Resource Usage
- Sync jobs run in background queues to avoid blocking the web interface
- Large networks may require increased worker processes
- Monitor database growth and implement log rotation

## FAQ

### Q: Can I sync devices from NetBox to WhatsUp Gold?
A: Currently, the plugin supports one-way sync from WUG to NetBox. Bidirectional sync may be added in future versions.

### Q: What happens if I delete a device from WhatsUp Gold?
A: The plugin will mark the device as inactive in the sync status but won't delete it from NetBox to preserve data integrity.

### Q: Can I customize the field mapping?
A: Field mapping is currently fixed but can be extended through custom fields. Future versions may support configurable mappings.

### Q: How do I handle large networks with thousands of devices?
A: Use selective sync, adjust sync intervals, and ensure adequate system resources. Consider syncing different device groups separately.

## Support

### Documentation
- Plugin documentation: [GitHub Wiki](https://github.com/yourusername/netbox-wug-sync/wiki)
- NetBox documentation: [netbox.readthedocs.io](https://netbox.readthedocs.io/)
- WhatsUp Gold API: Refer to your WUG installation documentation

### Community
- GitHub Issues: [Report bugs and feature requests](https://github.com/yourusername/netbox-wug-sync/issues)
- NetBox Community: [netdev.chat](https://netdev.chat/)

### Professional Support
For commercial support and custom development, contact the maintainers.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Changelog

### v0.1.0 (Initial Release)
- Basic device synchronization from WhatsUp Gold to NetBox
- Web interface for connection and device management
- REST API for programmatic access
- Automatic site and device type creation
- Comprehensive logging and error handling

---

**Note**: This plugin is not affiliated with or endorsed by NetBox Labs or Ipswitch WhatsUp Gold. It is an independent community project.