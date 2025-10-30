# NetBox WUG Sync Plugin - Deployment Guide

This guide provides complete step-by-step instructions for deploying the NetBox WhatsUp Gold Sync plugin in production environments.

## 🚀 Quick Start

### Prerequisites

- NetBox v4.4+ running in Docker
- Docker and Docker Compose installed
- Git access to this repository
- WhatsUp Gold server with API access

### Production Deployment Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/bassslap/netbox-wug-sync.git
   cd netbox-wug-sync
   ```

2. **Choose Your Deployment Method**
   - **Docker (Recommended)**: See [Docker Deployment](#docker-deployment)
   - **pip install**: See [Manual Installation](#manual-installation)

## 🐳 Docker Deployment

### Method 1: Using Provided Examples (Recommended)

1. **Copy Docker configuration files to your NetBox directory:**
   ```bash
   # Copy example files to your NetBox installation directory
   cp examples/docker/* /path/to/your/netbox-docker/
   ```

2. **Build the custom NetBox image:**
   ```bash
   cd /path/to/your/netbox-docker/
   chmod +x build.sh
   ./build.sh
   ```

3. **Update your docker-compose.yml or create override:**
   ```yaml
   # Add to docker-compose.override.yml
   services:
     netbox:
       image: mynetbox:latest
     netbox-worker:
       image: mynetbox:latest
   ```

4. **Start NetBox:**
   ```bash
   docker compose up -d
   ```

5. **Collect static files (important for logo display):**
   ```bash
   docker exec -u root netbox-netbox-1 python /opt/netbox/netbox/manage.py collectstatic --noinput
   ```

### Method 2: Manual Docker Setup

1. **Create custom Dockerfile:**
   ```dockerfile
   FROM netboxcommunity/netbox:v4.4-3.4.1
   
   RUN apt-get update && apt-get install -y git python3-pip
   
   # Download get-pip.py and install pip in the NetBox venv
   RUN curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
       /opt/netbox/venv/bin/python3 /tmp/get-pip.py && \
       rm /tmp/get-pip.py
   
   # Clone the plugin from main branch
   RUN git clone --branch main https://github.com/bassslap/netbox-wug-sync.git /opt/netbox/netbox-wug-sync
   
   # Install plugin
   RUN /opt/netbox/venv/bin/python3 -m pip install --upgrade pip setuptools wheel
   RUN /opt/netbox/venv/bin/python3 -m pip install -e /opt/netbox/netbox-wug-sync
   
   # Verify plugin installation
   RUN /opt/netbox/venv/bin/python3 -c "import netbox_wug_sync"
   ```

2. **Build and deploy:**
   ```bash
   docker build -t mynetbox:latest .
   docker compose up -d
   ```

## 📦 Manual Installation

### For Standard NetBox Installations

1. **Install the plugin:**
   ```bash
   # In your NetBox virtual environment
   pip install git+https://github.com/bassslap/netbox-wug-sync.git
   ```

2. **Configure NetBox settings:**
   ```python
   # Add to configuration.py
   PLUGINS = [
       'netbox_wug_sync',
   ]
   
   PLUGINS_CONFIG = {
       'netbox_wug_sync': {
           # Plugin configuration options here
       }
   }
   ```

3. **Run migrations and collect static files:**
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

4. **Restart NetBox services:**
   ```bash
   systemctl restart netbox netbox-rq
   ```

## ⚙️ Configuration

### Required NetBox Configuration

Add to your NetBox `configuration.py`:

```python
# Enable the plugin
PLUGINS = [
    'netbox_wug_sync',
]

# Optional plugin configuration
PLUGINS_CONFIG = {
    'netbox_wug_sync': {
        'default_sync_interval': 300,  # 5 minutes
        'max_concurrent_syncs': 3,
        'enable_auto_sync': True,
    }
}
```

### WhatsUp Gold API Setup

1. **Enable REST API in WhatsUp Gold:**
   - Go to Settings → Web and Mobile Services
   - Enable REST API
   - Note the API endpoint URL

2. **Create API User:**
   - Create a dedicated user account for NetBox integration
   - Assign appropriate permissions for device and network discovery

3. **Configure WUG Connection in NetBox:**
   - Navigate to Plugins → WUG Sync → WUG Connections
   - Add new connection with your WhatsUp Gold details

## 🔍 Verification Steps

### 1. Check Plugin Installation
```bash
# In NetBox container or environment
python manage.py shell -c "import netbox_wug_sync; print('Plugin loaded successfully')"
```

### 2. Verify Web Interface
- Navigate to `/plugins/wug-sync/` in your NetBox instance
- You should see the WhatsUp Gold Sync Dashboard
- Verify the WhatsUp Gold logo displays correctly

### 3. Run Installation Verification Script
```bash
# Comprehensive plugin verification
python scripts/verify_installation.py
```
This script provides detailed verification including:
- Plugin import and Django app registration
- Database table validation
- Static files availability
- Configuration checks

### 4. Test API Connectivity
- Go to WUG Connections and click "Test Connection"
- Should return successful connection status

### 5. Verify Static Files
```bash
# Check that SVG logo is accessible
curl -I http://your-netbox-url/static/netbox_wug_sync/img/wug-logo.svg
# Should return HTTP 200 OK
```

## 🔧 Troubleshooting

### Common Issues

**1. Plugin not loading:**
- Ensure plugin is in PLUGINS list in configuration.py
- Check NetBox logs for import errors
- Verify plugin is installed in correct virtual environment

**2. Logo not displaying:**
- Run `collectstatic --noinput` to copy static files
- Check static file serving configuration
- Verify file permissions

**3. Database errors:**
- Run `python manage.py migrate` to apply plugin migrations
- Check database connectivity and permissions

**4. WUG API connection fails:**
- Verify WhatsUp Gold REST API is enabled
- Check network connectivity between NetBox and WUG server
- Validate API credentials and permissions

### Debug Commands

```bash
# Check plugin status
python manage.py shell -c "
from django.apps import apps
print('Installed apps:', [app.name for app in apps.get_app_configs()])
"

# Verify database tables
python manage.py dbshell -c "\dt netbox_wug_sync*"

# Check static files
python manage.py findstatic netbox_wug_sync/img/wug-logo.svg

# Test WUG client connection
python manage.py shell -c "
from netbox_wug_sync.wug_client import WUGClient
client = WUGClient('http://your-wug-server', 'username', 'password')
print(client.test_connection())
"
```

## 📋 Production Checklist

Before deploying to production, verify:

- [ ] NetBox v4.4+ is running
- [ ] Plugin is installed and configured
- [ ] Database migrations completed successfully
- [ ] Static files collected and accessible
- [ ] WhatsUp Gold API connectivity tested
- [ ] Plugin dashboard accessible at `/plugins/wug-sync/`
- [ ] Logo displays correctly (not alt text)
- [ ] WUG connection test passes
- [ ] Sync functionality works end-to-end
- [ ] Error handling and logging configured
- [ ] Backup and recovery procedures in place

## 🔄 Updates and Maintenance

### Updating the Plugin

```bash
# For Docker deployments
cd /path/to/your/netbox-docker/
./build.sh  # Rebuilds with latest plugin code
docker compose up -d

# For manual installations
pip install --upgrade git+https://github.com/bassslap/netbox-wug-sync.git
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart netbox netbox-rq
```

### Monitoring

- Monitor NetBox logs for plugin-related errors
- Check sync job status regularly in the dashboard
- Monitor API call performance and rate limits
- Set up alerts for failed sync operations

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review NetBox and plugin logs
3. Verify configuration against this guide
4. Check the repository issues for known problems

For technical support, please create an issue in the GitHub repository with:
- NetBox version
- Plugin version/commit hash
- Error logs and stack traces
- Configuration details (with sensitive data redacted)