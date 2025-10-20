"""
NetBox WhatsUp Gold Sync Jobs

This module contains the background jobs for synchronizing devices between
NetBox and WhatsUp Gold using NetBox's job system.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from django.utils import timezone as django_timezone
from netbox.jobs import JobRunner

from .models import WUGConnection, WUGDevice, WUGSyncLog
from .wug_client import WUGAPIClient, normalize_wug_device_data, create_netbox_device_data
from .sync_utils import (
    find_or_create_site, 
    find_or_create_device_type, 
    find_or_create_device_role,
    create_or_update_netbox_device
)


logger = logging.getLogger(__name__)


class WUGSyncJob(JobRunner):
    """
    NetBox job for synchronizing devices from WhatsUp Gold
    """
    
    class Meta:
        name = "WhatsUp Gold Device Sync"
        description = "Synchronize devices from WhatsUp Gold to NetBox"
        
    def run(self, connection_id: int = None, sync_type: str = 'scheduled', **kwargs):
        """
        Main sync job execution
        
        Args:
            connection_id: Specific WUG connection to sync (None for all active connections)
            sync_type: Type of sync ('scheduled', 'manual', 'api')
        """
        self.logger.info(f"Starting WhatsUp Gold sync job (type: {sync_type})")
        
        # Get connections to sync
        if connection_id:
            connections = WUGConnection.objects.filter(id=connection_id, is_active=True)
        else:
            connections = WUGConnection.objects.filter(is_active=True)
        
        if not connections.exists():
            self.logger.warning("No active WUG connections found for sync")
            return
        
        total_success = 0
        total_errors = 0
        
        # Sync each connection
        for connection in connections:
            try:
                success_count, error_count = self._sync_connection(connection, sync_type)
                total_success += success_count
                total_errors += error_count
                
            except Exception as e:
                self.logger.error(f"Failed to sync connection {connection.name}: {str(e)}")
                total_errors += 1
        
        # Log summary
        self.logger.info(
            f"WUG sync completed. "
            f"Connections processed: {len(connections)}, "
            f"Devices synced: {total_success}, "
            f"Errors: {total_errors}"
        )
        
        return {
            'connections_processed': len(connections),
            'devices_synced': total_success,
            'errors': total_errors
        }
    
    def _sync_connection(self, connection: WUGConnection, sync_type: str) -> Tuple[int, int]:
        """
        Sync devices for a specific WUG connection
        
        Args:
            connection: WUGConnection instance
            sync_type: Type of sync operation
            
        Returns:
            Tuple of (success_count, error_count)
        """
        self.logger.info(f"Starting sync for connection: {connection.name}")
        
        # Create sync log entry
        sync_log = WUGSyncLog.objects.create(
            connection=connection,
            sync_type=sync_type,
            status='running',
            start_time=django_timezone.now()
        )
        
        success_count = 0
        error_count = 0
        
        try:
            # Initialize WUG API client
            with WUGAPIClient(
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password,
                use_ssl=connection.use_ssl,
                verify_ssl=connection.verify_ssl
            ) as wug_client:
                
                # Test connection
                test_result = wug_client.test_connection()
                if not test_result['success']:
                    raise Exception(f"WUG connection test failed: {test_result['message']}")
                
                # Get devices from WUG
                self.logger.info("Fetching devices from WhatsUp Gold...")
                wug_devices = wug_client.get_devices(include_details=True)
                
                sync_log.devices_discovered = len(wug_devices)
                sync_log.save()
                
                self.logger.info(f"Found {len(wug_devices)} devices in WhatsUp Gold")
                
                # Process each device
                for wug_device_raw in wug_devices:
                    try:
                        result = self._process_wug_device(connection, wug_device_raw)
                        
                        if result['action'] in ['created', 'updated']:
                            success_count += 1
                            if result['action'] == 'created':
                                sync_log.devices_created += 1
                            else:
                                sync_log.devices_updated += 1
                        elif result['action'] == 'skipped':
                            sync_log.devices_skipped += 1
                        
                    except Exception as e:
                        error_count += 1
                        sync_log.devices_errors += 1
                        self.logger.error(
                            f"Failed to process device {wug_device_raw.get('id', 'unknown')}: {str(e)}"
                        )
            
            # Update connection last sync time
            connection.last_sync = django_timezone.now()
            connection.save()
            
            # Complete sync log
            sync_log.status = 'completed'
            sync_log.end_time = django_timezone.now()
            sync_log.summary = (
                f"Processed {sync_log.devices_discovered} devices. "
                f"Created: {sync_log.devices_created}, "
                f"Updated: {sync_log.devices_updated}, "
                f"Skipped: {sync_log.devices_skipped}, "
                f"Errors: {sync_log.devices_errors}"
            )
            sync_log.save()
            
            self.logger.info(f"Sync completed for {connection.name}: {sync_log.summary}")
            
        except Exception as e:
            error_count += 1
            
            # Mark sync as failed
            sync_log.status = 'failed'
            sync_log.end_time = django_timezone.now()
            sync_log.error_message = str(e)
            sync_log.save()
            
            self.logger.error(f"Sync failed for connection {connection.name}: {str(e)}")
            raise
        
        return success_count, error_count
    
    def _process_wug_device(self, connection: WUGConnection, wug_device_raw: Dict) -> Dict:
        """
        Process a single WhatsUp Gold device
        
        Args:
            connection: WUGConnection instance
            wug_device_raw: Raw device data from WUG API
            
        Returns:
            Dictionary with processing results
        """
        # Normalize WUG device data
        wug_device_data = normalize_wug_device_data(wug_device_raw)
        
        wug_device_id = wug_device_data.get('id')
        wug_device_name = wug_device_data.get('name', f"unknown-{wug_device_id}")
        
        if not wug_device_id:
            raise ValueError("Device missing required ID field")
        
        self.logger.debug(f"Processing WUG device: {wug_device_name} (ID: {wug_device_id})")
        
        # Get or create WUGDevice record
        wug_device, created = WUGDevice.objects.get_or_create(
            connection=connection,
            wug_id=str(wug_device_id),
            defaults={
                'wug_name': wug_device_name,
                'sync_status': 'pending'
            }
        )
        
        # Update WUG device record with latest data
        wug_device.wug_name = wug_device_name
        wug_device.wug_display_name = wug_device_data.get('display_name', '')
        wug_device.wug_ip_address = wug_device_data.get('ip_address')
        wug_device.wug_mac_address = wug_device_data.get('mac_address', '')
        wug_device.wug_device_type = wug_device_data.get('device_type', '')
        wug_device.wug_vendor = wug_device_data.get('vendor', '')
        wug_device.wug_model = wug_device_data.get('model', '')
        wug_device.wug_os_version = wug_device_data.get('os_version', '')
        wug_device.wug_group = wug_device_data.get('group', '')
        wug_device.wug_location = wug_device_data.get('location', '')
        wug_device.wug_status = wug_device_data.get('status', '')
        wug_device.wug_last_seen = wug_device_data.get('last_seen')
        wug_device.wug_raw_data = wug_device_raw
        wug_device.last_sync_attempt = django_timezone.now()
        wug_device.sync_status = 'syncing'
        
        # Check if sync is enabled for this device
        if not wug_device.sync_enabled:
            wug_device.sync_status = 'skipped'
            wug_device.save()
            return {'action': 'skipped', 'reason': 'sync_disabled'}
        
        try:
            # Determine NetBox site
            site = None
            if connection.auto_create_sites and wug_device.wug_group:
                site = find_or_create_site(wug_device.wug_group)
            
            # Determine NetBox device type
            device_type = None
            if connection.auto_create_device_types:
                vendor = wug_device.wug_vendor or 'Unknown'
                model = wug_device.wug_model or wug_device.wug_device_type or 'Unknown'
                device_type = find_or_create_device_type(vendor, model)
            
            # Get device role
            device_role = connection.default_device_role
            if not device_role:
                device_role = find_or_create_device_role('server')  # fallback
            
            # Create NetBox device data
            netbox_device_data = create_netbox_device_data(
                wug_device_data,
                site_id=site.id if site else None,
                device_type_id=device_type.id if device_type else None,
                device_role_id=device_role.id if device_role else None
            )
            
            # Create or update NetBox device
            netbox_device, action = create_or_update_netbox_device(
                wug_device, netbox_device_data
            )
            
            # Update WUG device with NetBox relationship
            wug_device.netbox_device = netbox_device
            wug_device.sync_status = 'success'
            wug_device.last_sync_success = django_timezone.now()
            wug_device.sync_error_message = ''
            
            self.logger.info(
                f"Successfully {action} NetBox device: {netbox_device.name} "
                f"for WUG device: {wug_device_name}"
            )
            
            return {'action': action, 'netbox_device': netbox_device}
            
        except Exception as e:
            wug_device.sync_status = 'error'
            wug_device.sync_error_message = str(e)
            
            self.logger.error(f"Failed to sync device {wug_device_name}: {str(e)}")
            raise
            
        finally:
            wug_device.save()


class WUGFullSyncJob(WUGSyncJob):
    """
    Job for performing a full synchronization of all devices
    """
    
    class Meta:
        name = "WhatsUp Gold Full Sync"
        description = "Perform a complete synchronization of all devices from WhatsUp Gold"
    
    def run(self, **kwargs):
        """Run full sync for all active connections"""
        return super().run(sync_type='manual', **kwargs)


class WUGConnectionTestJob(JobRunner):
    """
    Job for testing WhatsUp Gold connection settings
    """
    
    class Meta:
        name = "Test WhatsUp Gold Connection"
        description = "Test connectivity and authentication to WhatsUp Gold server"
    
    def run(self, connection_id: int, **kwargs):
        """
        Test a specific WUG connection
        
        Args:
            connection_id: WUGConnection ID to test
        """
        try:
            connection = WUGConnection.objects.get(id=connection_id)
        except WUGConnection.DoesNotExist:
            self.logger.error(f"WUG connection {connection_id} not found")
            return {'success': False, 'error': 'Connection not found'}
        
        self.logger.info(f"Testing WUG connection: {connection.name}")
        
        try:
            with WUGAPIClient(
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password,
                use_ssl=connection.use_ssl,
                verify_ssl=connection.verify_ssl
            ) as wug_client:
                
                result = wug_client.test_connection()
                
                if result['success']:
                    self.logger.info(f"Connection test successful for {connection.name}")
                    
                    # Try to get device count as additional validation
                    try:
                        devices = wug_client.get_devices(include_details=False)
                        device_count = len(devices) if isinstance(devices, list) else 0
                        result['device_count'] = device_count
                        self.logger.info(f"Found {device_count} devices in WhatsUp Gold")
                    except Exception as e:
                        self.logger.warning(f"Could not get device count: {str(e)}")
                        result['device_count'] = 'unknown'
                else:
                    self.logger.error(f"Connection test failed for {connection.name}: {result['message']}")
                
                return result
                
        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            self.logger.error(error_msg)
            return {'success': False, 'error': error_msg}


class NetBoxToWUGExportJob(JobRunner):
    """
    NetBox job for exporting NetBox IP addresses to WhatsUp Gold
    """
    
    class Meta:
        name = "Export NetBox IPs to WhatsUp Gold"
        description = "Export NetBox device IP addresses to WhatsUp Gold for monitoring"
        
    def run(self, connection_id: int = None, export_type: str = 'scheduled', 
            device_filters: Dict = None, **kwargs):
        """
        Main export job execution
        
        Args:
            connection_id: Specific WUG connection to export to (None for all active connections)
            export_type: Type of export ('scheduled', 'manual', 'api')
            device_filters: Filters to apply when selecting NetBox devices
        """
        from .sync_utils import get_netbox_devices_for_export, extract_device_ips_for_wug, format_ips_for_wug_scan
        
        self.logger.info(f"Starting NetBox to WUG export job (type: {export_type})")
        
        # Get connections to export to
        if connection_id:
            connections = WUGConnection.objects.filter(
                id=connection_id, 
                is_active=True, 
                enable_netbox_export=True
            )
        else:
            connections = WUGConnection.objects.filter(
                is_active=True, 
                enable_netbox_export=True
            )
        
        if not connections.exists():
            self.logger.warning("No active WUG connections found with NetBox export enabled")
            return
        
        total_exported = 0
        total_errors = 0
        
        # Process each connection
        for connection in connections:
            try:
                exported_count, error_count = self._export_to_connection(
                    connection, export_type, device_filters or {}
                )
                total_exported += exported_count
                total_errors += error_count
                
            except Exception as e:
                self.logger.error(f"Failed to export to connection {connection.name}: {str(e)}")
                total_errors += 1
        
        # Log summary
        self.logger.info(
            f"NetBox export completed. "
            f"Connections processed: {len(connections)}, "
            f"IPs exported: {total_exported}, "
            f"Errors: {total_errors}"
        )
        
        return {
            'connections_processed': len(connections),
            'ips_exported': total_exported,
            'errors': total_errors
        }
    
    def _export_to_connection(self, connection: WUGConnection, export_type: str, 
                            device_filters: Dict) -> Tuple[int, int]:
        """
        Export NetBox devices to a specific WUG connection
        
        Args:
            connection: WUGConnection instance
            export_type: Type of export operation
            device_filters: Filters for device selection
            
        Returns:
            Tuple of (exported_count, error_count)
        """
        from .models import NetBoxIPExport
        from .sync_utils import (
            get_netbox_devices_for_export, 
            extract_device_ips_for_wug, 
            format_ips_for_wug_scan,
            validate_ip_for_export
        )
        
        self.logger.info(f"Starting export for connection: {connection.name}")
        
        exported_count = 0
        error_count = 0
        
        try:
            # Get NetBox devices to export
            self.logger.info("Fetching NetBox devices for export...")
            
            # Apply default filters for export
            export_filters = {
                'exclude_recent_exports': True,
                **device_filters
            }
            
            devices = get_netbox_devices_for_export(connection, export_filters)
            
            if not devices:
                self.logger.info(f"No devices found for export to {connection.name}")
                return 0, 0
            
            self.logger.info(f"Found {len(devices)} NetBox devices for export")
            
            # Extract IP addresses and metadata
            ip_data = extract_device_ips_for_wug(devices)
            
            # Initialize WUG API client
            with WUGAPIClient(
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password,
                use_ssl=connection.use_ssl,
                verify_ssl=connection.verify_ssl
            ) as wug_client:
                
                # Test connection
                test_result = wug_client.test_connection()
                if not test_result['success']:
                    raise Exception(f"WUG connection test failed: {test_result['message']}")
                
                # Process each IP address
                for ip_info in ip_data:
                    try:
                        result = self._export_single_ip(
                            connection, wug_client, ip_info, export_type
                        )
                        
                        if result['success']:
                            exported_count += 1
                        else:
                            error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        self.logger.error(
                            f"Failed to export IP {ip_info.get('ip_address', 'unknown')}: {str(e)}"
                        )
            
            # Update connection last export time
            connection.last_export = django_timezone.now()
            connection.save()
            
            self.logger.info(f"Export completed for {connection.name}: {exported_count} exported, {error_count} errors")
            
        except Exception as e:
            error_count += 1
            self.logger.error(f"Export failed for connection {connection.name}: {str(e)}")
            raise
        
        return exported_count, error_count
    
    def _export_single_ip(self, connection: WUGConnection, wug_client: WUGAPIClient, 
                         ip_info: Dict, export_type: str) -> Dict:
        """
        Export a single IP address to WhatsUp Gold
        
        Args:
            connection: WUGConnection instance
            wug_client: WUGAPIClient instance
            ip_info: IP and device information
            export_type: Type of export operation
            
        Returns:
            Dictionary with export results
        """
        from .models import NetBoxIPExport
        from .sync_utils import validate_ip_for_export, create_wug_device_config
        from dcim.models import Device
        
        ip_address = ip_info['ip_address']
        netbox_device_id = ip_info.get('netbox_id')
        
        self.logger.debug(f"Processing IP: {ip_address}")
        
        # Validate IP for export
        validation = validate_ip_for_export(ip_address, connection)
        if not validation['valid']:
            return {
                'success': False,
                'ip_address': ip_address,
                'error': '; '.join(validation['errors'])
            }
        
        # Log warnings if any
        for warning in validation['warnings']:
            self.logger.warning(f"IP {ip_address}: {warning}")
        
        try:
            # Get or create export record
            netbox_device = None
            if netbox_device_id:
                try:
                    netbox_device = Device.objects.get(id=netbox_device_id)
                except Device.DoesNotExist:
                    pass
            
            export_record, created = NetBoxIPExport.objects.get_or_create(
                connection=connection,
                ip_address=ip_address,
                defaults={
                    'netbox_device': netbox_device,
                    'export_reason': export_type,
                    'export_status': 'pending'
                }
            )
            
            if not created and export_record.export_status in ['exported', 'scan_triggered', 'scan_completed']:
                # Skip if recently processed
                return {
                    'success': False,
                    'ip_address': ip_address,
                    'error': f'IP already processed (status: {export_record.export_status})'
                }
            
            # Update export record
            export_record.export_status = 'pending'
            export_record.export_reason = export_type
            export_record.save()
            
            # Try to add device by IP first
            try:
                device_config = create_wug_device_config(netbox_device, connection) if netbox_device else {
                    'device_name': f"NetBox-{ip_address}",
                    'group': 'NetBox Exports'
                }
                
                add_result = wug_client.add_device_by_ip(ip_address, device_config)
                
                if add_result['success']:
                    export_record.export_status = 'exported'
                    export_record.exported_at = django_timezone.now()
                    export_record.wug_device_id = add_result.get('device_id', '')
                    
                    # Update device metadata if we have it
                    if netbox_device and export_record.wug_device_id:
                        try:
                            metadata_result = wug_client.update_device_metadata(
                                export_record.wug_device_id, ip_info
                            )
                            self.logger.debug(f"Updated metadata for WUG device {export_record.wug_device_id}")
                        except Exception as e:
                            self.logger.warning(f"Failed to update metadata: {str(e)}")
                    
                    self.logger.info(f"Successfully exported IP {ip_address} as WUG device")
                
            except Exception as e:
                # If device addition fails, try scanning the IP instead
                self.logger.warning(f"Device addition failed for {ip_address}, trying scan: {str(e)}")
                
                if connection.auto_scan_exported_ips:
                    try:
                        scan_result = wug_client.scan_ip_address(ip_address, {
                            'device_name': ip_info.get('netbox_name', f'NetBox-{ip_address}'),
                            'group': ip_info.get('netbox_site', 'NetBox Exports')
                        })
                        
                        if scan_result['success']:
                            export_record.export_status = 'scan_triggered'
                            export_record.scan_triggered_at = django_timezone.now()
                            export_record.wug_scan_id = scan_result.get('scan_id', '')
                            
                            self.logger.info(f"Successfully triggered scan for IP {ip_address}")
                        else:
                            raise Exception(f"Scan failed: {scan_result.get('message', 'Unknown error')}")
                    
                    except Exception as scan_error:
                        export_record.export_status = 'error'
                        export_record.error_message = f"Both device add and scan failed: {str(scan_error)}"
                        self.logger.error(f"Failed to scan IP {ip_address}: {str(scan_error)}")
                        
                        export_record.save()
                        return {
                            'success': False,
                            'ip_address': ip_address,
                            'error': export_record.error_message
                        }
                else:
                    export_record.export_status = 'error'
                    export_record.error_message = f"Device addition failed and scanning disabled: {str(e)}"
                    
                    export_record.save()
                    return {
                        'success': False,
                        'ip_address': ip_address,
                        'error': export_record.error_message
                    }
            
            export_record.save()
            
            return {
                'success': True,
                'ip_address': ip_address,
                'export_status': export_record.export_status,
                'wug_device_id': export_record.wug_device_id,
                'scan_id': export_record.wug_scan_id
            }
            
        except Exception as e:
            # Update export record with error
            if 'export_record' in locals():
                export_record.export_status = 'error'
                export_record.error_message = str(e)
                export_record.save()
            
            return {
                'success': False,
                'ip_address': ip_address,
                'error': str(e)
            }


class WUGScanStatusUpdateJob(JobRunner):
    """
    Job to update the status of WUG scans triggered from NetBox exports
    """
    
    class Meta:
        name = "Update WUG Scan Status"
        description = "Check and update status of WhatsUp Gold scans triggered from NetBox"
    
    def run(self, connection_id: int = None, **kwargs):
        """
        Check scan status for pending scans
        
        Args:
            connection_id: Specific connection to check (None for all)
        """
        from .models import NetBoxIPExport
        
        self.logger.info("Starting WUG scan status update job")
        
        # Get connections to check
        if connection_id:
            connections = WUGConnection.objects.filter(id=connection_id, is_active=True)
        else:
            connections = WUGConnection.objects.filter(is_active=True)
        
        updated_count = 0
        
        for connection in connections:
            # Get exports with pending scans
            pending_scans = NetBoxIPExport.objects.filter(
                connection=connection,
                export_status='scan_triggered',
                wug_scan_id__isnull=False
            )
            
            if not pending_scans.exists():
                continue
            
            try:
                with WUGAPIClient(
                    host=connection.host,
                    port=connection.port,
                    username=connection.username,
                    password=connection.password,
                    use_ssl=connection.use_ssl,
                    verify_ssl=connection.verify_ssl
                ) as wug_client:
                    
                    for export_record in pending_scans:
                        try:
                            # Check scan status
                            scan_status = wug_client.get_scan_status(export_record.wug_scan_id)
                            
                            export_record.wug_scan_status = scan_status.get('status', '')
                            
                            if scan_status.get('status') == 'completed':
                                export_record.export_status = 'scan_completed'
                                export_record.scan_completed_at = django_timezone.now()
                                
                                # Check if device was discovered
                                scan_results = wug_client.get_scan_results(export_record.wug_scan_id)
                                devices_found = scan_results.get('devices_found', [])
                                
                                if devices_found:
                                    export_record.wug_device_discovered = True
                                    # Try to find the device ID for our IP
                                    for device in devices_found:
                                        if device.get('ip_address') == export_record.ip_address:
                                            export_record.wug_device_id = device.get('device_id', '')
                                            break
                                
                                self.logger.info(
                                    f"Scan completed for IP {export_record.ip_address}: "
                                    f"{'device found' if export_record.wug_device_discovered else 'no device found'}"
                                )
                            
                            elif scan_status.get('status') == 'failed':
                                export_record.export_status = 'error'
                                export_record.error_message = f"WUG scan failed: {scan_status.get('error', 'Unknown error')}"
                            
                            export_record.save()
                            updated_count += 1
                            
                        except Exception as e:
                            self.logger.error(f"Failed to update scan status for {export_record.ip_address}: {str(e)}")
            
            except Exception as e:
                self.logger.error(f"Failed to check scans for connection {connection.name}: {str(e)}")
        
        self.logger.info(f"Updated status for {updated_count} scan operations")
        
        return {
            'scans_updated': updated_count
        }