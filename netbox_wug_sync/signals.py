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
from .sync_utils import create_wug_device_from_netbox_data

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
    try:
        logger.debug(f"Device signal triggered for {getattr(instance, 'name', 'unknown')} - created: {created}")
        
        # Additional safety: ensure instance is a proper Device object
        if not instance or not hasattr(instance, 'name'):
            logger.debug("Signal triggered with invalid device instance")
            return
            
        # Check if device has primary IP and it's not None
        if not hasattr(instance, 'primary_ip4') or not instance.primary_ip4:
            logger.debug(f"Device {instance.name} has no primary IPv4 address, skipping WUG sync")
            return
        
        # Additional safety check for the address property
        if not hasattr(instance.primary_ip4, 'address') or not instance.primary_ip4.address:
            logger.debug(f"Device {instance.name} primary IP has no address property, skipping WUG sync")
            return

        # Additional safety for status attribute
        if not hasattr(instance, 'status'):
            logger.debug(f"Device {instance.name} has no status attribute, skipping WUG sync")
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
        
        # Get the primary IP address with additional safety
        primary_ip = str(instance.primary_ip4.address).split('/')[0]  # Remove CIDR notation
        
        # Sync to all active WUG connections
        for connection in connections:
            try:
                # Use the new reverse sync functionality
                result = create_wug_device_from_netbox_data(instance, connection)
                
                if result['success']:
                    logger.info(f"Successfully synced device {instance.name} to WUG connection {connection.name} (Device ID: {result.get('device_id', 'unknown')})")
                    
                    # Create sync log entry
                    WUGSyncLog.objects.create(
                        connection=connection,
                        sync_type='netbox_to_wug',
                        status='completed',
                        start_time=timezone.now(),
                        end_time=timezone.now(),
                        devices_discovered=1,
                        devices_created=1 if created else 0,
                        devices_updated=0 if created else 1,
                        devices_errors=0,
                        summary=f"NetBox device {instance.name} {'created' if created else 'updated'} in WUG via signal - Device ID: {result.get('device_id', 'unknown')}"
                    )
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"Failed to sync device {instance.name} to WUG connection {connection.name}: {error_msg}")
                    
                    # Create error sync log entry
                    WUGSyncLog.objects.create(
                        connection=connection,
                        sync_type='netbox_to_wug',
                        status='failed',
                        start_time=timezone.now(),
                        end_time=timezone.now(),
                        devices_discovered=1,
                        devices_created=0,
                        devices_updated=0,
                        devices_errors=1,
                        summary=f"Failed to sync NetBox device {instance.name} to WUG: {error_msg}"
                    )
            except Exception as e:
                logger.error(f"Failed to sync device {instance.name} to WUG connection {connection.name}: {str(e)}")
                
                # Create error sync log entry
                WUGSyncLog.objects.create(
                    connection=connection,
                    sync_type='netbox_to_wug',
                    status='error',
                    start_time=timezone.now(),
                    end_time=timezone.now(),
                    devices_discovered=1,
                    devices_created=0,
                    devices_updated=0,
                    devices_errors=1,
                    summary=f"Exception while syncing NetBox device {instance.name} to WUG: {str(e)}"
                )
    
    except Exception as e:
        # Top-level exception handler to prevent signal errors from breaking NetBox
        logger.error(f"Critical error in device_saved_handler for device {getattr(instance, 'name', 'unknown')}: {str(e)}")
        # Don't re-raise the exception to prevent breaking NetBox functionality


@receiver(post_delete, sender=Device)
def device_deleted_handler(sender, instance, **kwargs):
    """
    Handle Device deletion to remove from WhatsUp Gold
    
    Removes device from WUG when deleted from NetBox if it was previously synced.
    """
    try:
        logger.debug(f"Device deletion signal triggered for {getattr(instance, 'name', 'unknown')}")
        
        # Temporary: Just log and return to isolate the issue
        return
        
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
                logger.error(f"Failed to remove WUG device {wug_device.device_name}: {str(e)}")
    
    except Exception as e:
        # Top-level exception handler to prevent signal errors from breaking NetBox
        logger.error(f"Critical error in device_deleted_handler for device {getattr(instance, 'name', 'unknown')}: {str(e)}")
        # Don't re-raise the exception to prevent breaking NetBox functionality


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