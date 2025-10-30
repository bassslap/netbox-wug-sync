"""
Unit tests for WUG client and sync utilities
"""

from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
import requests

from netbox_wug_sync.wug_client import WUGClient
from netbox_wug_sync.sync_utils import WUGSyncManager
from netbox_wug_sync.models import WUGConnection, WUGDevice, WUGSyncLog
from tests.test_utils import TestConfig, create_test_wug_connection


class WUGClientUnitTest(TestCase):
    """Detailed unit tests for WUG client"""
    
    def setUp(self):
        """Set up test client"""
        self.client = WUGClient(
            base_url=TestConfig.TEST_WUG_HOST,
            username=TestConfig.TEST_WUG_USERNAME,
            password=TestConfig.TEST_WUG_PASSWORD
        )
    
    def test_client_initialization(self):
        """Test client is properly initialized"""
        self.assertEqual(self.client.base_url, TestConfig.TEST_WUG_HOST)
        self.assertEqual(self.client.username, TestConfig.TEST_WUG_USERNAME)
        self.assertEqual(self.client.password, TestConfig.TEST_WUG_PASSWORD)
        self.assertIsNotNone(self.client.session)
    
    def test_url_building(self):
        """Test URL building utility"""
        endpoint = "/api/devices"
        full_url = self.client._build_url(endpoint)
        expected = f"{TestConfig.TEST_WUG_HOST}/api/devices"
        self.assertEqual(full_url, expected)
    
    def test_url_building_with_trailing_slash(self):
        """Test URL building handles trailing slashes correctly"""
        client = WUGClient("http://test.com/", "user", "pass")
        endpoint = "/api/devices"
        full_url = client._build_url(endpoint)
        expected = "http://test.com/api/devices"
        self.assertEqual(full_url, expected)
    
    @patch('netbox_wug_sync.wug_client.requests.Session.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.client._make_request("GET", "/api/test")
        
        self.assertEqual(result, {"data": "test"})
        mock_get.assert_called_once()
    
    @patch('netbox_wug_sync.wug_client.requests.Session.get')
    def test_make_request_http_error(self, mock_get):
        """Test HTTP error handling"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        result = self.client._make_request("GET", "/api/test")
        
        self.assertIsNone(result)
    
    @patch('netbox_wug_sync.wug_client.requests.Session.get')
    def test_make_request_connection_error(self, mock_get):
        """Test connection error handling"""
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        result = self.client._make_request("GET", "/api/test")
        
        self.assertIsNone(result)
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_test_connection_success(self, mock_request):
        """Test successful connection test"""
        mock_request.return_value = {"status": "ok"}
        
        result = self.client.test_connection()
        
        self.assertTrue(result)
        mock_request.assert_called_once_with("GET", "/api/info")
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_test_connection_failure(self, mock_request):
        """Test failed connection test"""
        mock_request.return_value = None
        
        result = self.client.test_connection()
        
        self.assertFalse(result)
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_get_devices_success(self, mock_request):
        """Test successful device retrieval"""
        mock_request.return_value = TestConfig.SAMPLE_WUG_DEVICES
        
        devices = self.client.get_devices()
        
        self.assertEqual(len(devices), 3)
        self.assertEqual(devices[0]["name"], "Router1")
        self.assertEqual(devices[1]["name"], "Switch1")
        mock_request.assert_called_once_with("GET", "/api/devices")
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_get_devices_failure(self, mock_request):
        """Test failed device retrieval"""
        mock_request.return_value = None
        
        devices = self.client.get_devices()
        
        self.assertEqual(devices, [])
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_get_device_by_id_success(self, mock_request):
        """Test successful device retrieval by ID"""
        mock_request.return_value = TestConfig.SAMPLE_WUG_DEVICE
        
        device = self.client.get_device_by_id(123)
        
        self.assertEqual(device["name"], "Test Router")
        self.assertEqual(device["id"], 123)
        mock_request.assert_called_once_with("GET", "/api/devices/123")
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_get_device_by_id_not_found(self, mock_request):
        """Test device not found by ID"""
        mock_request.return_value = None
        
        device = self.client.get_device_by_id(999)
        
        self.assertIsNone(device)
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_add_device_success(self, mock_request):
        """Test successful device addition"""
        mock_request.return_value = {"id": 456, "status": "created"}
        
        device_data = {
            "name": "New Device",
            "ipAddress": "192.168.1.100",
            "deviceType": "Switch"
        }
        
        result = self.client.add_device(device_data)
        
        self.assertTrue(result)
        mock_request.assert_called_once_with("POST", "/api/devices", json=device_data)
    
    @patch('netbox_wug_sync.wug_client.WUGClient._make_request')
    def test_add_device_failure(self, mock_request):
        """Test failed device addition"""
        mock_request.return_value = None
        
        device_data = {"name": "New Device"}
        
        result = self.client.add_device(device_data)
        
        self.assertFalse(result)


class WUGSyncManagerTest(TestCase):
    """Test cases for sync manager utility"""
    
    def setUp(self):
        """Set up test data"""
        self.connection = create_test_wug_connection()
        self.sync_manager = WUGSyncManager(self.connection)
    
    def test_sync_manager_initialization(self):
        """Test sync manager initialization"""
        self.assertEqual(self.sync_manager.connection, self.connection)
        self.assertIsNotNone(self.sync_manager.wug_client)
    
    @patch('netbox_wug_sync.sync_utils.WUGClient.get_devices')
    def test_sync_devices_from_wug_success(self, mock_get_devices):
        """Test successful sync from WUG to NetBox"""
        mock_get_devices.return_value = TestConfig.SAMPLE_WUG_DEVICES[:2]  # First 2 devices
        
        result = self.sync_manager.sync_devices_from_wug()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['devices_processed'], 2)
        self.assertGreater(result['devices_created'], 0)
        
        # Verify devices were created
        devices = WUGDevice.objects.filter(wug_connection=self.connection)
        self.assertEqual(devices.count(), 2)
    
    @patch('netbox_wug_sync.sync_utils.WUGClient.get_devices')
    def test_sync_devices_from_wug_failure(self, mock_get_devices):
        """Test failed sync from WUG to NetBox"""
        mock_get_devices.return_value = []
        
        result = self.sync_manager.sync_devices_from_wug()
        
        self.assertTrue(result['success'])  # Empty result is still success
        self.assertEqual(result['devices_processed'], 0)
    
    @patch('netbox_wug_sync.sync_utils.WUGClient.get_devices')
    def test_sync_creates_sync_log(self, mock_get_devices):
        """Test that sync operations create log entries"""
        mock_get_devices.return_value = TestConfig.SAMPLE_WUG_DEVICES[:1]
        
        initial_log_count = WUGSyncLog.objects.count()
        
        self.sync_manager.sync_devices_from_wug()
        
        final_log_count = WUGSyncLog.objects.count()
        self.assertEqual(final_log_count, initial_log_count + 1)
        
        # Verify log details
        log = WUGSyncLog.objects.latest('created')
        self.assertEqual(log.wug_connection, self.connection)
        self.assertEqual(log.sync_type, 'wug_to_netbox')
        self.assertEqual(log.status, 'success')
    
    def test_device_mapping(self):
        """Test WUG device data mapping to NetBox format"""
        wug_device = TestConfig.SAMPLE_WUG_DEVICE
        
        mapped = self.sync_manager._map_wug_device_to_netbox(wug_device)
        
        self.assertEqual(mapped['name'], wug_device['name'])
        self.assertEqual(mapped['wug_device_id'], wug_device['id'])
        self.assertEqual(mapped['ip_address'], wug_device['ipAddress'])
        self.assertEqual(mapped['device_type'], wug_device['deviceType'])
        self.assertEqual(mapped['manufacturer'], wug_device['manufacturer'])
        self.assertEqual(mapped['model'], wug_device['model'])
    
    def test_device_mapping_with_missing_fields(self):
        """Test device mapping handles missing fields gracefully"""
        incomplete_device = {
            "id": 123,
            "name": "Incomplete Device",
            "ipAddress": "192.168.1.50"
            # Missing other fields
        }
        
        mapped = self.sync_manager._map_wug_device_to_netbox(incomplete_device)
        
        self.assertEqual(mapped['name'], "Incomplete Device")
        self.assertEqual(mapped['wug_device_id'], 123)
        self.assertEqual(mapped['ip_address'], "192.168.1.50")
        self.assertIn('device_type', mapped)  # Should have default
        self.assertIn('manufacturer', mapped)  # Should have default


class SyncUtilsIntegrationTest(TestCase):
    """Integration tests for sync utilities"""
    
    def setUp(self):
        """Set up test data"""
        self.connection = create_test_wug_connection()
    
    @patch('netbox_wug_sync.wug_client.WUGClient.test_connection')
    def test_connection_validation(self, mock_test):
        """Test connection validation before sync"""
        from netbox_wug_sync.sync_utils import validate_wug_connection
        
        # Test successful validation
        mock_test.return_value = True
        result = validate_wug_connection(self.connection)
        self.assertTrue(result)
        
        # Test failed validation
        mock_test.return_value = False
        result = validate_wug_connection(self.connection)
        self.assertFalse(result)
    
    def test_error_handling_in_sync(self):
        """Test error handling during sync operations"""
        from netbox_wug_sync.sync_utils import WUGSyncManager
        
        # Create sync manager with invalid connection
        invalid_connection = WUGConnection.objects.create(
            name="Invalid Server",
            host="http://invalid.example.com",
            username="invalid",
            password="invalid"
        )
        
        sync_manager = WUGSyncManager(invalid_connection)
        
        # Should handle errors gracefully
        result = sync_manager.sync_devices_from_wug()
        
        # Should log the failure
        logs = WUGSyncLog.objects.filter(wug_connection=invalid_connection)
        self.assertGreater(logs.count(), 0)
        
        error_log = logs.latest('created')
        self.assertEqual(error_log.status, 'error')