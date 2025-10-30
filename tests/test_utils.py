"""
Test configuration and utilities for NetBox WUG Sync Plugin tests
"""

import os
import django
from django.conf import settings
from django.test.utils import get_runner


def setup_test_environment():
    """Set up Django test environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
    django.setup()


class TestConfig:
    """Test configuration constants"""
    
    TEST_WUG_HOST = "http://test-wug.example.com"
    TEST_WUG_USERNAME = "testuser"
    TEST_WUG_PASSWORD = "testpass"
    
    SAMPLE_WUG_DEVICE = {
        "id": 123,
        "name": "Test Router",
        "ipAddress": "192.168.1.1",
        "deviceType": "Router",
        "manufacturer": "Cisco",
        "model": "ISR4321",
        "description": "Test device description",
        "location": "Test Location"
    }
    
    SAMPLE_WUG_DEVICES = [
        {
            "id": 1,
            "name": "Router1",
            "ipAddress": "192.168.1.1",
            "deviceType": "Router",
            "manufacturer": "Cisco",
            "model": "ISR4321"
        },
        {
            "id": 2,
            "name": "Switch1",
            "ipAddress": "192.168.1.2",
            "deviceType": "Switch",
            "manufacturer": "Cisco",
            "model": "C9300"
        },
        {
            "id": 3,
            "name": "Firewall1",
            "ipAddress": "192.168.1.3",
            "deviceType": "Firewall",
            "manufacturer": "Fortinet",
            "model": "FortiGate-60F"
        }
    ]


def create_test_wug_connection():
    """Create a test WUG connection for testing"""
    from netbox_wug_sync.models import WUGConnection
    
    return WUGConnection.objects.create(
        name="Test WUG Server",
        host=TestConfig.TEST_WUG_HOST,
        username=TestConfig.TEST_WUG_USERNAME,
        password=TestConfig.TEST_WUG_PASSWORD,
        enabled=True
    )


def create_test_wug_device(connection=None, **kwargs):
    """Create a test WUG device for testing"""
    from netbox_wug_sync.models import WUGDevice
    
    if connection is None:
        connection = create_test_wug_connection()
    
    defaults = {
        'wug_connection': connection,
        'wug_device_id': 123,
        'name': 'Test Device',
        'ip_address': '192.168.1.1',
        'device_type': 'Router',
        'manufacturer': 'Cisco',
        'model': 'ISR4321'
    }
    defaults.update(kwargs)
    
    return WUGDevice.objects.create(**defaults)


def create_test_sync_log(connection=None, **kwargs):
    """Create a test sync log for testing"""
    from netbox_wug_sync.models import WUGSyncLog
    
    if connection is None:
        connection = create_test_wug_connection()
    
    defaults = {
        'wug_connection': connection,
        'sync_type': 'wug_to_netbox',
        'status': 'success',
        'message': 'Test sync completed',
        'devices_processed': 10,
        'devices_created': 5,
        'devices_updated': 3,
        'devices_failed': 2
    }
    defaults.update(kwargs)
    
    return WUGSyncLog.objects.create(**defaults)