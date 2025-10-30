"""
NetBox WUG Sync Plugin Test Suite

This module provides unit tests for the NetBox WhatsUp Gold sync plugin.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import Mock, patch

from netbox_wug_sync.models import WUGConnection, WUGDevice, WUGSyncLog
from netbox_wug_sync.wug_client import WUGClient

User = get_user_model()


class WUGConnectionModelTest(TestCase):
    """Test cases for WUGConnection model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_create_wug_connection(self):
        """Test creating a WUG connection"""
        connection = WUGConnection.objects.create(
            name="Test WUG Server",
            host="http://wug.example.com",
            username="testuser",
            password="testpass",
            enabled=True
        )
        
        self.assertEqual(connection.name, "Test WUG Server")
        self.assertEqual(connection.host, "http://wug.example.com")
        self.assertTrue(connection.enabled)
        self.assertIsNotNone(connection.pk)
    
    def test_wug_connection_str(self):
        """Test string representation of WUG connection"""
        connection = WUGConnection.objects.create(
            name="Test Server",
            host="http://test.com",
            username="user",
            password="pass"
        )
        
        self.assertEqual(str(connection), "Test Server")
    
    def test_get_absolute_url_with_valid_pk(self):
        """Test get_absolute_url with valid primary key"""
        connection = WUGConnection.objects.create(
            name="Test Server",
            host="http://test.com",
            username="user",
            password="pass"
        )
        
        url = connection.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugconnection', args=[connection.pk])
        self.assertEqual(url, expected_url)
    
    def test_get_absolute_url_defensive(self):
        """Test get_absolute_url defensive programming for None pk"""
        connection = WUGConnection(
            name="Test Server",
            host="http://test.com",
            username="user",
            password="pass"
        )
        # Don't save, so pk is None
        
        url = connection.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugconnection_list')
        self.assertEqual(url, expected_url)


class WUGDeviceModelTest(TestCase):
    """Test cases for WUGDevice model"""
    
    def setUp(self):
        """Set up test data"""
        self.connection = WUGConnection.objects.create(
            name="Test WUG Server",
            host="http://wug.example.com",
            username="testuser",
            password="testpass"
        )
    
    def test_create_wug_device(self):
        """Test creating a WUG device"""
        device = WUGDevice.objects.create(
            wug_connection=self.connection,
            wug_device_id=123,
            name="Test Device",
            ip_address="192.168.1.1",
            device_type="Router",
            manufacturer="Cisco",
            model="ISR4321"
        )
        
        self.assertEqual(device.name, "Test Device")
        self.assertEqual(device.ip_address, "192.168.1.1")
        self.assertEqual(device.wug_device_id, 123)
        self.assertEqual(device.wug_connection, self.connection)
    
    def test_wug_device_str(self):
        """Test string representation of WUG device"""
        device = WUGDevice.objects.create(
            wug_connection=self.connection,
            wug_device_id=123,
            name="Test Device",
            ip_address="192.168.1.1"
        )
        
        self.assertEqual(str(device), "Test Device (192.168.1.1)")
    
    def test_get_absolute_url_with_valid_pk(self):
        """Test get_absolute_url with valid primary key"""
        device = WUGDevice.objects.create(
            wug_connection=self.connection,
            wug_device_id=123,
            name="Test Device",
            ip_address="192.168.1.1"
        )
        
        url = device.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugdevice', args=[device.pk])
        self.assertEqual(url, expected_url)
    
    def test_get_absolute_url_defensive(self):
        """Test get_absolute_url defensive programming for None pk"""
        device = WUGDevice(
            wug_connection=self.connection,
            wug_device_id=123,
            name="Test Device",
            ip_address="192.168.1.1"
        )
        # Don't save, so pk is None
        
        url = device.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugdevice_list')
        self.assertEqual(url, expected_url)


class WUGSyncLogModelTest(TestCase):
    """Test cases for WUGSyncLog model"""
    
    def setUp(self):
        """Set up test data"""
        self.connection = WUGConnection.objects.create(
            name="Test WUG Server",
            host="http://wug.example.com",
            username="testuser",
            password="testpass"
        )
    
    def test_create_sync_log(self):
        """Test creating a sync log entry"""
        log = WUGSyncLog.objects.create(
            wug_connection=self.connection,
            sync_type='wug_to_netbox',
            status='success',
            message="Sync completed successfully",
            devices_processed=10,
            devices_created=5,
            devices_updated=3,
            devices_failed=2
        )
        
        self.assertEqual(log.sync_type, 'wug_to_netbox')
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.devices_processed, 10)
        self.assertEqual(log.wug_connection, self.connection)
    
    def test_sync_log_str(self):
        """Test string representation of sync log"""
        log = WUGSyncLog.objects.create(
            wug_connection=self.connection,
            sync_type='wug_to_netbox',
            status='success',
            message="Test sync"
        )
        
        expected_str = f"Test WUG Server - wug_to_netbox - success"
        self.assertEqual(str(log), expected_str)
    
    def test_get_absolute_url_with_valid_pk(self):
        """Test get_absolute_url with valid primary key"""
        log = WUGSyncLog.objects.create(
            wug_connection=self.connection,
            sync_type='wug_to_netbox',
            status='success',
            message="Test sync"
        )
        
        url = log.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugsynclog', args=[log.pk])
        self.assertEqual(url, expected_url)
    
    def test_get_absolute_url_defensive(self):
        """Test get_absolute_url defensive programming for None pk"""
        log = WUGSyncLog(
            wug_connection=self.connection,
            sync_type='wug_to_netbox',
            status='success',
            message="Test sync"
        )
        # Don't save, so pk is None
        
        url = log.get_absolute_url()
        expected_url = reverse('plugins:netbox_wug_sync:wugsynclog_list')
        self.assertEqual(url, expected_url)


