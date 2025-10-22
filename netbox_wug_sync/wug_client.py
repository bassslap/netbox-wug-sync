"""
WhatsUp Gold API Client

This module provides a Python client for interacting with the WhatsUp Gold REST API.
Based on typical WhatsUp Gold API patterns and the Swagger endpoint reference.
"""

import json
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


class WUGAPIException(Exception):
    """Custom exception for WhatsUp Gold API errors"""
    pass


class WUGAuthenticationError(WUGAPIException):
    """Exception raised for authentication failures"""
    pass


class WUGAPIClient:
    """WhatsUp Gold REST API Client"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 9644, 
                 use_ssl: bool = True, verify_ssl: bool = False, timeout: int = 30):
        """
        Initialize WhatsUp Gold API client
        
        Args:
            host: WUG server hostname or IP
            username: WUG username for API access
            password: WUG password
            port: WUG API port (default: 9644)
            use_ssl: Use HTTPS (default: True)
            verify_ssl: Verify SSL certificates (default: False)
            timeout: Request timeout in seconds (default: 30)
        """
        self.username = username
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        # Sanitize host - remove protocol if included
        if host.startswith('http://') or host.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(host)
            self.host = parsed.hostname
            # Use port from URL if not explicitly provided
            if parsed.port and port == 9644:  # 9644 is default
                self.port = parsed.port
        else:
            self.host = host
        
        # Build base URL
        protocol = 'https' if use_ssl else 'http'
        self.base_url = f"{protocol}://{self.host}:{self.port}/api"
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        # Authentication token
        self._token = None
        self._token_expires = None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def close(self):
        """Close the session"""
        if self.session:
            self.session.close()
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, 
                     params: Dict = None, authenticated: bool = True) -> Dict:
        """
        Make HTTP request to WUG API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: URL parameters
            authenticated: Whether to include authentication
            
        Returns:
            Response data as dictionary
            
        Raises:
            WUGAPIException: For API errors
            WUGAuthenticationError: For authentication errors
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Add authentication if required
        if authenticated:
            self._ensure_authenticated()
            headers['Authorization'] = f'Bearer {self._token}'
        
        # Prepare request data
        kwargs = {
            'headers': headers,
            'timeout': self.timeout,
            'params': params
        }
        
        if data is not None:
            kwargs['json'] = data
        
        try:
            logger.debug(f"Making {method} request to {url}")
            response = self.session.request(method, url, **kwargs)
            
            # Log response status
            logger.debug(f"Response status: {response.status_code}")
            
            # Handle different response codes
            if response.status_code == 401:
                # Clear token and retry once
                self._token = None
                if authenticated:
                    self._ensure_authenticated()
                    headers['Authorization'] = f'Bearer {self._token}'
                    kwargs['headers'] = headers
                    response = self.session.request(method, url, **kwargs)
                    
                    if response.status_code == 401:
                        raise WUGAuthenticationError("Authentication failed")
            
            # Raise exception for bad status codes
            response.raise_for_status()
            
            # Parse JSON response
            try:
                return response.json()
            except ValueError:
                # Return empty dict if no JSON content
                return {}
                
        except requests.exceptions.Timeout:
            raise WUGAPIException(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise WUGAPIException(f"Connection error: {str(e)}")
        except requests.exceptions.HTTPError as e:
            raise WUGAPIException(f"HTTP error {response.status_code}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise WUGAPIException(f"Request error: {str(e)}")
    
    def _make_request_raw(self, method: str, endpoint: str, headers: Dict = None) -> Dict:
        """
        Make raw HTTP request to WUG API (for basic auth)
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            headers: Request headers
            
        Returns:
            Response data as dictionary
        """
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        
        default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if headers:
            default_headers.update(headers)
        
        try:
            logger.debug(f"Making {method} request to {url} with basic auth")
            response = self.session.request(method, url, headers=default_headers, timeout=self.timeout)
            
            logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            
            try:
                return response.json()
            except ValueError:
                return {}
                
        except requests.exceptions.Timeout:
            raise WUGAPIException(f"Request timeout after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise WUGAPIException(f"Connection error: {str(e)}")
        except requests.exceptions.HTTPError as e:
            raise WUGAPIException(f"HTTP error {response.status_code}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise WUGAPIException(f"Request error: {str(e)}")
    
    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token"""
        if self._token is None or self._is_token_expired():
            self._authenticate()
    
    def _is_token_expired(self) -> bool:
        """Check if the current token is expired"""
        if self._token_expires is None:
            return True
        return datetime.now(timezone.utc) >= self._token_expires
    
    def _authenticate(self):
        """Authenticate with WhatsUp Gold and get access token"""
        auth_data = {
            'username': self.username,
            'password': self.password
        }
        
        # Debug logging (remove password from logs for security)
        logger.info(f"Attempting authentication with username: '{self.username}' (password length: {len(self.password)})")
        
        # Try different WhatsUp Gold API authentication endpoints and methods
        auth_attempts = [
            ('/api/v1/token', 'json'),  # JSON payload
            ('/api/token', 'json'),
            ('/api/v1/token', 'basic'),  # Basic auth
            ('/api/token', 'basic'),
            ('/auth/token', 'json'),
            ('/NmConsole/api/token', 'json')
        ]
        
        last_error = None
        for endpoint, auth_method in auth_attempts:
            try:
                logger.info(f"Trying authentication endpoint: {endpoint} with method: {auth_method}")
                
                if auth_method == 'basic':
                    # Try basic authentication
                    import base64
                    credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                    headers = {'Authorization': f'Basic {credentials}'}
                    response = self._make_request_raw('POST', endpoint, headers=headers)
                else:
                    # Try JSON payload authentication
                    response = self._make_request('POST', endpoint, data=auth_data, authenticated=False)
                
                self._token = response.get('token') or response.get('access_token')
                if self._token:
                    # Calculate token expiration (assume 1 hour if not provided)
                    expires_in = response.get('expires_in', 3600)  # seconds
                    self._token_expires = datetime.now(timezone.utc).replace(
                        microsecond=0
                    ) + timedelta(seconds=expires_in - 60)  # Refresh 1 minute early
                    
                    logger.info(f"Successfully authenticated with WhatsUp Gold using endpoint: {endpoint} method: {auth_method}")
                    return
                else:
                    logger.warning(f"No token returned from endpoint {endpoint} method {auth_method}")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Authentication failed for endpoint {endpoint} method {auth_method}: {str(e)}")
                continue
        
        # If all endpoints failed
        if last_error:
            raise WUGAuthenticationError(f"Authentication failed on all endpoints and methods. Last error: {str(last_error)}")
        else:
            raise WUGAuthenticationError("No token returned from any authentication endpoint or method")
    
    def test_connection(self) -> Dict:
        """
        Test the API connection and authentication
        
        Returns:
            Dictionary with connection test results
        """
        try:
            # First test basic connectivity without authentication
            test_url = f"{self.base_url.split('/api')[0]}"
            logger.info(f"Testing basic connectivity to: {test_url}")
            
            response = self.session.get(test_url, verify=self.verify_ssl, timeout=self.timeout)
            logger.info(f"Basic connectivity test: {response.status_code}")
            
            # Test if API endpoint exists at all
            api_test_url = self.base_url
            logger.info(f"Testing API endpoint: {api_test_url}")
            
            api_response = self.session.get(api_test_url, verify=self.verify_ssl, timeout=self.timeout)
            logger.info(f"API endpoint test: {api_response.status_code}")
            
            # Try to get system information or device count as a test
            response = self._make_request('GET', '/system/info')
            return {
                'success': True,
                'message': 'Connection successful',
                'server_info': response
            }
        except WUGAuthenticationError:
            return {
                'success': False,
                'message': 'Authentication failed - check username and password'
            }
        except WUGAPIException as e:
            return {
                'success': False,
                'message': f'API error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    def get_devices(self, include_details: bool = True) -> List[Dict]:
        """
        Get all devices from WhatsUp Gold
        
        Args:
            include_details: Whether to include detailed device information
            
        Returns:
            List of device dictionaries
        """
        try:
            # Get basic device list
            devices = self._make_request('GET', '/devices')
            
            # Ensure we have a list
            if isinstance(devices, dict):
                devices = devices.get('devices', [])
            
            if include_details:
                # Get detailed information for each device
                detailed_devices = []
                for device in devices:
                    device_id = device.get('id') or device.get('deviceId')
                    if device_id:
                        try:
                            detail = self.get_device_details(device_id)
                            device.update(detail)
                        except Exception as e:
                            logger.warning(f"Failed to get details for device {device_id}: {e}")
                    detailed_devices.append(device)
                return detailed_devices
            
            return devices
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get devices: {str(e)}")
    
    def get_device_details(self, device_id: Union[int, str]) -> Dict:
        """
        Get detailed information for a specific device
        
        Args:
            device_id: Device ID in WhatsUp Gold
            
        Returns:
            Device details dictionary
        """
        try:
            return self._make_request('GET', f'/devices/{device_id}')
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get device details for {device_id}: {str(e)}")
    
    def get_updated_devices(self, since: datetime) -> List[Dict]:
        """
        Get devices that have been updated since a specific timestamp
        
        Args:
            since: DateTime to check for updates since
            
        Returns:
            List of updated device dictionaries
        """
        try:
            # Format timestamp for API (adjust format as needed for WUG API)
            timestamp = since.isoformat()
            
            params = {'since': timestamp}
            return self._make_request('GET', '/devices/updated', params=params)
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get updated devices: {str(e)}")
    
    def get_device_groups(self) -> List[Dict]:
        """
        Get all device groups from WhatsUp Gold
        
        Returns:
            List of device group dictionaries
        """
        try:
            response = self._make_request('GET', '/groups')
            
            # Ensure we have a list
            if isinstance(response, dict):
                return response.get('groups', [])
            return response
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get device groups: {str(e)}")
    
    def scan_network(self, network: str) -> Dict:
        """
        Initiate a network scan in WhatsUp Gold
        
        Args:
            network: Network range to scan (e.g., "192.168.1.0/24")
            
        Returns:
            Scan operation result dictionary
        """
        try:
            data = {'network': network}
            return self._make_request('POST', '/scan/network', data=data)
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to initiate network scan: {str(e)}")
    
    def get_scan_status(self, scan_id: Union[int, str]) -> Dict:
        """
        Get the status of a network scan
        
        Args:
            scan_id: Scan operation ID
            
        Returns:
            Scan status dictionary
        """
        try:
            return self._make_request('GET', f'/scan/{scan_id}/status')
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get scan status: {str(e)}")
    
    def add_device(self, device_data: Dict) -> Dict:
        """
        Add a new device to WhatsUp Gold
        
        Args:
            device_data: Device configuration dictionary
            
        Returns:
            Created device information
        """
        try:
            return self._make_request('POST', '/devices', data=device_data)
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to add device: {str(e)}")
    
    def update_device(self, device_id: Union[int, str], device_data: Dict) -> Dict:
        """
        Update an existing device in WhatsUp Gold
        
        Args:
            device_id: Device ID to update
            device_data: Updated device configuration
            
        Returns:
            Updated device information
        """
        try:
            return self._make_request('PUT', f'/devices/{device_id}', data=device_data)
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to update device {device_id}: {str(e)}")
    
    def delete_device(self, device_id: Union[int, str]) -> bool:
        """
        Delete a device from WhatsUp Gold
        
        Args:
            device_id: Device ID to delete
            
        Returns:
            True if successful
        """
        try:
            self._make_request('DELETE', f'/devices/{device_id}')
            return True
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to delete device {device_id}: {str(e)}")
    
    # NetBox to WUG Export Methods
    
    def scan_ip_address(self, ip_address: str, scan_options: Dict = None) -> Dict:
        """
        Trigger a scan of a specific IP address in WhatsUp Gold
        
        Args:
            ip_address: IP address to scan
            scan_options: Optional scan configuration parameters
            
        Returns:
            Scan operation result dictionary with scan_id
        """
        try:
            data = {
                'ip_address': ip_address,
                'scan_type': 'discovery'
            }
            
            # Add optional scan parameters
            if scan_options:
                data.update(scan_options)
            
            response = self._make_request('POST', '/scan/ip', data=data)
            
            # Ensure we have a scan ID
            scan_id = response.get('scan_id') or response.get('id')
            if not scan_id:
                raise WUGAPIException("No scan ID returned from IP scan request")
            
            return {
                'success': True,
                'scan_id': scan_id,
                'message': f'Scan initiated for IP {ip_address}',
                'scan_details': response
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to scan IP {ip_address}: {str(e)}")
    
    def scan_ip_range(self, ip_range: str, scan_options: Dict = None) -> Dict:
        """
        Trigger a scan of an IP range in WhatsUp Gold
        
        Args:
            ip_range: IP range to scan (e.g., "192.168.1.0/24" or "192.168.1.1-192.168.1.50")
            scan_options: Optional scan configuration parameters
            
        Returns:
            Scan operation result dictionary
        """
        try:
            data = {
                'ip_range': ip_range,
                'scan_type': 'range_discovery'
            }
            
            if scan_options:
                data.update(scan_options)
            
            response = self._make_request('POST', '/scan/range', data=data)
            
            return {
                'success': True,
                'scan_id': response.get('scan_id') or response.get('id'),
                'message': f'Range scan initiated for {ip_range}',
                'scan_details': response
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to scan IP range {ip_range}: {str(e)}")
    
    def add_device_by_ip(self, ip_address: str, device_config: Dict = None) -> Dict:
        """
        Add a device to WhatsUp Gold by IP address
        
        Args:
            ip_address: IP address of device to add
            device_config: Optional device configuration parameters
            
        Returns:
            Device creation result dictionary
        """
        try:
            data = {
                'ip_address': ip_address,
                'discovery_method': 'ip'
            }
            
            # Add device configuration if provided
            if device_config:
                data.update(device_config)
            
            # Set defaults for NetBox-sourced devices
            if 'device_name' not in data:
                data['device_name'] = f"NetBox-{ip_address}"
            
            if 'group' not in data:
                data['group'] = 'NetBox Imports'
            
            response = self._make_request('POST', '/devices/add-by-ip', data=data)
            
            return {
                'success': True,
                'device_id': response.get('device_id') or response.get('id'),
                'message': f'Device added for IP {ip_address}',
                'device_details': response
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to add device by IP {ip_address}: {str(e)}")
    
    def update_device_metadata(self, device_id: Union[int, str], metadata: Dict) -> Dict:
        """
        Update device metadata in WhatsUp Gold with NetBox information
        
        Args:
            device_id: WhatsUp Gold device ID
            metadata: Metadata dictionary from NetBox
            
        Returns:
            Update result dictionary
        """
        try:
            # Prepare metadata update
            data = {
                'metadata_source': 'NetBox',
                'custom_fields': {}
            }
            
            # Map NetBox device information to WUG custom fields
            if metadata.get('netbox_name'):
                data['custom_fields']['netbox_device_name'] = metadata['netbox_name']
            
            if metadata.get('netbox_site'):
                data['custom_fields']['netbox_site'] = metadata['netbox_site']
            
            if metadata.get('netbox_role'):
                data['custom_fields']['netbox_device_role'] = metadata['netbox_role']
            
            if metadata.get('netbox_type'):
                data['custom_fields']['netbox_device_type'] = metadata['netbox_type']
            
            if metadata.get('netbox_platform'):
                data['custom_fields']['netbox_platform'] = metadata['netbox_platform']
            
            if metadata.get('netbox_serial'):
                data['custom_fields']['netbox_serial'] = metadata['netbox_serial']
            
            if metadata.get('netbox_asset_tag'):
                data['custom_fields']['netbox_asset_tag'] = metadata['netbox_asset_tag']
            
            # Update device notes/description
            if metadata.get('netbox_description'):
                data['description'] = f"NetBox: {metadata['netbox_description']}"
            
            response = self._make_request('PUT', f'/devices/{device_id}/metadata', data=data)
            
            return {
                'success': True,
                'device_id': device_id,
                'message': 'Device metadata updated from NetBox',
                'update_details': response
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to update device metadata for {device_id}: {str(e)}")
    
    def get_scan_results(self, scan_id: Union[int, str]) -> Dict:
        """
        Get detailed results from a completed scan
        
        Args:
            scan_id: Scan operation ID
            
        Returns:
            Scan results dictionary
        """
        try:
            response = self._make_request('GET', f'/scan/{scan_id}/results')
            
            return {
                'scan_id': scan_id,
                'status': response.get('status'),
                'devices_found': response.get('devices_found', []),
                'scan_summary': response.get('summary', {}),
                'completion_time': response.get('completion_time'),
                'error_details': response.get('errors', [])
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get scan results for {scan_id}: {str(e)}")
    
    def bulk_add_ips(self, ip_addresses: List[str], batch_config: Dict = None) -> Dict:
        """
        Add multiple IP addresses to WhatsUp Gold in a batch operation
        
        Args:
            ip_addresses: List of IP addresses to add
            batch_config: Optional batch configuration parameters
            
        Returns:
            Batch operation result dictionary
        """
        try:
            data = {
                'ip_addresses': ip_addresses,
                'operation': 'bulk_add',
                'source': 'NetBox'
            }
            
            if batch_config:
                data.update(batch_config)
            
            # Set defaults for batch operations
            if 'group' not in data:
                data['group'] = 'NetBox Bulk Import'
            
            if 'scan_after_add' not in data:
                data['scan_after_add'] = True
            
            response = self._make_request('POST', '/devices/bulk-add', data=data)
            
            return {
                'success': True,
                'batch_id': response.get('batch_id'),
                'added_count': response.get('added_count', 0),
                'failed_count': response.get('failed_count', 0),
                'scan_ids': response.get('scan_ids', []),
                'message': f'Bulk operation initiated for {len(ip_addresses)} IP addresses',
                'batch_details': response
            }
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to bulk add IPs: {str(e)}")


# Utility functions for data transformation
def normalize_wug_device_data(wug_device: Dict) -> Dict:
    """
    Normalize WhatsUp Gold device data to a standard format
    
    Args:
        wug_device: Raw device data from WUG API
        
    Returns:
        Normalized device data dictionary
    """
    # Map common WUG field names to standardized names
    field_mapping = {
        'deviceId': 'id',
        'deviceName': 'name',
        'displayName': 'display_name',
        'ipAddress': 'ip_address',
        'macAddress': 'mac_address',
        'deviceType': 'device_type',
        'manufacturer': 'vendor',
        'model': 'model',
        'osVersion': 'os_version',
        'groupName': 'group',
        'location': 'location',
        'status': 'status',
        'lastSeen': 'last_seen',
    }
    
    normalized = {}
    
    # Map known fields
    for wug_field, std_field in field_mapping.items():
        if wug_field in wug_device:
            normalized[std_field] = wug_device[wug_field]
    
    # Keep original data for reference
    normalized['raw_data'] = wug_device
    
    # Parse timestamps
    if 'last_seen' in normalized and isinstance(normalized['last_seen'], str):
        try:
            normalized['last_seen'] = datetime.fromisoformat(normalized['last_seen'].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            normalized['last_seen'] = None
    
    return normalized


def create_netbox_device_data(wug_device: Dict, site_id: int = None, 
                             device_type_id: int = None, device_role_id: int = None) -> Dict:
    """
    Create NetBox device data from WhatsUp Gold device information
    
    Args:
        wug_device: Normalized WUG device data
        site_id: NetBox site ID
        device_type_id: NetBox device type ID  
        device_role_id: NetBox device role ID
        
    Returns:
        NetBox device creation data
    """
    netbox_data = {
        'name': wug_device.get('name', f"wug-device-{wug_device.get('id')}"),
        'status': 'active',  # Default to active
    }
    
    # Add optional fields if provided
    if site_id:
        netbox_data['site'] = site_id
    if device_type_id:
        netbox_data['device_type'] = device_type_id
    if device_role_id:
        netbox_data['device_role'] = device_role_id
    
    # Add custom fields for WUG data
    custom_fields = {}
    
    if wug_device.get('ip_address'):
        # Primary IP will be handled separately
        custom_fields['wug_ip_address'] = wug_device['ip_address']
    
    if wug_device.get('mac_address'):
        custom_fields['wug_mac_address'] = wug_device['mac_address']
    
    if wug_device.get('vendor'):
        custom_fields['wug_vendor'] = wug_device['vendor']
    
    if wug_device.get('model'):
        custom_fields['wug_model'] = wug_device['model']
    
    if wug_device.get('os_version'):
        custom_fields['wug_os_version'] = wug_device['os_version']
    
    if wug_device.get('group'):
        custom_fields['wug_group'] = wug_device['group']
    
    if wug_device.get('location'):
        custom_fields['wug_location'] = wug_device['location']
    
    if custom_fields:
        netbox_data['custom_fields'] = custom_fields
    
    return netbox_data