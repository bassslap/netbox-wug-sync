#!/usr/bin/env python3
"""
Test script to verify the updated WhatsUp Gold client functionality
"""

import sys
import os
import json
import logging
from typing import List, Dict

# Add the netbox_wug_sync package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netbox_wug_sync.wug_client import WUGAPIClient, WUGAPIException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_wug_connection():
    """Test basic WhatsUp Gold connection and authentication"""
    logger.info("Testing WhatsUp Gold connection...")
    
    try:
        with WUGAPIClient(
            host="192.168.221.91",
            username="automate", 
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            # Test connection
            logger.info("Testing connection...")
            connection_result = client.test_connection()
            logger.info(f"Connection test result: {connection_result}")
            
            # Discover endpoints
            logger.info("Discovering API endpoints...")
            endpoints = client.discover_endpoints()
            logger.info(f"Discovered {len(endpoints)} endpoints")
            
            # Get devices
            logger.info("Getting devices...")
            devices = client.get_devices(include_details=False)
            logger.info(f"Found {len(devices)} devices")
            
            # Show device details
            for i, device in enumerate(devices[:3]):  # Show first 3 devices
                device_id = device.get('id')
                device_name = device.get('name', 'Unknown')
                device_ip = device.get('networkAddress', 'No IP')
                group_name = device.get('group_name', 'Unknown group')
                
                logger.info(f"Device {i+1}: {device_name} (ID: {device_id})")
                logger.info(f"  IP: {device_ip}")
                logger.info(f"  Group: {group_name}")
                logger.info(f"  Keys: {list(device.keys())}")
            
            return True
            
    except WUGAPIException as e:
        logger.error(f"WUG API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def test_device_details():
    """Test getting detailed device information"""
    logger.info("Testing device details...")
    
    try:
        with WUGAPIClient(
            host="192.168.221.91",
            username="automate", 
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            # Get devices with details
            devices = client.get_devices(include_details=True)
            logger.info(f"Found {len(devices)} devices with details")
            
            if devices:
                # Show detailed info for first device
                device = devices[0]
                logger.info(f"Detailed device info for: {device.get('name', 'Unknown')}")
                
                # Show all available keys
                keys = list(device.keys())
                logger.info(f"Available device properties: {keys}")
                
                # Show specific important properties
                important_props = ['id', 'name', 'networkAddress', 'hostName', 'role', 'brand', 'os', 'bestState', 'worstState']
                for prop in important_props:
                    if prop in device:
                        logger.info(f"  {prop}: {device[prop]}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error testing device details: {e}")
        return False

def test_device_groups():
    """Test device group functionality"""
    logger.info("Testing device groups...")
    
    try:
        with WUGAPIClient(
            host="192.168.221.91",
            username="automate", 
            password="automate",
            port=9644,
            use_ssl=True,
            verify_ssl=False
        ) as client:
            
            # Get device groups directly
            groups_response = client._make_request('GET', '/device-groups/-')
            logger.info(f"Device groups response keys: {list(groups_response.keys())}")
            
            if 'data' in groups_response:
                groups_data = groups_response['data']
                groups = groups_data.get('groups', [])
                
                logger.info(f"Found {len(groups)} device groups:")
                for group in groups[:5]:  # Show first 5 groups
                    group_id = group.get('id')
                    group_name = group.get('name', 'Unknown')
                    group_type = group.get('groupType', 'Unknown')
                    logger.info(f"  Group: {group_name} (ID: {group_id}, Type: {group_type})")
            
            return True
            
    except Exception as e:
        logger.error(f"Error testing device groups: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting WhatsUp Gold client tests...")
    
    tests = [
        test_wug_connection,
        test_device_details,
        test_device_groups
    ]
    
    results = {}
    for test_func in tests:
        test_name = test_func.__name__
        logger.info(f"\n{'='*50}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = test_func()
            results[test_name] = result
            logger.info(f"Test {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("Test Summary:")
    logger.info(f"{'='*50}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! WhatsUp Gold integration is working!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())