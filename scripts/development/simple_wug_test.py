#!/usr/bin/env python3
"""
Simple test script to verify WhatsUp Gold API functionality
"""

import sys
import os
import json
import logging
import requests
import urllib3
from datetime import datetime, timedelta
from typing import List, Dict, Union
from urllib.parse import urljoin, urlparse

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WUGAPIException(Exception):
    """Base exception for WhatsUp Gold API errors"""
    pass

class WUGAuthenticationError(WUGAPIException):
    """Authentication-related API errors"""
    pass

class SimpleWUGClient:
    """Simplified WhatsUp Gold API client for testing"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 9644, 
                 use_ssl: bool = True, verify_ssl: bool = False):
        """Initialize the WUG API client"""
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        
        # Build base URL
        protocol = 'https' if use_ssl else 'http'
        self.base_url = f"{protocol}://{self.host}:{self.port}/api/v1"
        
        # Session for connection reuse
        self.session = requests.Session()
        self.session.verify = verify_ssl
        
        # Authentication token
        self._token = None
        self._token_expires = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            self.session.close()
    
    def _authenticate(self):
        """Authenticate with WhatsUp Gold API using OAuth 2.0"""
        token_url = f"{self.base_url}/token"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        }
        
        data = f"grant_type=password&username={self.username}&password={self.password}"
        
        try:
            response = self.session.post(token_url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                self._token = token_data.get('access_token')
                
                # Calculate token expiry
                expires_in = token_data.get('expires_in', 3600)  # Default 1 hour
                self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)  # 60s buffer
                
                logger.info("Successfully authenticated with WhatsUp Gold API")
                return True
            else:
                raise WUGAuthenticationError(f"Authentication failed: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise WUGAuthenticationError(f"Authentication request failed: {str(e)}")
    
    def _is_token_expired(self) -> bool:
        """Check if the current token is expired"""
        return self._token_expires is None or datetime.now() >= self._token_expires
    
    def _ensure_authenticated(self):
        """Ensure we have a valid authentication token"""
        if self._token is None or self._is_token_expired():
            self._authenticate()
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, 
                     params: Dict = None) -> Dict:
        """Make HTTP request to WUG API"""
        # Build full URL - endpoint should start with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        url = self.base_url + endpoint
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Add authentication
        self._ensure_authenticated()
        headers['Authorization'] = f'Bearer {self._token}'
        
        # Prepare request data
        request_kwargs = {
            'headers': headers,
            'timeout': 30
        }
        
        if data:
            request_kwargs['json'] = data
        if params:
            request_kwargs['params'] = params
        
        try:
            response = self.session.request(method, url, **request_kwargs)
            
            if response.status_code in [200, 201]:
                try:
                    return response.json()
                except ValueError:
                    return {'status': 'success', 'response': response.text}
            elif response.status_code == 401:
                # Token might be expired, try re-authentication once
                logger.warning("Received 401, attempting re-authentication...")
                self._token = None
                self._ensure_authenticated()
                headers['Authorization'] = f'Bearer {self._token}'
                request_kwargs['headers'] = headers
                
                response = self.session.request(method, url, **request_kwargs)
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    raise WUGAuthenticationError(f"Re-authentication failed: {response.status_code}")
            else:
                error_msg = f"API request failed: {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg = f"{error_msg} - {error_data['error'].get('message', 'Unknown error')}"
                except:
                    error_msg = f"{error_msg} - {response.text}"
                
                raise WUGAPIException(error_msg)
                
        except requests.exceptions.RequestException as e:
            raise WUGAPIException(f"Request failed: {str(e)}")
    
    def test_connection(self) -> Dict:
        """Test connection to WhatsUp Gold API"""
        try:
            response = self._make_request('GET', '/product/version')
            return {
                'success': True,
                'message': 'Connection successful',
                'version_info': response
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
    
    def get_device_groups(self) -> List[Dict]:
        """Get all device groups"""
        response = self._make_request('GET', '/device-groups/-')
        
        if isinstance(response, dict) and 'data' in response:
            groups_data = response['data']
            return groups_data.get('groups', [])
        
        return []
    
    def get_devices_from_group(self, group_id: str) -> List[Dict]:
        """Get devices from a specific group"""
        response = self._make_request('GET', f'/device-groups/{group_id}/devices')
        
        if isinstance(response, dict) and 'data' in response:
            devices_data = response['data']
            return devices_data.get('devices', [])
        
        return []
    
    def get_all_devices(self) -> List[Dict]:
        """Get all devices from all groups"""
        all_devices = []
        device_ids_seen = set()
        
        groups = self.get_device_groups()
        logger.info(f"Found {len(groups)} device groups")
        
        for group in groups:
            group_id = group.get('id')
            group_name = group.get('name', 'Unknown')
            
            if not group_id:
                continue
            
            try:
                devices = self.get_devices_from_group(group_id)
                logger.info(f"Group '{group_name}': {len(devices)} devices")
                
                for device in devices:
                    device_id = device.get('id')
                    if device_id and device_id not in device_ids_seen:
                        device['group_id'] = group_id
                        device['group_name'] = group_name
                        all_devices.append(device)
                        device_ids_seen.add(device_id)
                        
            except Exception as e:
                logger.warning(f"Failed to get devices from group {group_name}: {e}")
        
        return all_devices

def test_basic_connection():
    """Test basic connection and authentication"""
    logger.info("Testing basic connection...")
    
    try:
        with SimpleWUGClient(
            host="192.168.221.91",
            username="automate",
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            result = client.test_connection()
            logger.info(f"Connection test: {result}")
            return result['success']
            
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

def test_device_discovery():
    """Test device discovery functionality"""
    logger.info("Testing device discovery...")
    
    try:
        with SimpleWUGClient(
            host="192.168.221.91",
            username="automate",
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            # Get all devices
            devices = client.get_all_devices()
            logger.info(f"Found {len(devices)} total devices")
            
            # Show device details
            for i, device in enumerate(devices[:5]):  # Show first 5 devices
                device_id = device.get('id')
                device_name = device.get('name', 'Unknown')
                device_ip = device.get('networkAddress', 'No IP')
                group_name = device.get('group_name', 'Unknown group')
                device_role = device.get('role', 'Unknown role')
                device_state = device.get('bestState', 'Unknown state')
                
                logger.info(f"Device {i+1}: {device_name}")
                logger.info(f"  ID: {device_id}")
                logger.info(f"  IP: {device_ip}")
                logger.info(f"  Group: {group_name}")
                logger.info(f"  Role: {device_role}")
                logger.info(f"  State: {device_state}")
                logger.info(f"  Properties: {list(device.keys())}")
                logger.info("")
            
            return len(devices) > 0
            
    except Exception as e:
        logger.error(f"Device discovery test failed: {e}")
        return False

def test_device_groups():
    """Test device group functionality"""
    logger.info("Testing device groups...")
    
    try:
        with SimpleWUGClient(
            host="192.168.221.91",
            username="automate",
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            groups = client.get_device_groups()
            logger.info(f"Found {len(groups)} device groups:")
            
            for i, group in enumerate(groups[:10]):  # Show first 10 groups
                group_id = group.get('id')
                group_name = group.get('name', 'Unknown')
                group_type = group.get('groupType', 'Unknown')
                parent_id = group.get('parentGroupId', 'None')
                
                logger.info(f"  {i+1}. {group_name} (ID: {group_id})")
                logger.info(f"     Type: {group_type}, Parent: {parent_id}")
            
            return len(groups) > 0
            
    except Exception as e:
        logger.error(f"Device groups test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting WhatsUp Gold API tests...")
    
    tests = [
        ("Basic Connection", test_basic_connection),
        ("Device Groups", test_device_groups),
        ("Device Discovery", test_device_discovery)
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            result = test_func()
            results[test_name] = result
            status = "PASSED" if result else "FAILED"
            logger.info(f"Test '{test_name}': {status}")
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("Test Summary:")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! WhatsUp Gold API integration is working!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())