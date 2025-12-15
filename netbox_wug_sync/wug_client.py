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
        
        # Build base URL - WhatsUp Gold API is at /api/v1
        protocol = 'https' if use_ssl else 'http'
        self.base_url = f"{protocol}://{self.host}:{self.port}/api/v1"
        
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
        # Build full URL - endpoint should start with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        url = self.base_url + endpoint
        
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
            # Try to get error details from response body
            error_detail = ""
            try:
                error_body = response.json()
                error_detail = f" - Details: {error_body}"
            except:
                try:
                    error_detail = f" - Response: {response.text[:500]}"
                except:
                    pass
            raise WUGAPIException(f"HTTP error {response.status_code}: {str(e)}{error_detail}")
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
        """Authenticate with WhatsUp Gold using OAuth 2.0 password grant"""
        logger.info(f"Starting WUG OAuth 2.0 authentication to {self.base_url}")
        
        # WhatsUp Gold uses OAuth 2.0 with password grant type
        # Must use form-encoded data, not JSON
        auth_data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password
        }
        
        logger.info(f"Attempting OAuth 2.0 authentication with username: '{self.username}'")
        
        try:
            # WhatsUp Gold token endpoint is at /api/v1/token (not within our base URL)
            base_url_no_api = self.base_url.replace('/api/v1', '')
            token_url = f"{base_url_no_api}/api/v1/token"
            
            logger.info(f"Posting to token endpoint: {token_url}")
            
            # OAuth 2.0 requires form-encoded data but JSON content-type (per PowerShell implementation)
            response = requests.post(
                token_url,
                data=auth_data,  # Use data= for form encoding, not json=
                headers={'Content-Type': 'application/json'},  # Match PowerShell implementation
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            logger.info(f"Authentication response: Status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"OAuth response data keys: {list(data.keys())}")
                
                self._token = data.get('access_token')
                if self._token:
                    # Calculate token expiration
                    expires_in = data.get('expires_in', 3600)  # seconds
                    self._token_expires = datetime.now(timezone.utc).replace(
                        microsecond=0
                    ) + timedelta(seconds=expires_in - 60)  # Refresh 1 minute early
                    
                    logger.info(f"Successfully authenticated with WhatsUp Gold! Token expires in {expires_in} seconds")
                    return
                else:
                    logger.error(f"No access_token in response: {data}")
                    raise WUGAuthenticationError("No access_token returned from OAuth endpoint")
            else:
                error_text = response.text
                logger.error(f"Authentication failed: Status {response.status_code}, Response: {error_text}")
                raise WUGAuthenticationError(f"OAuth authentication failed: {response.status_code} - {error_text}")
                
        except requests.RequestException as e:
            logger.error(f"Request error during authentication: {e}")
            raise WUGAuthenticationError(f"Authentication request failed: {str(e)}")
    
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
            
            # Try to discover available API endpoints based on working Swagger endpoints
            logger.info("=== Testing WhatsUp Gold API v1 endpoints ===")
            test_endpoints = [
                '/product/version',     # Product version (working)
                '/device-groups/-',     # Device groups (working)
                '/monitors/-',          # Monitor templates (working)
                '/credentials/-',       # Credentials (working)
            ]
            
            working_endpoints = []
            for endpoint in test_endpoints:
                try:
                    response = self._make_request('GET', endpoint)
                    working_endpoints.append(endpoint)
                    logger.info(f"✅ SUCCESS: {endpoint} - Status: 200")
                    if isinstance(response, dict) and 'data' in response:
                        data = response['data']
                        if isinstance(data, list):
                            logger.info(f"   Found {len(data)} items")
                            # Show first item structure if available
                            if len(data) > 0 and isinstance(data[0], dict):
                                keys = list(data[0].keys())[:5]  # First 5 keys
                                logger.info(f"   Sample keys: {keys}")
                        elif isinstance(data, dict):
                            keys = list(data.keys())[:5]  # First 5 keys
                            logger.info(f"   Response keys: {keys}")
                    else:
                        logger.info(f"   Response type: {type(response)}")
                except Exception as e:
                    logger.info(f"❌ FAILED: {endpoint} - {str(e)}")
            
            if working_endpoints:
                logger.info(f"🎉 Found working endpoints: {working_endpoints}")
                return {
                    'success': True,
                    'message': f'Connection successful! Found {len(working_endpoints)} working endpoints.',
                    'working_endpoints': working_endpoints
                }
            else:
                return {
                    'success': False,
                    'message': 'Authentication successful but no API endpoints found. Check API documentation.'
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
            all_devices = []
            
            # First get all device groups
            groups_response = self._make_request('GET', '/device-groups/-')
            
            if not isinstance(groups_response, dict) or 'data' not in groups_response:
                logger.warning("Unexpected device groups response format")
                return []
            
            groups_data = groups_response['data']
            groups = groups_data.get('groups', [])
            
            logger.info(f"Found {len(groups)} device groups")
            
            # Get devices from each group
            for group in groups:
                group_id = group.get('id')
                group_name = group.get('name', 'Unknown')
                
                if not group_id:
                    continue
                
                try:
                    logger.debug(f"Getting devices from group: {group_name} (ID: {group_id})")
                    devices_response = self._make_request('GET', f'/device-groups/{group_id}/devices')
                    
                    if isinstance(devices_response, dict) and 'data' in devices_response:
                        devices_data = devices_response['data']
                        devices = devices_data.get('devices', [])
                        
                        # Add group information to devices
                        for device in devices:
                            device['group_id'] = group_id
                            device['group_name'] = group_name
                            
                            # Avoid duplicates by checking device ID
                            device_id = device.get('id')
                            if device_id and not any(d.get('id') == device_id for d in all_devices):
                                all_devices.append(device)
                                
                        logger.debug(f"Found {len(devices)} devices in group {group_name}")
                        
                except Exception as e:
                    logger.warning(f"Failed to get devices from group {group_name}: {e}")
                    continue
            
            logger.info(f"Total unique devices found: {len(all_devices)}")
            
            # Get detailed information if requested
            if include_details:
                detailed_devices = []
                for device in all_devices:
                    device_id = device.get('id')
                    if device_id:
                        try:
                            # Get detailed device information
                            detail = self.get_device_details(device_id)
                            device.update(detail)
                        except Exception as e:
                            logger.warning(f"Failed to get details for device {device_id}: {e}")
                    detailed_devices.append(device)
                return detailed_devices
            
            return all_devices
            
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
            response = self._make_request('GET', '/device-groups/-')
            
            # Response structure: {'paging': {...}, 'data': {'groups': [...]}}
            if isinstance(response, dict):
                data = response.get('data', {})
                return data.get('groups', [])
            return response
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to get device groups: {str(e)}")
    
    def find_group_recursive(self, group_name: str) -> Optional[Dict]:
        """
        Recursively search for a group by name in the entire group hierarchy
        
        Args:
            group_name: Name of the group to find
            
        Returns:
            Group dictionary if found, None otherwise
        """
        try:
            groups = self.get_device_groups()
            
            # Search all groups (flat list includes nested groups)
            for group in groups:
                if group.get('name') == group_name:
                    logger.info(f"Found group '{group_name}' with ID {group.get('id')}")
                    return group
            
            logger.warning(f"Group '{group_name}' not found in WUG hierarchy")
            return None
            
        except Exception as e:
            logger.error(f"Failed to search for group '{group_name}': {e}")
            return None
    
    def get_group_path(self, group_name: str) -> Optional[str]:
        """
        Get the full hierarchical path for a group by walking up the parent chain
        
        Args:
            group_name: Name of the group to find the path for
            
        Returns:
            Full group path (e.g., "ParentGroup\\ChildGroup") or just the group name if no parents
            None if group not found
        """
        try:
            groups = self.get_device_groups()
            
            # Build a lookup dictionary by group ID and name
            groups_by_id = {g['id']: g for g in groups}
            groups_by_name = {g['name']: g for g in groups}
            
            # Find the target group
            if group_name not in groups_by_name:
                logger.warning(f"Group '{group_name}' not found in WUG")
                return None
            
            target_group = groups_by_name[group_name]
            
            # Build path by walking up parent chain
            path_parts = [target_group['name']]
            current_parent_id = target_group.get('parentGroupId', '')
            
            # Walk up the parent chain (max 10 levels to prevent infinite loops)
            max_depth = 10
            while current_parent_id and current_parent_id != '0' and current_parent_id != '' and max_depth > 0:
                if current_parent_id in groups_by_id:
                    parent_group = groups_by_id[current_parent_id]
                    path_parts.insert(0, parent_group['name'])
                    current_parent_id = parent_group.get('parentGroupId', '')
                else:
                    break
                max_depth -= 1
            
            # Join path parts with backslash
            full_path = '\\'.join(path_parts)
            logger.info(f"Resolved group path for '{group_name}': {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"Failed to get group path for '{group_name}': {e}")
            return None
    
    def create_group(self, group_name: str, parent_group: str = "My Network") -> Dict:
        """
        Create a new device group in WhatsUp Gold
        
        Args:
            group_name: Name of the group to create
            parent_group: Parent group name (default: "My Network")
            
        Returns:
            Created group data as dictionary
        """
        try:
            logger.info(f"Creating WUG group '{group_name}' under parent '{parent_group}'")
            
            # WUG group creation payload
            group_data = {
                "name": group_name,
                "parentGroup": parent_group
            }
            
            response = self._make_request('POST', '/device-groups/-', data=group_data)
            logger.info(f"Successfully created group '{group_name}' in WUG")
            return response
            
        except WUGAPIException as e:
            # If group already exists, log but don't fail
            if "already exists" in str(e).lower() or "409" in str(e):
                logger.info(f"Group '{group_name}' already exists in WUG")
                return {"name": group_name, "status": "already_exists"}
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to create group '{group_name}': {str(e)}")
    
    def ensure_group_exists(self, group_name: str, parent_group: str = "My Network") -> bool:
        """
        Ensure a group exists in WUG, creating it if necessary
        
        Args:
            group_name: Name of the group to ensure exists
            parent_group: Parent group name (default: "My Network")
            
        Returns:
            True if group exists or was created successfully
        """
        try:
            # Check if group already exists
            groups = self.get_device_groups()
            for group in groups:
                if group.get('name') == group_name:
                    logger.info(f"Group '{group_name}' already exists in WUG")
                    return True
            
            # Group doesn't exist, create it
            logger.info(f"Group '{group_name}' not found, creating it")
            self.create_group(group_name, parent_group)
            return True
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to ensure group exists '{group_name}': {str(e)}")
    
    def add_device_to_group(self, device_id: str, group_id: str) -> bool:
        """
        Add a device to a group in WhatsUp Gold
        
        Args:
            device_id: Device ID to add to group
            group_id: Group ID to add device to
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Adding device {device_id} to group {group_id}")
            
            # Use PUT to add device to group
            endpoint = f'/device-groups/{group_id}/devices/{device_id}'
            response = self._make_request('PUT', endpoint)
            
            logger.info(f"Successfully added device {device_id} to group {group_id}")
            return True
            
        except WUGAPIException as e:
            logger.error(f"Failed to add device to group: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to add device {device_id} to group {group_id}: {e}")
            return False
    
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
            # In WhatsUp Gold, devices are managed as "monitors"
            # Try to add the device using the monitors endpoint first
            monitor_data = {
                'networkAddress': ip_address,
                'displayName': device_config.get('displayName', ip_address) if device_config else ip_address,
                'description': device_config.get('description', f'Device added from NetBox: {ip_address}') if device_config else f'Device added from NetBox: {ip_address}',
                'enabled': True,
                'monitoringSettings': {
                    'enableMonitoring': True
                }
            }
            
            # Add device configuration if provided
            if device_config:
                if 'community' in device_config:
                    monitor_data['snmpCommunity'] = device_config['community']
                if 'snmpVersion' in device_config:
                    monitor_data['snmpVersion'] = device_config['snmpVersion']
                if 'location' in device_config:
                    monitor_data['location'] = device_config['location']
                if 'contact' in device_config:
                    monitor_data['contact'] = device_config['contact']
            
            # Try POST to /monitors/- endpoint first
            try:
                response = self._make_request('POST', '/monitors/-', data=monitor_data)
                device_id = response.get('id') or response.get('monitorId') or response.get('deviceId')
                
                return {
                    'success': True,
                    'deviceId': device_id,
                    'id': device_id,
                    'message': f'Monitor successfully added for IP {ip_address}',
                    'response': response
                }
            except WUGAPIException as e:
                if "405" in str(e) or "Method Not Allowed" in str(e) or "404" in str(e):
                    # If POST /monitors/- fails, fallback to the bulk new device approach
                    logger.info(f"POST /monitors/- failed, trying bulk newDevice approach for {ip_address}")
                    return self._add_device_via_bulk_endpoint(ip_address, device_config)
                else:
                    raise
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to add device by IP {ip_address}: {str(e)}")
    
    def _add_device_via_bulk_endpoint(self, ip_address: str, device_config: Dict = None) -> Dict:
        """
        Fallback method to add device using the bulk newDevice endpoint
        """
        try:
            # Find a suitable device group
            groups_response = self._make_request('GET', '/device-groups/-')
            
            target_group_id = None
            if isinstance(groups_response, dict) and 'data' in groups_response:
                groups = groups_response['data'].get('groups', [])
                
                # Look for "Discovered Devices" group first
                for group in groups:
                    if group.get('name') == 'Discovered Devices':
                        target_group_id = group.get('id')
                        break
                
                # If not found, use "My Network" as fallback
                if not target_group_id:
                    for group in groups:
                        if group.get('name') == 'My Network':
                            target_group_id = group.get('id')
                            break
                
                # If still not found, use the first available group
                if not target_group_id and groups:
                    target_group_id = groups[0].get('id')
            
            if not target_group_id:
                raise WUGAPIException("No suitable device group found for adding devices")
            
            # Prepare device addition data based on Swagger BulkNewDeviceOptions
            data = {
                'ipOrNames': [ip_address],
                'forceAdd': False,  # Perform scanning
                'resolveDNSHostNames': True,
                'expandVirtualEnvironment': True,
                'expandWirelessEnvironment': True,
                'useAllCredentials': True
            }
            
            # Add device configuration if provided
            if device_config:
                # Map common device config options
                if 'force_add' in device_config:
                    data['forceAdd'] = device_config['force_add']
                if 'force_create' in device_config:
                    data['forceCreate'] = device_config['force_create']
                if 'role' in device_config:
                    data['forceRole'] = device_config['role']
                if 'credentials' in device_config:
                    data['credentials'] = device_config['credentials']
            
            # Try both POST and PUT methods for the newDevice endpoint
            for method in ['POST', 'PUT']:
                try:
                    response = self._make_request(method, f'/device-groups/{target_group_id}/newDevice', data=data)
                    
                    return {
                        'success': True,
                        'message': f'Device addition initiated for IP {ip_address} in group {target_group_id} via {method}',
                        'operation_details': response
                    }
                except WUGAPIException as e:
                    if "405" in str(e) and method == 'POST':
                        # Try PUT if POST fails
                        continue
                    else:
                        raise
            
            raise WUGAPIException(f"Both POST and PUT methods failed for newDevice endpoint")
            
        except WUGAPIException:
            raise
        except Exception as e:
            raise WUGAPIException(f"Failed to add device via bulk endpoint for IP {ip_address}: {str(e)}")
    
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

    def discover_endpoints(self):
        """Discover available API endpoints using real WhatsUp Gold API paths."""
        logger.info("Discovering WhatsUp Gold API endpoints...")
        endpoints = {}
        
        # Based on actual working Swagger API endpoints
        test_patterns = [
            # Device management - primary endpoints for our sync
            '/device-groups/-',          # Get all device groups (WORKING)
            '/monitors/-',               # Get all monitors (WORKING)
            '/credentials/-',            # Get all credentials (WORKING)
            '/device-role/-',            # Get all device roles (WORKING)
            
            # Product information
            '/product/version',          # Get product version (WORKING)
            '/product/whoAmI',           # Get current user info (WORKING)
            '/product/api',              # Get API info
            '/product/timezone',         # Get timezone
            
            # Device operations (require device ID)
            # '/devices/{deviceId}',       # Individual device operations
            # '/devices/{deviceId}/status', # Device status
            # '/devices/{deviceId}/properties', # Device properties
        ]
        
        for pattern in test_patterns:
            endpoint_url = f"{self.base_url}{pattern}"
            try:
                logger.debug(f"Testing endpoint: {endpoint_url}")
                response = self.session.get(endpoint_url, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✓ Found working endpoint: {pattern}")
                    endpoints[pattern] = {
                        'url': endpoint_url,
                        'status_code': response.status_code,
                        'content_type': response.headers.get('content-type', 'unknown')
                    }
                    
                    # Try to peek at the response structure
                    try:
                        json_data = response.json()
                        if isinstance(json_data, dict):
                            if 'data' in json_data:
                                logger.debug(f"  Response has 'data' envelope")
                                data = json_data['data']
                                if isinstance(data, list):
                                    logger.debug(f"  Data is list with {len(data)} items")
                                elif isinstance(data, dict):
                                    logger.debug(f"  Data is dict with keys: {list(data.keys())}")
                            if 'paging' in json_data:
                                logger.debug(f"  Response supports paging")
                    except:
                        pass
                        
                elif response.status_code == 401:
                    logger.warning(f"✗ Authentication required for: {pattern}")
                elif response.status_code == 403:
                    logger.warning(f"✗ Access forbidden for: {pattern}")
                elif response.status_code == 404:
                    logger.debug(f"✗ Not found: {pattern}")
                else:
                    logger.debug(f"✗ Unexpected status {response.status_code} for: {pattern}")
                    
            except requests.exceptions.Timeout:
                logger.debug(f"✗ Timeout for endpoint: {pattern}")
            except requests.exceptions.RequestException as e:
                logger.debug(f"✗ Request error for {pattern}: {e}")
                
        if endpoints:
            logger.info(f"Found {len(endpoints)} working API endpoints")
            for endpoint, info in endpoints.items():
                logger.info(f"  {endpoint}: {info['status_code']} ({info['content_type']})")
        else:
            logger.warning("No working API endpoints found")
            
        return endpoints

    def create_device(self, display_name: str, ip_address: str, hostname: str = None, 
                     device_type: str = "Network Device", primary_role: str = "Device",
                     poll_interval: int = 60, group_name: str = None) -> Dict:
        """
        Create a new device in WhatsUp Gold
        
        Args:
            display_name: Display name for the device
            ip_address: IP address of the device
            hostname: Hostname (optional, defaults to display_name)
            device_type: Device type (optional)
            primary_role: Primary role (optional)
            poll_interval: Polling interval in seconds (optional)
            group_name: WUG group/location name (optional, maps to NetBox Site)
            
        Returns:
            Dictionary with creation result including device ID
            
        Raises:
            WUGAPIException: For API errors
        """
        try:
            logger.info(f"Creating device '{display_name}' with IP {ip_address} in group '{group_name or 'My Network'}'")
            
            # Use display_name as hostname if not provided
            if hostname is None:
                hostname = display_name
            
            # Prepare groups array - groups should be objects with 'name' key
            groups = []
            
            if group_name:
                # Verify group exists
                all_groups = self.get_device_groups()
                matching_group = next((g for g in all_groups if g.get('name') == group_name), None)
                
                if matching_group:
                    # Groups need to be specified as objects with 'name' key
                    groups.append({"name": group_name})
                    logger.info(f"Adding device to WUG group '{group_name}'")
                else:
                    logger.warning(f"Group '{group_name}' not found in WUG, device will be created without group assignment")
            
            # Create device template
            device_template = {
                "displayName": display_name,
                "deviceType": device_type,
                "primaryRole": primary_role,
                "pollIntervalSeconds": poll_interval,
                "interfaces": [
                    {
                        "defaultInterface": True,
                        "pollUsingNetworkName": False,
                        "networkAddress": ip_address,
                        "networkName": hostname
                    }
                ],
                "attributes": [],
                "customLinks": [],
                "activeMonitors": [
                    {
                        "classId": "",
                        "Name": "Ping"
                    }
                ],
                "performanceMonitors": [],
                "passiveMonitors": [],
                "dependencies": [],
                "ncmTasks": [],
                "applicationProfiles": [],
                "layer2Data": "",
                "groups": groups
            }
            
            # Create request body with correct structure
            body = {
                "options": ["all"],
                "templates": [device_template]
            }
            
            # Make PATCH request to create device
            logger.debug(f"Device creation payload: {body}")
            response = self._make_request('PATCH', '/devices/-/config/template', data=body)
            logger.info(f"===== FULL API RESPONSE =====")
            logger.info(f"Response type: {type(response)}")
            logger.info(f"Response: {json.dumps(response, indent=2)}")
            logger.info(f"============================")
            
            if response and 'data' in response:
                data = response['data']
                
                # Check for errors
                if 'errors' in data and data['errors']:
                    errors = data['errors']
                    logger.warning(f"Device creation had warnings: {errors}")
                
                # Get device ID from response
                if 'idMap' in data and data['idMap']:
                    device_id = data['idMap'][0].get('resultId')
                    template_id = data['idMap'][0].get('templateId')
                    
                    logger.info(f"Successfully created device '{display_name}' with ID {device_id}")
                    
                    return {
                        'success': True,
                        'device_id': device_id,
                        'template_id': template_id,
                        'display_name': display_name,
                        'ip_address': ip_address,
                        'hostname': hostname,
                        'errors': data.get('errors', [])
                    }
                else:
                    logger.error(f"Device creation response missing device ID or idMap. Full data keys: {list(data.keys())}")
                    logger.error(f"Full data: {json.dumps(data, indent=2)}")
                    return {
                        'success': False,
                        'message': 'Device creation response missing device ID',
                        'response_data': data
                    }
            else:
                logger.error(f"Invalid device creation response (no 'data' key): {response}")
                return {
                    'success': False,
                    'message': 'Invalid API response format'
                }
                
        except Exception as e:
            logger.error(f"Failed to create device '{display_name}': {e}")
            return {
                'success': False,
                'message': f'Device creation failed: {str(e)}'
            }


# Utility functions for data transformation
def normalize_wug_device_data(wug_device: Dict) -> Dict:
    """
    Normalize WhatsUp Gold device data to a standard format
    
    Args:
        wug_device: Raw device data from WUG API
        
    Returns:
        Normalized device data dictionary
    """
    # Map actual WUG field names to standardized names based on API response
    field_mapping = {
        'id': 'id',
        'name': 'name',
        'hostName': 'hostname',
        'networkAddress': 'ip_address',  # This is where IP addresses are stored
        'role': 'device_type',
        'brand': 'vendor',
        'os': 'os_version',
        'bestState': 'status',
        'worstState': 'worst_status',
        'description': 'description',
        'notes': 'notes',
        'group_name': 'group',
        # Legacy mappings for other possible field names
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
            value = wug_device[wug_field]
            # Only set non-empty values
            if value is not None and value != '':
                normalized[std_field] = value
    
    # Extract brand/model information if available
    if 'brand' in wug_device and wug_device['brand']:
        normalized['vendor'] = wug_device['brand']
        # Use role as model if no specific model is available
        if 'role' in wug_device and wug_device['role'] not in ['Device', 'Unknown']:
            normalized['model'] = wug_device['role']
    
    # Map status values
    if 'status' in normalized:
        status_lower = str(normalized['status']).lower()
        if status_lower in ['up', 'online', 'active']:
            normalized['status'] = 'up'
        elif status_lower in ['down', 'offline', 'inactive']:
            normalized['status'] = 'down'
        else:
            normalized['status'] = 'unknown'
    
    # Ensure we have an ID
    if 'id' not in normalized and 'id' in wug_device:
        normalized['id'] = str(wug_device['id'])
    
    # Ensure we have a name
    if 'name' not in normalized:
        if 'hostname' in normalized:
            normalized['name'] = normalized['hostname']
        elif 'ip_address' in normalized:
            normalized['name'] = normalized['ip_address']
        else:
            normalized['name'] = f"device-{normalized.get('id', 'unknown')}"
    
    # Keep original data for reference
    normalized['raw_data'] = wug_device
    
    # Parse timestamps if any
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