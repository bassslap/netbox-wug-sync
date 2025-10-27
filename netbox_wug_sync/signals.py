"""
Signal handlers for NetBox to WhatsUp Gold device synchronization

This module handles Django signals to automatically add devices to WhatsUp Gold
when they are created or updated in NetBox with specific criteria.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from dcim.models import Device
from dcim.choices import DeviceStatusChoices
from ipam.models import IPAddress

from .models import WUGConnection, WUGDevice, WUGSyncLog
from .wug_client import WUGAPIClient

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Device)
def device_saved_handler(sender, instance, created, **kwargs):
    """
    Handle Device creation/update to sync with WhatsUp Gold
    
    Automatically adds device to WUG if:
    - Device has an IPv4 primary address
    - Device status is 'active'
    - There are active WUG connections configured
    """
    if not instance.primary_ip4:
        logger.debug(f"Device {instance.name} has no primary IPv4 address, skipping WUG sync")
        return
    
    if instance.status != DeviceStatusChoices.STATUS_ACTIVE:
        logger.debug(f"Device {instance.name} is not active (status: {instance.status}), skipping WUG sync")
        return
    
    # Get active WUG connections
    connections = WUGConnection.objects.filter(is_active=True)
    if not connections.exists():
        logger.debug("No active WUG connections found, skipping device sync")
        return
    
    logger.info(f"NetBox device {'created' if created else 'updated'}: {instance.name}, syncing to WUG")
    
    # Get the primary IP address
    primary_ip = str(instance.primary_ip4.address).split('/')[0]  # Remove CIDR notation
    
    # Sync to all active WUG connections
    for connection in connections:
        try:
            sync_device_to_wug(instance, connection, primary_ip, created)
        except Exception as e:
            logger.error(f"Failed to sync device {instance.name} to WUG connection {connection.name}: {str(e)}")


@receiver(post_delete, sender=Device)
def device_deleted_handler(sender, instance, **kwargs):
    """
    Handle Device deletion to remove from WhatsUp Gold
    
    Removes device from WUG when deleted from NetBox if it was previously synced.
    """
    # Find any WUG devices that were synced from this NetBox device
    wug_devices = WUGDevice.objects.filter(netbox_device_id=instance.id)
    
    if not wug_devices.exists():
        logger.debug(f"No WUG devices found for deleted NetBox device {instance.name}")
        return
    
    logger.info(f"NetBox device deleted: {instance.name}, removing from WUG")
    
    for wug_device in wug_devices:
        try:
            remove_device_from_wug(wug_device)
        except Exception as e:
            logger.error(f"Failed to remove device {instance.name} from WUG: {str(e)}")


def sync_device_to_wug(netbox_device, wug_connection, ip_address, is_new_device=True):
    """
    Sync a NetBox device to WhatsUp Gold
    
    Args:
        netbox_device: NetBox Device instance
        wug_connection: WUGConnection instance
        ip_address: Primary IP address of the device
        is_new_device: Whether this is a new device creation
    """
    # Check if device already exists in WUG for this connection
    existing_wug_device = WUGDevice.objects.filter(
        connection=wug_connection,
        netbox_device_id=netbox_device.id
    ).first()
    
    if existing_wug_device and not is_new_device:
        logger.debug(f"Device {netbox_device.name} already exists in WUG connection {wug_connection.name}, updating")
        action = "update"
    else:
        logger.info(f"Adding new device {netbox_device.name} to WUG connection {wug_connection.name}")
        action = "create"
    
    # Prepare device data for WUG
    device_data = {
        'ipAddress': ip_address,
        'displayName': netbox_device.name,
        'description': f"Device synced from NetBox - {netbox_device.device_type.model if netbox_device.device_type else 'Unknown'}",
        'location': netbox_device.site.name if netbox_device.site else 'Unknown',
        'contact': netbox_device.comments or '',
        'community': 'public',  # Default SNMP community
        'snmpVersion': '2c',    # Default SNMP version
        'enableMonitoring': True
    }
    
    # Add additional metadata
    if netbox_device.role:
        device_data['role'] = netbox_device.role.name
    
    if netbox_device.platform:
        device_data['platform'] = netbox_device.platform.name
    
    try:
        # Create WUG API client
        with WUGAPIClient(
            host=wug_connection.host,
            username=wug_connection.username,
            password=wug_connection.password,  # Fix: Use password field directly
            port=wug_connection.port,
            use_ssl=wug_connection.use_ssl,
            verify_ssl=wug_connection.verify_ssl
        ) as client:
            
            # Add device to WUG
            result = client.add_device_by_ip(ip_address, device_data)
            
            if result.get('success', False):
                wug_device_id = result.get('deviceId') or result.get('id')
                
                # Create or update WUGDevice record
                if existing_wug_device:
                    existing_wug_device.wug_device_id = wug_device_id
                    existing_wug_device.last_sync = timezone.now()
                    existing_wug_device.sync_status = 'success'
                    existing_wug_device.save()
                    wug_device = existing_wug_device
                else:
                    wug_device = WUGDevice.objects.create(
                        connection=wug_connection,
                        wug_device_id=wug_device_id,
                        netbox_device_id=netbox_device.id,
                        device_name=netbox_device.name,
                        ip_address=ip_address,
                        sync_status='success'
                    )
                
                logger.info(f"Successfully {action}d device {netbox_device.name} in WUG (ID: {wug_device_id})")
                
                # Trigger scan for the newly added device
                if action == "create":
                    logger.info(f"Triggering scan for newly added device {netbox_device.name} at {ip_address}")
                    try:
                        scan_result = client.scan_ip_address(ip_address)
                        if scan_result.get('success', False):
                            logger.info(f"Successfully triggered scan for device {netbox_device.name}")
                            
                            # Check for IP conflicts during the scan
                            check_ip_conflicts_after_scan(ip_address, netbox_device, wug_connection, client)
                        else:
                            scan_error = scan_result.get('message', 'Unknown scan error')
                            logger.warning(f"Failed to trigger scan for device {netbox_device.name}: {scan_error}")
                    except Exception as scan_e:
                        logger.warning(f"Exception while scanning device {netbox_device.name}: {str(scan_e)}")
                
                # Create sync log entry
                WUGSyncLog.objects.create(
                    connection=wug_connection,
                    sync_type='netbox_to_wug',
                    status='completed',
                    start_time=timezone.now(),
                    end_time=timezone.now(),
                    devices_discovered=1,
                    devices_created=1 if action == "create" else 0,
                    devices_updated=1 if action == "update" else 0,
                    devices_errors=0,
                    summary=f"NetBox device {netbox_device.name} {action}d in WUG via signal"
                )
                
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Failed to {action} device {netbox_device.name} in WUG: {error_msg}")
                
                # Update existing record or create failed record
                if existing_wug_device:
                    existing_wug_device.sync_status = 'failed'
                    existing_wug_device.error_message = error_msg
                    existing_wug_device.save()
                
                # Create error sync log entry
                WUGSyncLog.objects.create(
                    connection=wug_connection,
                    sync_type='netbox_to_wug',
                    status='failed',
                    start_time=timezone.now(),
                    end_time=timezone.now(),
                    devices_discovered=1,
                    devices_created=0,
                    devices_updated=0,
                    devices_errors=1,
                    summary=f"Failed to {action} NetBox device {netbox_device.name} in WUG: {error_msg}"
                )
                
    except Exception as e:
        logger.error(f"Exception while syncing device {netbox_device.name} to WUG: {str(e)}")
        
        # Create error sync log entry
        WUGSyncLog.objects.create(
            connection=wug_connection,
            sync_type='netbox_to_wug',
            status='error',
            start_time=timezone.now(),
            end_time=timezone.now(),
            devices_discovered=1,
            devices_created=0,
            devices_updated=0,
            devices_errors=1,
            summary=f"Exception while syncing NetBox device {netbox_device.name} to WUG: {str(e)}"
        )


def remove_device_from_wug(wug_device):
    """
    Remove a device from WhatsUp Gold
    
    Args:
        wug_device: WUGDevice instance to remove
    """
    try:
        with WUGAPIClient(
            host=wug_device.connection.host,
            username=wug_device.connection.username,
            password=wug_device.connection.password,  # Fix: Use password field directly
            port=wug_device.connection.port,
            use_ssl=wug_device.connection.use_ssl,
            verify_ssl=wug_device.connection.verify_ssl
        ) as client:
            
            # Remove device from WUG
            result = client.delete_device(wug_device.wug_device_id)
            
            if result.get('success', False):
                logger.info(f"Successfully removed device {wug_device.device_name} from WUG")
                
                # Create sync log entry
                WUGSyncLog.objects.create(
                    connection=wug_device.connection,
                    sync_type='netbox_to_wug',
                    status='completed',
                    start_time=timezone.now(),
                    end_time=timezone.now(),
                    devices_discovered=1,
                    devices_created=0,
                    devices_updated=0,
                    devices_errors=0,
                    summary=f"NetBox device {wug_device.device_name} removed from WUG"
                )
                
                # Delete the WUGDevice record
                wug_device.delete()
                
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Failed to remove device {wug_device.device_name} from WUG: {error_msg}")
                
    except Exception as e:
        logger.error(f"Exception while removing device {wug_device.device_name} from WUG: {str(e)}")


def check_ip_conflicts_after_scan(ip_address, netbox_device, wug_connection, wug_client):
    """
    Check for IP conflicts after a device scan
    
    This function looks for other devices in both NetBox and WUG that have the same
    IP address and creates appropriate warnings.
    
    Args:
        ip_address: IP address to check for conflicts
        netbox_device: The NetBox device that was just added
        wug_connection: WUG connection instance 
        wug_client: Authenticated WUG API client instance
    """
    conflicts_found = []
    
    try:
        # Check for conflicts in NetBox first
        conflicting_netbox_devices = Device.objects.filter(
            primary_ip4__address__startswith=ip_address
        ).exclude(id=netbox_device.id)
        
        for conflict_device in conflicting_netbox_devices:
            conflicts_found.append({
                'type': 'netbox',
                'device_name': conflict_device.name,
                'device_id': conflict_device.id,
                'ip_address': str(conflict_device.primary_ip4.address).split('/')[0],
                'location': conflict_device.site.name if conflict_device.site else 'Unknown'
            })
        
        # Check for conflicts in WUG by getting all devices and comparing IPs
        try:
            wug_devices = wug_client.get_devices()
            if wug_devices.get('success', False):
                device_list = wug_devices.get('devices', [])
                
                for wug_device in device_list:
                    device_ip = wug_device.get('ipAddress') or wug_device.get('networkAddress')
                    device_name = wug_device.get('displayName') or wug_device.get('name', 'Unknown')
                    device_id = wug_device.get('id') or wug_device.get('deviceId')
                    
                    if device_ip == ip_address:
                        # Check if this is not the device we just added
                        our_wug_device = WUGDevice.objects.filter(
                            connection=wug_connection,
                            netbox_device_id=netbox_device.id
                        ).first()
                        
                        if not our_wug_device or str(our_wug_device.wug_device_id) != str(device_id):
                            conflicts_found.append({
                                'type': 'wug',
                                'device_name': device_name,
                                'device_id': device_id,
                                'ip_address': device_ip,
                                'location': wug_device.get('location', 'Unknown')
                            })
        except Exception as wug_e:
            logger.warning(f"Could not check WUG for IP conflicts: {str(wug_e)}")
        
        # Log warnings for any conflicts found
        if conflicts_found:
            conflict_summary = []
            for conflict in conflicts_found:
                conflict_summary.append(
                    f"{conflict['type'].upper()}: {conflict['device_name']} "
                    f"(ID: {conflict['device_id']}, Location: {conflict['location']})"
                )
            
            warning_message = (
                f"⚠️  IP CONFLICT DETECTED for {ip_address}! "
                f"Device {netbox_device.name} shares this IP with: {'; '.join(conflict_summary)}"
            )
            
            logger.warning(warning_message)
            
            # Create a sync log entry to record the conflict
            WUGSyncLog.objects.create(
                connection=wug_connection,
                sync_type='ip_conflict_check',
                status='warning',
                start_time=timezone.now(),
                end_time=timezone.now(),
                devices_discovered=len(conflicts_found) + 1,  # Include the original device
                devices_created=0,
                devices_updated=0,
                devices_errors=0,
                summary=warning_message
            )
            
        else:
            logger.info(f"✅ No IP conflicts detected for {ip_address}")
            
    except Exception as e:
        logger.error(f"Exception while checking IP conflicts for {ip_address}: {str(e)}")