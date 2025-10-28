"""
Sync Utilities for NetBox WhatsUp Gold Integration

This module contains utility functions for synchronizing data between
NetBox and WhatsUp Gold, including functions for finding or creating
NetBox objects like Sites, DeviceTypes, and DeviceRoles.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from dcim.models import Site, DeviceType, DeviceRole, Manufacturer, Device
from dcim.choices import DeviceStatusChoices
from extras.models import Tag


logger = logging.getLogger(__name__)


def find_or_create_site(site_name: str, site_slug: str = None) -> Site:
    """
    Find an existing NetBox site or create a new one
    
    Args:
        site_name: Site name (will be used as display name)
        site_slug: Optional site slug (will be generated from name if not provided)
        
    Returns:
        Site instance
    """
    if not site_slug:
        # Generate slug from name
        site_slug = site_name.lower().replace(' ', '-').replace('_', '-')
        # Remove special characters
        site_slug = ''.join(c for c in site_slug if c.isalnum() or c == '-')
        # Remove consecutive dashes and trim
        while '--' in site_slug:
            site_slug = site_slug.replace('--', '-')
        site_slug = site_slug.strip('-')
        
        # Ensure slug is not empty
        if not site_slug:
            site_slug = 'unknown-site'
    
    # Try to find existing site
    try:
        site = Site.objects.get(slug=site_slug)
        logger.debug(f"Found existing site: {site.name}")
        return site
    except Site.DoesNotExist:
        pass
    
    # Create new site
    site = Site.objects.create(
        name=site_name,
        slug=site_slug,
        description=f"Auto-created from WhatsUp Gold group: {site_name}"
    )
    
    logger.info(f"Created new site: {site.name} ({site.slug})")
    return site


def find_or_create_manufacturer(manufacturer_name: str) -> Manufacturer:
    """
    Find an existing manufacturer or create a new one
    
    Args:
        manufacturer_name: Manufacturer name
        
    Returns:
        Manufacturer instance
    """
    if not manufacturer_name or manufacturer_name.lower() in ['unknown', '']:
        manufacturer_name = 'Unknown'
    
    # Generate slug from name
    slug = manufacturer_name.lower().replace(' ', '-').replace('_', '-')
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    
    if not slug:
        slug = 'unknown'
    
    # Try to find existing manufacturer
    try:
        manufacturer = Manufacturer.objects.get(slug=slug)
        logger.debug(f"Found existing manufacturer: {manufacturer.name}")
        return manufacturer
    except Manufacturer.DoesNotExist:
        pass
    
    # Create new manufacturer
    manufacturer = Manufacturer.objects.create(
        name=manufacturer_name,
        slug=slug,
        description=f"Auto-created from WhatsUp Gold device data"
    )
    
    logger.info(f"Created new manufacturer: {manufacturer.name} ({manufacturer.slug})")
    return manufacturer


def find_or_create_device_type(vendor: str, model: str) -> DeviceType:
    """
    Find an existing DeviceType or create a new one
    
    Args:
        vendor: Device vendor/manufacturer
        model: Device model
        
    Returns:
        DeviceType instance
    """
    if not model or model.lower() in ['unknown', '']:
        model = 'Unknown Model'
    
    # Find or create manufacturer
    manufacturer = find_or_create_manufacturer(vendor)
    
    # Generate slug for device type
    type_name = f"{manufacturer.name} {model}"
    slug = f"{manufacturer.slug}-{model.lower().replace(' ', '-').replace('_', '-')}"
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    
    if not slug:
        slug = f"{manufacturer.slug}-unknown"
    
    # Try to find existing device type
    try:
        device_type = DeviceType.objects.get(slug=slug)
        logger.debug(f"Found existing device type: {device_type.model}")
        return device_type
    except DeviceType.DoesNotExist:
        pass
    
    # Create new device type
    device_type = DeviceType.objects.create(
        manufacturer=manufacturer,
        model=model,
        slug=slug,
        description=f"Auto-created from WhatsUp Gold: {vendor} {model}",
        u_height=1,  # Default to 1U
        is_full_depth=False,
    )
    
    logger.info(f"Created new device type: {device_type.manufacturer.name} {device_type.model}")
    return device_type


def find_or_create_device_role(role_name: str) -> DeviceRole:
    """
    Find an existing DeviceRole or create a new one
    
    Args:
        role_name: Role name (e.g., 'server', 'switch', 'router')
        
    Returns:
        DeviceRole instance
    """
    if not role_name:
        role_name = 'server'  # Default role
    
    # Generate slug from name
    slug = role_name.lower().replace(' ', '-').replace('_', '-')
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    
    if not slug:
        slug = 'server'
    
    # Try to find existing role
    try:
        device_role = DeviceRole.objects.get(slug=slug)
        logger.debug(f"Found existing device role: {device_role.name}")
        return device_role
    except DeviceRole.DoesNotExist:
        pass
    
    # Create new device role
    device_role = DeviceRole.objects.create(
        name=role_name.title(),
        slug=slug,
        color='9e9e9e',  # Default gray color
        description=f"Auto-created device role from WhatsUp Gold sync"
    )
    
    logger.info(f"Created new device role: {device_role.name} ({device_role.slug})")
    return device_role


def create_or_update_netbox_device(wug_device, netbox_device_data: Dict) -> Tuple[Device, str]:
    """
    Create a new NetBox device or update an existing one
    
    Args:
        wug_device: WUGDevice instance
        netbox_device_data: Device data for NetBox
        
    Returns:
        Tuple of (Device instance, action) where action is 'created' or 'updated'
    """
    from .models import WUGDevice  # Import here to avoid circular imports
    
    # Check if device already exists in NetBox
    if wug_device.netbox_device:
        # Update existing device
        device = wug_device.netbox_device
        
        # Update device fields
        for field, value in netbox_device_data.items():
            if field == 'custom_fields':
                # Handle custom fields separately
                if hasattr(device, 'custom_field_data'):
                    device.custom_field_data.update(value)
                continue
                
            if hasattr(device, field) and value is not None:
                setattr(device, field, value)
        
        device.full_clean()
        device.save()
        
        logger.debug(f"Updated existing NetBox device: {device.name}")
        return device, 'updated'
    
    else:
        # Create new device
        device_name = netbox_device_data.get('name')
        
        # Check if a device with this name already exists
        existing_device = Device.objects.filter(name=device_name).first()
        if existing_device:
            # Use existing device and associate it
            wug_device.netbox_device = existing_device
            wug_device.save()
            
            logger.debug(f"Associated existing NetBox device: {existing_device.name}")
            return existing_device, 'updated'
        
        # Remove custom_fields from main data for device creation
        custom_fields = netbox_device_data.pop('custom_fields', {})
        
        # Create the device
        device = Device.objects.create(**netbox_device_data)
        
        # Set custom fields if any
        if custom_fields and hasattr(device, 'custom_field_data'):
            device.custom_field_data.update(custom_fields)
            device.save()
        
        device.full_clean()
        
        logger.info(f"Created new NetBox device: {device.name}")
        return device, 'created'


def map_wug_status_to_netbox(wug_status: str) -> str:
    """
    Map WhatsUp Gold device status to NetBox device status
    
    Args:
        wug_status: Status from WhatsUp Gold
        
    Returns:
        NetBox device status choice
    """
    status_mapping = {
        'up': DeviceStatusChoices.STATUS_ACTIVE,
        'down': DeviceStatusChoices.STATUS_FAILED,
        'unknown': DeviceStatusChoices.STATUS_OFFLINE,
        'maintenance': DeviceStatusChoices.STATUS_PLANNED,
        'disabled': DeviceStatusChoices.STATUS_DECOMMISSIONING,
    }
    
    if wug_status:
        wug_status_lower = wug_status.lower()
        return status_mapping.get(wug_status_lower, DeviceStatusChoices.STATUS_ACTIVE)
    
    return DeviceStatusChoices.STATUS_ACTIVE


def validate_device_data(device_data: Dict) -> Dict:
    """
    Validate and clean device data before creating/updating NetBox device
    
    Args:
        device_data: Device data dictionary
        
    Returns:
        Cleaned device data dictionary
    """
    cleaned_data = device_data.copy()
    
    # Ensure required fields are present
    if not cleaned_data.get('name'):
        raise ValueError("Device name is required")
    
    # Clean device name (NetBox has restrictions)
    name = cleaned_data['name']
    # Remove/replace invalid characters
    cleaned_name = ''.join(c if c.isalnum() or c in '.-_' else '-' for c in name)
    cleaned_name = cleaned_name.strip('.-_')
    
    if not cleaned_name:
        raise ValueError("Device name cannot be empty after cleaning")
    
    cleaned_data['name'] = cleaned_name
    
    # Ensure status is valid
    if 'status' not in cleaned_data:
        cleaned_data['status'] = DeviceStatusChoices.STATUS_ACTIVE
    
    return cleaned_data


def get_or_create_default_site() -> Site:
    """
    Get or create a default site for devices without a specific location
    
    Returns:
        Default Site instance
    """
    try:
        return Site.objects.get(slug='default')
    except Site.DoesNotExist:
        return Site.objects.create(
            name='Default',
            slug='default',
            description='Default site for devices without a specific location'
        )


def get_or_create_default_device_type() -> DeviceType:
    """
    Get or create a default device type for unknown devices
    
    Returns:
        Default DeviceType instance
    """
    try:
        return DeviceType.objects.get(slug='unknown-device')
    except DeviceType.DoesNotExist:
        manufacturer = find_or_create_manufacturer('Unknown')
        return DeviceType.objects.create(
            manufacturer=manufacturer,
            model='Unknown Device',
            slug='unknown-device',
            description='Default device type for unknown devices from WUG sync',
            u_height=1,
            is_full_depth=False
        )


def get_or_create_default_device_role() -> DeviceRole:
    """
    Get or create a default device role
    
    Returns:
        Default DeviceRole instance
    """
    return find_or_create_device_role('server')


def get_netbox_devices_for_export(connection, filters: Dict = None) -> List[Device]:
    """
    Get NetBox devices that should be exported to WhatsUp Gold
    
    Args:
        connection: WUGConnection instance
        filters: Optional filters for device selection
        
    Returns:
        List of NetBox Device instances
    """
    from ipam.models import IPAddress  # Import here to avoid circular imports
    
    # Base queryset - devices with primary IP addresses
    queryset = Device.objects.filter(
        primary_ip4__isnull=False,
        status='active'
    ).select_related('primary_ip4', 'site', 'device_type', 'device_role', 'platform')
    
    # Apply additional filters if provided
    if filters:
        if filters.get('sites'):
            queryset = queryset.filter(site__in=filters['sites'])
        
        if filters.get('device_roles'):
            queryset = queryset.filter(device_role__in=filters['device_roles'])
        
        if filters.get('device_types'):
            queryset = queryset.filter(device_type__in=filters['device_types'])
        
        if filters.get('tags'):
            queryset = queryset.filter(tags__in=filters['tags'])
        
        # Exclude devices already exported recently
        if filters.get('exclude_recent_exports'):
            from django.utils import timezone
            recent_cutoff = timezone.now() - timezone.timedelta(hours=24)
            
            recently_exported_ips = connection.ip_exports.filter(
                exported_at__gte=recent_cutoff,
                export_status__in=['exported', 'scan_triggered', 'scan_completed']
            ).values_list('ip_address', flat=True)
            
            if recently_exported_ips:
                queryset = queryset.exclude(
                    primary_ip4__address__startswith__in=[
                        str(ip).split('/')[0] for ip in recently_exported_ips
                    ]
                )
    
    return list(queryset)


def extract_device_ips_for_wug(devices: List[Device]) -> List[Dict]:
    """
    Extract IP addresses and metadata from NetBox devices for WUG export
    
    Args:
        devices: List of NetBox Device instances
        
    Returns:
        List of dictionaries containing IP and device metadata
    """
    ip_data = []
    
    for device in devices:
        if not device.primary_ip4:
            continue
            
        # Extract IP address (remove subnet mask)
        ip_address = str(device.primary_ip4.address).split('/')[0]
        
        # Prepare device metadata for WUG
        metadata = {
            'ip_address': ip_address,
            'netbox_id': device.id,
            'netbox_name': device.name,
            'netbox_site': device.site.name if device.site else '',
            'netbox_role': device.device_role.name if device.device_role else '',
            'netbox_type': f"{device.device_type.manufacturer.name} {device.device_type.model}" if device.device_type else '',
            'netbox_platform': device.platform.name if device.platform else '',
            'netbox_serial': device.serial or '',
            'netbox_asset_tag': device.asset_tag or '',
            'netbox_description': device.comments or '',
            'netbox_status': device.status,
        }
        
        # Add custom field data if available
        if hasattr(device, 'custom_field_data') and device.custom_field_data:
            metadata['netbox_custom_fields'] = device.custom_field_data
        
        # Add location information
        if device.location:
            metadata['netbox_location'] = device.location.name
        
        if device.rack:
            metadata['netbox_rack'] = device.rack.name
            if device.position:
                metadata['netbox_rack_position'] = device.position
        
        ip_data.append(metadata)
    
    return ip_data


def format_ips_for_wug_scan(ip_data: List[Dict], scan_type: str = 'individual') -> Dict:
    """
    Format IP addresses for WhatsUp Gold scanning
    
    Args:
        ip_data: List of IP data dictionaries from extract_device_ips_for_wug
        scan_type: Type of scan ('individual', 'batch', 'range')
        
    Returns:
        Dictionary formatted for WUG scanning
    """
    if scan_type == 'individual':
        # Format for individual IP scans
        return {
            'scan_requests': [
                {
                    'ip_address': item['ip_address'],
                    'device_name': item['netbox_name'],
                    'group': item['netbox_site'] or 'NetBox Devices',
                    'metadata': {k: v for k, v in item.items() if k.startswith('netbox_')},
                    'scan_options': {
                        'ping_timeout': 5000,
                        'snmp_timeout': 5000,
                        'discovery_methods': ['ping', 'snmp', 'wmi']
                    }
                }
                for item in ip_data
            ]
        }
    
    elif scan_type == 'batch':
        # Format for batch operations
        return {
            'ip_addresses': [item['ip_address'] for item in ip_data],
            'batch_config': {
                'group': 'NetBox Batch Import',
                'scan_after_add': True,
                'discovery_methods': ['ping', 'snmp', 'wmi'],
                'metadata_mapping': {
                    item['ip_address']: {k: v for k, v in item.items() if k.startswith('netbox_')}
                    for item in ip_data
                }
            }
        }
    
    elif scan_type == 'range':
        # Group IPs by network ranges for efficient scanning
        from ipaddress import IPv4Network, IPv4Address
        
        ranges = {}
        individual_ips = []
        
        for item in ip_data:
            try:
                ip = IPv4Address(item['ip_address'])
                # Try to group by /24 networks
                network = IPv4Network(f"{ip}/{24}", strict=False)
                network_str = str(network)
                
                if network_str not in ranges:
                    ranges[network_str] = []
                ranges[network_str].append(item)
                
            except ValueError:
                # If IP parsing fails, add to individual list
                individual_ips.append(item)
        
        return {
            'range_scans': [
                {
                    'ip_range': network,
                    'device_count': len(items),
                    'metadata': {item['ip_address']: item for item in items}
                }
                for network, items in ranges.items()
                if len(items) >= 3  # Only use range scan for 3+ IPs
            ],
            'individual_scans': [
                item for network, items in ranges.items()
                if len(items) < 3
            ] + individual_ips
        }
    
    else:
        raise ValueError(f"Unsupported scan type: {scan_type}")


def create_wug_device_config(netbox_device: Device, connection: 'WUGConnection') -> Dict:
    """
    Create WhatsUp Gold device configuration from NetBox device
    
    Args:
        netbox_device: NetBox Device instance
        connection: WUGConnection instance
        
    Returns:
        Dictionary with WUG device configuration
    """
    config = {
        'device_name': netbox_device.name,
        'ip_address': str(netbox_device.primary_ip4.address).split('/')[0],
        'group': netbox_device.site.name if netbox_device.site else 'NetBox Devices',
        'description': f"Imported from NetBox: {netbox_device.comments or netbox_device.name}",
    }
    
    # Add device type information
    if netbox_device.device_type:
        config['device_type'] = netbox_device.device_type.model
        config['manufacturer'] = netbox_device.device_type.manufacturer.name
    
    # Add platform information
    if netbox_device.platform:
        config['platform'] = netbox_device.platform.name
    
    # Add location information
    location_parts = []
    if netbox_device.site:
        location_parts.append(netbox_device.site.name)
    if netbox_device.location:
        location_parts.append(netbox_device.location.name)
    if netbox_device.rack:
        rack_info = netbox_device.rack.name
        if netbox_device.position:
            rack_info += f" U{netbox_device.position}"
        location_parts.append(rack_info)
    
    if location_parts:
        config['location'] = ' > '.join(location_parts)
    
    # Add custom fields for NetBox metadata
    config['custom_fields'] = {
        'netbox_id': netbox_device.id,
        'netbox_url': f"/dcim/devices/{netbox_device.id}/",
        'netbox_serial': netbox_device.serial or '',
        'netbox_asset_tag': netbox_device.asset_tag or '',
        'netbox_role': netbox_device.device_role.name if netbox_device.device_role else '',
        'netbox_status': netbox_device.status,
        'import_timestamp': datetime.now().isoformat(),
    }
    
    # Add NetBox custom field data
    if hasattr(netbox_device, 'custom_field_data') and netbox_device.custom_field_data:
        for key, value in netbox_device.custom_field_data.items():
            config['custom_fields'][f'netbox_cf_{key}'] = str(value)
    
    return config


def validate_ip_for_export(ip_address: str, connection: 'WUGConnection') -> Dict:
    """
    Validate if an IP address can be exported to WhatsUp Gold
    
    Args:
        ip_address: IP address to validate
        connection: WUGConnection instance
        
    Returns:
        Dictionary with validation results
    """
    from ipaddress import IPv4Address, AddressValueError
    
    result = {
        'valid': True,
        'ip_address': ip_address,
        'warnings': [],
        'errors': []
    }
    
    # Basic IP validation
    try:
        ip_obj = IPv4Address(ip_address)
    except AddressValueError:
        result['valid'] = False
        result['errors'].append('Invalid IP address format')
        return result
    
    # Check for private vs public IP
    if ip_obj.is_private:
        result['warnings'].append('Private IP address')
    elif ip_obj.is_global:
        result['warnings'].append('Public IP address - ensure WUG can reach it')
    
    # Check for special IP ranges
    if ip_obj.is_loopback:
        result['valid'] = False
        result['errors'].append('Loopback IP address cannot be monitored')
    
    if ip_obj.is_multicast:
        result['valid'] = False
        result['errors'].append('Multicast IP address cannot be monitored')
    
    if ip_obj.is_reserved:
        result['warnings'].append('Reserved IP address range')
    
    # Check if IP was recently exported
    from .models import NetBoxIPExport
    recent_export = NetBoxIPExport.objects.filter(
        connection=connection,
        ip_address=ip_address,
        exported_at__isnull=False
    ).order_by('-exported_at').first()
    
    if recent_export:
        from django.utils import timezone
        hours_ago = (timezone.now() - recent_export.exported_at).total_seconds() / 3600
        
        if hours_ago < 24:
            result['warnings'].append(f'IP was exported {hours_ago:.1f} hours ago')
        
        if recent_export.export_status == 'error':
            result['warnings'].append('Previous export failed - retry may be needed')
    
    return result


def cleanup_orphaned_wug_devices(connection_id: int, active_wug_ids: List[str]) -> int:
    """
    Clean up WUGDevice records for devices that no longer exist in WhatsUp Gold
    
    Args:
        connection_id: WUGConnection ID
        active_wug_ids: List of WUG device IDs that are currently active
        
    Returns:
        Number of cleaned up devices
    """
    from .models import WUGDevice  # Import here to avoid circular imports
    
    # Find WUG devices that are no longer present in WhatsUp Gold
    orphaned_devices = WUGDevice.objects.filter(
        connection_id=connection_id
    ).exclude(wug_id__in=active_wug_ids)
    
    count = orphaned_devices.count()
    
    if count > 0:
        logger.info(f"Marking {count} orphaned WUG devices as inactive")
        
        # Mark as inactive rather than deleting (preserve history)
        orphaned_devices.update(
            sync_enabled=False,
            sync_status='skipped'
        )
    
    return count


def get_or_create_wug_tag():
    """
    Get or create the 'wug' tag for marking devices synced from WhatsUp Gold
    
    Returns:
        Tag instance
    """
    tag, created = Tag.objects.get_or_create(
        name='wug',
        defaults={
            'slug': 'wug',
            'color': '2196f3',  # Blue color
            'description': 'Device synced from WhatsUp Gold'
        }
    )
    return tag


def  create_netbox_device_from_wug_data(wug_device_data: Dict, connection) -> Device:
    """
    Create a NetBox device from normalized WUG device data
    
    Args:
        wug_device_data: Normalized device data from WUG
        connection: WUGConnection instance
        
    Returns:
        Device instance or None if creation failed
    """
    try:
        print(f"DEBUG: Function start - processing device data: {wug_device_data.get('name')}")
        device_name = wug_device_data.get('name')
        device_ip = wug_device_data.get('ip_address')
        vendor = wug_device_data.get('vendor', 'Unknown')
        device_type_name = wug_device_data.get('device_type', 'Unknown')
        group_name = wug_device_data.get('group', 'Default')
        
        print(f"DEBUG: Variables extracted - device_name={device_name}, device_ip={device_ip}")
        
        # Check if device already exists
        existing_device = Device.objects.filter(name=device_name).first()
        if existing_device:
            print(f"DEBUG: Device {device_name} already exists, checking IP assignment")
            logger.debug(f"Device {device_name} already exists in NetBox, checking IP assignment")
            
            # Check if the device has a primary IP assigned
            if not existing_device.primary_ip4 and device_ip:
                print(f"DEBUG: Device {device_name} missing primary IP, assigning {device_ip}")
                logger.info(f"Device {device_name} missing primary IP, assigning {device_ip}")
                
                try:
                    from ipam.models import IPAddress
                    from dcim.models import Interface
                    
                    # Check if IP address already exists
                    ip_address = IPAddress.objects.filter(address=f"{device_ip}/32").first()
                    
                    if not ip_address:
                        # Create new IP address
                        ip_address = IPAddress.objects.create(
                            address=f"{device_ip}/32",
                            description=f"Primary IP for {device_name} (synced from WUG)"
                        )
                        logger.info(f"Created IP address: {ip_address.address}")
                    else:
                        logger.info(f"IP address {device_ip}/32 already exists")
                    
                    # Create a management interface if it doesn't exist
                    interface_name = "mgmt0"
                    interface = Interface.objects.filter(
                        device=existing_device,
                        name=interface_name
                    ).first()
                    
                    if not interface:
                        interface = Interface.objects.create(
                            device=existing_device,
                            name=interface_name,
                            type="virtual",
                            description=f"Management interface (synced from WUG)"
                        )
                        logger.info(f"Created interface: {interface.name}")
                    else:
                        logger.info(f"Interface {interface_name} already exists")
                    
                    # Assign IP to interface
                    ip_address.assigned_object = interface
                    ip_address.save()
                    logger.info(f"Assigned IP {ip_address.address} to interface {interface.name}")
                    
                    # Set as primary IP for device
                    existing_device.primary_ip4 = ip_address
                    existing_device.save()
                    
                    logger.info(f"Assigned primary IP {device_ip} to existing device {device_name}")
                    print(f"DEBUG: Successfully assigned IP {device_ip} to {device_name}")
                    
                except Exception as ip_error:
                    logger.error(f"Failed to assign IP address {device_ip} to existing device {device_name}: {str(ip_error)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                if existing_device.primary_ip4:
                    print(f"DEBUG: Device {device_name} already has primary IP: {existing_device.primary_ip4}")
                else:
                    print(f"DEBUG: Device {device_name} has no IP data from WUG")
            
            return existing_device
        
        # Create site from group name if auto-create is enabled
        site = None
        if connection.auto_create_sites and group_name:
            site = find_or_create_site(group_name)
        else:
            site = get_or_create_default_site()
        
        # Create device type if auto-create is enabled
        device_type = None
        if connection.auto_create_device_types:
            device_type = find_or_create_device_type(vendor, device_type_name)
        else:
            device_type = get_or_create_default_device_type()
        
        # Get device role
        device_role = connection.default_device_role
        if not device_role:
            device_role = find_or_create_device_role('server')
        
        # Create the device
        device = Device.objects.create(
            name=device_name,
            device_type=device_type,
            role=device_role,
            site=site,
            status=map_wug_status_to_netbox(wug_device_data.get('status', 'active'))
        )
        
        logger.debug(f"Device created successfully: {device.name} (ID: {device.id})")
        
        # Add the "wug" tag to identify devices synced from WhatsUp Gold
        wug_tag = get_or_create_wug_tag()
        device.tags.add(wug_tag)
        
        logger.debug(f"WUG tag added to device {device.name}")
        
        # Create IP address and assign as primary if IP is provided
        if device_ip:
            logger.info(f"Assigning IP {device_ip} to device {device_name}")
            print(f"DEBUG: Starting IP assignment for {device_name} with IP {device_ip}")
            try:
                from ipam.models import IPAddress
                from dcim.models import Interface
                
                # Check if IP address already exists
                ip_address = IPAddress.objects.filter(address=f"{device_ip}/32").first()
                
                if not ip_address:
                    # Create new IP address
                    ip_address = IPAddress.objects.create(
                        address=f"{device_ip}/32",
                        description=f"Primary IP for {device_name} (synced from WUG)"
                    )
                    logger.info(f"Created IP address: {ip_address.address}")
                else:
                    logger.info(f"IP address {device_ip}/32 already exists")
                
                # Create a management interface if it doesn't exist
                interface_name = "mgmt0"
                interface = Interface.objects.filter(
                    device=device,
                    name=interface_name
                ).first()
                
                if not interface:
                    interface = Interface.objects.create(
                        device=device,
                        name=interface_name,
                        type="virtual",
                        description=f"Management interface (synced from WUG)"
                    )
                    logger.info(f"Created interface: {interface.name}")
                else:
                    logger.info(f"Interface {interface_name} already exists")
                
                # Assign IP to interface
                ip_address.assigned_object = interface
                ip_address.save()
                logger.info(f"Assigned IP {ip_address.address} to interface {interface.name}")
                
                # Set as primary IP for device
                device.primary_ip4 = ip_address
                device.save()
                
                logger.info(f"Assigned primary IP {device_ip} to device {device_name}")
                
            except Exception as ip_error:
                logger.error(f"Failed to assign IP address {device_ip} to device {device_name}: {str(ip_error)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.warning(f"No IP address provided for device {device_name}, skipping IP assignment")
        
        logger.info(f"Created NetBox device: {device_name} (ID: {device.id}) with 'wug' tag")
        return device
        
    except Exception as e:
        logger.error(f"Failed to create NetBox device for {device_name}: {str(e)}")
        return None


def sync_wug_connection(connection, sync_type: str = 'manual') -> Dict:
    """
    Sync devices for a specific WUG connection directly (bypassing JobRunner)
    
    Args:
        connection: WUGConnection instance
        sync_type: Type of sync operation ('manual', 'scheduled', 'api')
        
    Returns:
        Dictionary with sync results
    """
    logger.info(f"Starting direct sync for connection: {connection.name}")
    
    from .models import WUGSyncLog
    from .wug_client import WUGAPIClient
    
    # Create sync log entry
    sync_log = WUGSyncLog.objects.create(
        connection=connection,
        sync_type=sync_type,
        status='running',
        start_time=datetime.now(),  # Fix: Add start_time
        devices_discovered=0,
        devices_created=0,
        devices_updated=0,
        devices_errors=0
    )
    
    devices_synced = 0
    errors = 0
    
    try:
        # Create WUG API client
        with WUGAPIClient(
            host=connection.host,
            username=connection.username,
            password=connection.password,  # Fix: Use password field directly
            port=connection.port,
            use_ssl=connection.use_ssl,
            verify_ssl=connection.verify_ssl
        ) as client:
            
            # Test connection first
            test_result = client.test_connection()
            if not test_result.get('success', False):
                error_msg = test_result.get('message', 'Connection test failed')
                logger.error(f"WUG connection test failed: {error_msg}")
                
                # Update sync log
                sync_log.status = 'failed'
                sync_log.summary = f"Connection test failed: {error_msg}"
                sync_log.end_time = datetime.now()
                sync_log.save()
                
                return {
                    'success': False,
                    'message': error_msg,
                    'devices_synced': 0,
                    'errors': 1
                }
            
            logger.info(f"WUG connection test successful for {connection.name}")
            
            # Get devices from WUG
            wug_devices = client.get_devices(include_details=True)
            devices_discovered = len(wug_devices)
            
            logger.info(f"Discovered {devices_discovered} devices from WUG")
            
            # Update sync log with discovered count
            sync_log.devices_discovered = devices_discovered
            sync_log.save()
            
            # Process each device
            # ADD FILE LOGGING
            with open('/tmp/wug_sync_debug.log', 'w') as f:
                f.write(f"Starting sync loop - {len(wug_devices)} devices to process\n")
                for device_data in wug_devices:
                    device_name = device_data.get('name', 'unknown')
                    device_id = device_data.get('id', 'NO_ID')
                    device_ip = device_data.get('networkAddress') or device_data.get('ipAddress') or device_data.get('hostName', 'NO_IP')
                    f.write(f"\n=== Processing device: {device_name} (ID: {device_id}, IP: {device_ip}) ===\n")
                    f.flush()
            
            for device_data in wug_devices:
                device_name = device_data.get('name', 'unknown')
                logger.info(f"Processing device: {device_name}")
                print(f"DEBUG: Starting to process device: {device_name}")
                
                try:
                    # Normalize device data first
                    from .wug_client import normalize_wug_device_data
                    logger.info(f"Normalizing data for device: {device_name}")
                    normalized_device_data = normalize_wug_device_data(device_data)
                    
                    # FILE LOGGING
                    with open('/tmp/wug_sync_debug.log', 'a') as f:
                        f.write(f"\nNormalized {device_name}:\n")
                        f.write(f"  name: {normalized_device_data.get('name')}\n")
                        f.write(f"  ip_address: {normalized_device_data.get('ip_address')}\n")
                        f.write(f"  id: {normalized_device_data.get('id')}\n")
                        f.flush()
                    
                    logger.info(f"Normalized device data: name={normalized_device_data.get('name')}, ip={normalized_device_data.get('ip_address')}, id={normalized_device_data.get('id')}")
                    print(f"DEBUG: Normalized {device_name} - IP: {normalized_device_data.get('ip_address')}, ID: {normalized_device_data.get('id')}")
                    
                    # Sync individual device with normalized data
                    logger.info(f"Calling sync_single_device for: {device_name}")
                    result = sync_single_device(connection, normalized_device_data)
                    
                    # FILE LOGGING
                    with open('/tmp/wug_sync_debug.log', 'a') as f:
                        f.write(f"Sync result for {device_name}: {result}\n")
                        f.flush()
                    
                    logger.info(f"Sync result for {device_name}: {result}")
                    print(f"DEBUG: Sync result for {device_name}: {result}")
                    
                    if result['success']:
                        if result['action'] == 'created':
                            sync_log.devices_created += 1
                            logger.info(f"Device {device_name} CREATED successfully")
                        elif result['action'] == 'updated':
                            sync_log.devices_updated += 1
                            logger.info(f"Device {device_name} UPDATED successfully")
                        devices_synced += 1
                    else:
                        sync_log.devices_errors += 1
                        errors += 1
                        logger.error(f"Failed to sync device {device_name}: {result.get('error')}")
                        print(f"DEBUG ERROR: Failed to sync {device_name}: {result.get('error')}")
                        
                except Exception as device_error:
                    sync_log.devices_errors += 1
                    errors += 1
                    logger.error(f"Exception while syncing device {device_name}: {str(device_error)}")
                    print(f"DEBUG EXCEPTION: {device_name}: {str(device_error)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    print(f"DEBUG TRACEBACK: {traceback.format_exc()}")
            
            # Update final sync log
            sync_log.status = 'completed' if errors == 0 else 'completed_with_errors'
            sync_log.end_time = datetime.now()
            sync_log.summary = f"Synced {devices_synced} devices with {errors} errors"
            sync_log.save()
            
            logger.info(f"Sync completed for {connection.name}: {devices_synced} devices synced, {errors} errors")
            
            return {
                'success': True,
                'devices_synced': devices_synced,
                'errors': errors,
                'devices_discovered': devices_discovered,
                'message': f"Sync completed: {devices_synced} devices synced"
            }
            
    except Exception as e:
        logger.error(f"Exception during sync for connection {connection.name}: {str(e)}")
        
        # Update sync log with error
        sync_log.status = 'error'
        sync_log.end_time = datetime.now()
        sync_log.summary = f"Sync failed with exception: {str(e)}"
        sync_log.save()
        
        return {
            'success': False,
            'message': f"Sync failed: {str(e)}",
            'devices_synced': devices_synced,
            'errors': errors + 1
        }


def sync_single_device(connection, device_data: Dict) -> Dict:
    """
    Sync a single device from WUG to NetBox
    
    Args:
        connection: WUGConnection instance
        device_data: Device data from WUG API
        
    Returns:
        Dictionary with sync result for this device
    """
    from .models import WUGDevice
    
    try:
        device_name = device_data.get('name', 'Unknown')
        device_ip = device_data.get('ip_address')  # Use normalized field name
        wug_device_id = device_data.get('id')  # Use normalized field name
        
        logger.info(f"sync_single_device called for: {device_name}, IP: {device_ip}, ID: {wug_device_id}")
        print(f"DEBUG sync_single_device: {device_name}, IP: {device_ip}, ID: {wug_device_id}")
        
        if not device_name or not device_ip or not wug_device_id:
            error_msg = f"Missing required device data: name={device_name}, ip={device_ip}, id={wug_device_id}"
            logger.error(error_msg)
            print(f"DEBUG ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        logger.debug(f"Syncing device: {device_name} ({device_ip})")
        print(f"DEBUG: All required fields present for {device_name}")
        
        # Check if device already exists
        existing_wug_device = WUGDevice.objects.filter(
            connection=connection,
            wug_id=wug_device_id
        ).first()
        
        if existing_wug_device:
            logger.info(f"WUGDevice record already exists for {device_name}")
            print(f"DEBUG: WUGDevice record exists for {device_name}")
        else:
            logger.info(f"No existing WUGDevice record for {device_name}, will create new")
            print(f"DEBUG: No existing WUGDevice for {device_name}")
        
        # Create or update NetBox device
        logger.info(f"Calling create_netbox_device_from_wug_data for {device_name}")
        print(f"DEBUG: Calling create_netbox_device_from_wug_data for {device_name}")
        netbox_device = create_netbox_device_from_wug_data(device_data, connection)
        
        if netbox_device:
            logger.info(f"create_netbox_device_from_wug_data returned device: {netbox_device.name} (ID: {netbox_device.id})")
            print(f"DEBUG: Got NetBox device: {netbox_device.name} (ID: {netbox_device.id})")
            # Create or update WUGDevice record
            if existing_wug_device:
                logger.info(f"Updating existing WUGDevice record for {device_name}")
                print(f"DEBUG: Updating WUGDevice record for {device_name}")
                existing_wug_device.netbox_device = netbox_device
                existing_wug_device.wug_name = device_name
                existing_wug_device.wug_ip_address = device_ip
                existing_wug_device.last_sync_attempt = datetime.now()
                existing_wug_device.last_sync_success = datetime.now()
                existing_wug_device.sync_status = 'success'
                existing_wug_device.save()
                action = 'updated'
                logger.info(f"WUGDevice record updated for {device_name}")
            else:
                logger.info(f"Creating new WUGDevice record for {device_name}")
                print(f"DEBUG: Creating new WUGDevice record for {device_name}")
                WUGDevice.objects.create(
                    connection=connection,
                    wug_id=str(wug_device_id),
                    wug_name=device_name,
                    wug_ip_address=device_ip,
                    netbox_device=netbox_device,
                    sync_status='success',
                    last_sync_attempt=datetime.now(),
                    last_sync_success=datetime.now()
                )
                action = 'created'
                logger.info(f"WUGDevice record created for {device_name}")
                print(f"DEBUG: WUGDevice record created for {device_name}")
            
            logger.info(f"Successfully synced {device_name} - action: {action}")
            print(f"DEBUG: SUCCESS - {device_name} - action: {action}")
            return {
                'success': True,
                'action': action,
                'device_name': device_name,
                'netbox_device_id': netbox_device.id
            }
        else:
            error_msg = f"Failed to create/update NetBox device for {device_name}"
            logger.error(error_msg)
            print(f"DEBUG ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
            
    except Exception as e:
        error_msg = f"Exception syncing device: {str(e)}"
        logger.error(error_msg)
        print(f"DEBUG EXCEPTION in sync_single_device: {error_msg}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"DEBUG TRACEBACK: {traceback.format_exc()}")
        return {
            'success': False,
            'error': error_msg
        }