# Docker Examples for NetBox WUG Sync Plugin

This directory contains examples and documentation for deploying the netbox-wug-sync plugin with Docker.

## Quick Start

The easiest way to deploy NetBox with the WUG sync plugin is using Docker Compose with a custom image.

### Option 1: Use Custom Built Image (Recommended)

1. **Build the custom image:**
   ```bash
   cd examples/docker
   ./build.sh
   ```

2. **Use the docker-compose override:**
   ```bash
   cp docker-compose.override.yml /path/to/your/netbox/
   docker-compose up -d
   ```

### Option 2: Mount Plugin Directory

If you want to develop or frequently update the plugin:

```yaml
services:
  netbox:
    image: netboxcommunity/netbox:v4.4.5
    volumes:
      - /path/to/netbox-wug-sync:/opt/netbox/netbox-wug-sync:ro
    environment:
      - PYTHONPATH=/opt/netbox/netbox-wug-sync:$PYTHONPATH
```

## Files Included

- **`docker-compose.override.yml`** - Override file for docker-compose setup
- **`Dockerfile.plugin`** - Dockerfile for building custom NetBox image with plugin
- **`requirements-plugin.txt`** - Python requirements for the plugin
- **`build.sh`** - Script to build the custom image

## Configuration

### NetBox Plugin Configuration

Add to your NetBox `configuration.py`:

```python
PLUGINS = [
    'netbox_wug_sync',
]

PLUGINS_CONFIG = {
    'netbox_wug_sync': {
        # Plugin configuration options
        'default_connection_timeout': 30,
        'max_sync_devices': 1000,
    }
}
```

### Environment Variables

The plugin supports these environment variables:

- `WUG_SYNC_DEBUG` - Enable debug logging (default: False)
- `WUG_SYNC_TIMEOUT` - Default timeout for WUG API calls (default: 30)

## Version Compatibility

| NetBox Version | Plugin Version | Status |
|----------------|----------------|---------|
| 4.4.x          | 0.1.0+        | ✅ Supported |
| 4.3.x          | 0.1.0+        | ⚠️ May work |
| < 4.3          | Not supported | ❌ Not supported |

## Building for Different NetBox Versions

To build for a specific NetBox version:

```bash
NETBOX_VERSION=v4.4.5 ./build.sh
```

## Troubleshooting

### Plugin Not Loading

1. **Check plugin is installed:**
   ```bash
   docker exec netbox python -c "import netbox_wug_sync; print('OK')"
   ```

2. **Verify configuration:**
   ```bash
   docker exec netbox python manage.py shell -c "from django.conf import settings; print(settings.PLUGINS)"
   ```

3. **Check logs:**
   ```bash
   docker logs netbox
   ```

### Common Issues

**"Module not found"**: Ensure the plugin is properly installed in the NetBox Python environment.

**"get_absolute_url errors"**: Check that all model instances have valid primary keys and relationships.

**"Permission denied"**: Ensure proper file permissions if mounting directories.

## Production Deployment

For production deployments:

1. **Use specific version tags** instead of `latest`
2. **Pin NetBox version** in your Dockerfile
3. **Use secrets management** for sensitive configuration
4. **Set up monitoring** and health checks
5. **Regular backups** of NetBox data

Example production docker-compose override:

```yaml
services:
  netbox:
    image: mynetbox:v4.4.5-wug-0.1.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/login/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Development

For plugin development:

1. **Mount the source code:**
   ```yaml
   volumes:
     - ./netbox_wug_sync:/opt/netbox/venv/lib/python3.12/site-packages/netbox_wug_sync:ro
   ```

2. **Enable debug mode** in NetBox configuration
3. **Use development requirements** with additional tools

## Support

- **Issues**: [GitHub Issues](https://github.com/bassslap/netbox-wug-sync/issues)
- **Documentation**: [Project README](../../README.md)
- **NetBox Docs**: [NetBox Plugin Development](https://docs.netbox.dev/en/stable/plugins/)