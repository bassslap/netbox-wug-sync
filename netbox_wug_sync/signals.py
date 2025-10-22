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
    
    if instance.status != 'active':
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
    if netbox_device.device_role:
        device_data['role'] = netbox_device.device_role.name
    
    if netbox_device.platform:
        device_data['platform'] = netbox_device.platform.name
    
    try:
        # Create WUG API client
        with WUGAPIClient(
            host=wug_connection.host,
            username=wug_connection.username,
            password=wug_connection.get_password(),
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
                
                # Create sync log entry
                WUGSyncLog.objects.create(
                    connection=wug_connection,
                    sync_type='netbox_to_wug',
                    status='completed',
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
            password=wug_device.connection.get_password(),
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