class WUGClientTest(TestCase):
    """Test cases for WUG client"""
    
    def setUp(self):
        """Set up test data"""
        self.client = WUGClient(
            base_url="http://wug.example.com",
            username="testuser",
            password="testpass"
        )
    
    def test_wug_client_initialization(self):
        """Test WUG client initialization"""
        self.assertEqual(self.client.base_url, "http://wug.example.com")
        self.assertEqual(self.client.username, "testuser")
        self.assertEqual(self.client.password, "testpass")
    
    @patch('netbox_wug_sync.wug_client.requests.get')
    def test_test_connection_success(self, mock_get):
        """Test successful connection test"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response
        
        result = self.client.test_connection()
        self.assertTrue(result)
    
    @patch('netbox_wug_sync.wug_client.requests.get')
    def test_test_connection_failure(self, mock_get):
        """Test failed connection test"""
        mock_get.side_effect = Exception("Connection failed")
        
        result = self.client.test_connection()
        self.assertFalse(result)
    
    @patch('netbox_wug_sync.wug_client.requests.get')
    def test_get_devices_success(self, mock_get):
        """Test successful device retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "Device1",
                "ipAddress": "192.168.1.1",
                "deviceType": "Router"
            }
        ]
        mock_get.return_value = mock_response
        
        devices = self.client.get_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["name"], "Device1")
    
    @patch('netbox_wug_sync.wug_client.requests.get')
    def test_get_devices_failure(self, mock_get):
        """Test failed device retrieval"""
        mock_get.side_effect = Exception("API error")
        
        devices = self.client.get_devices()
        self.assertEqual(devices, [])


class DashboardViewTest(TestCase):
    """Test cases for dashboard view"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_login(self.user)
        
        self.connection = WUGConnection.objects.create(
            name="Test WUG Server",
            host="http://wug.example.com",
            username="testuser",
            password="testpass"
        )
    
    def test_dashboard_view_loads(self):
        """Test that dashboard view loads successfully"""
        url = reverse('plugins:netbox_wug_sync:dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WhatsUp Gold")
        self.assertContains(response, "Sync Dashboard")
    
    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication"""
        self.client.logout()
        url = reverse('plugins:netbox_wug_sync:dashboard')
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)


class APITestCase(APITestCase):
    """Test cases for REST API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        self.connection = WUGConnection.objects.create(
            name="Test WUG Server",
            host="http://wug.example.com",
            username="testuser",
            password="testpass"
        )
    
    def test_wug_connections_api_list(self):
        """Test WUG connections API list endpoint"""
        url = reverse('plugins-api:netbox_wug_sync-api:wugconnection-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], "Test WUG Server")
    
    def test_wug_connections_api_detail(self):
        """Test WUG connections API detail endpoint"""
        url = reverse('plugins-api:netbox_wug_sync-api:wugconnection-detail', args=[self.connection.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Test WUG Server")
        self.assertEqual(response.data['host'], "http://wug.example.com")
    
    def test_wug_devices_api_list(self):
        """Test WUG devices API list endpoint"""
        # Create a test device
        WUGDevice.objects.create(
            wug_connection=self.connection,
            wug_device_id=123,
            name="Test Device",
            ip_address="192.168.1.1"
        )
        
        url = reverse('plugins-api:netbox_wug_sync-api:wugdevice-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], "Test Device")
    
    def test_sync_logs_api_list(self):
        """Test sync logs API list endpoint"""
        # Create a test log
        WUGSyncLog.objects.create(
            wug_connection=self.connection,
            sync_type='wug_to_netbox',
            status='success',
            message="Test sync"
        )
        
        url = reverse('plugins-api:netbox_wug_sync-api:wugsynclog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['sync_type'], 'wug_to_netbox')


class PluginConfigTest(TestCase):
    """Test plugin configuration and setup"""
    
    def test_plugin_config_exists(self):
        """Test that plugin config is properly set up"""
        from django.apps import apps
        
        app_config = apps.get_app_config('netbox_wug_sync')
        self.assertEqual(app_config.name, 'netbox_wug_sync')
        self.assertIsNotNone(app_config.verbose_name)
    
    def test_plugin_installed(self):
        """Test that plugin is in installed apps"""
        from django.conf import settings
        
        self.assertIn('netbox_wug_sync', settings.INSTALLED_APPS)
    
    def test_urls_configured(self):
        """Test that plugin URLs are properly configured"""
        from django.urls import reverse
        
        # Test that main URLs are available
        try:
            reverse('plugins:netbox_wug_sync:dashboard')
            reverse('plugins:netbox_wug_sync:wugconnection_list')
            reverse('plugins:netbox_wug_sync:wugdevice_list')
            reverse('plugins:netbox_wug_sync:wugsynclog_list')
        except Exception as e:
            self.fail(f"URL configuration failed: {e}")