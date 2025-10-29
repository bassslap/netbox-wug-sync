"""
Views for NetBox WhatsUp Gold Sync Plugin

This module contains Django views for the plugin's web interface.
"""

import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from netbox.views import generic
from .models import WUGConnection, WUGDevice, WUGSyncLog
from .forms import WUGConnectionForm
from .tables import WUGConnectionTable, WUGDeviceTable, WUGSyncLogTable


logger = logging.getLogger(__name__)
from .jobs import WUGSyncJob, WUGConnectionTestJob
from .wug_client import WUGAPIClient


class WUGConnectionListView(generic.ObjectListView):
    """List view for WUG Connections"""
    
    model = WUGConnection
    queryset = WUGConnection.objects.all()
    table = WUGConnectionTable
    template_name = 'netbox_wug_sync/wugconnection_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'WhatsUp Gold Connections'
        return context


class WUGConnectionDetailView(generic.ObjectView):
    """Detail view for WUG Connection"""
    
    model = WUGConnection
    queryset = WUGConnection.objects.all()
    template_name = 'netbox_wug_sync/wugconnection_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        connection = self.get_object()
        
        # Get recent sync logs
        context['recent_logs'] = connection.sync_logs.all()[:10]
        
        # Get device statistics
        context['device_stats'] = {
            'total': connection.devices.count(),
            'synced': connection.devices.filter(sync_status='success').count(),
            'pending': connection.devices.filter(sync_status='pending').count(),
            'errors': connection.devices.filter(sync_status='error').count(),
        }
        
        return context


class WUGConnectionCreateView(generic.ObjectEditView):
    """Create view for WUG Connection"""
    
    model = WUGConnection
    queryset = WUGConnection.objects.all()
    form = WUGConnectionForm
    template_name = 'netbox_wug_sync/wugconnection_edit.html'
    
    def get_success_url(self):
        return reverse('plugins:netbox_wug_sync:wugconnection', kwargs={'pk': self.object.pk})


class WUGConnectionEditView(generic.ObjectEditView):
    """Edit view for WUG Connection"""
    
    model = WUGConnection
    queryset = WUGConnection.objects.all()
    form = WUGConnectionForm
    template_name = 'netbox_wug_sync/wugconnection_edit.html'
    
    def get_success_url(self):
        return reverse('plugins:netbox_wug_sync:wugconnection', kwargs={'pk': self.object.pk})


class WUGConnectionDeleteView(generic.ObjectDeleteView):
    """Delete view for WUG Connection"""
    
    model = WUGConnection
    queryset = WUGConnection.objects.all()
    template_name = 'netbox_wug_sync/wugconnection_delete.html'


class WUGDeviceListView(generic.ObjectListView):
    """List view for WUG Devices"""
    
    model = WUGDevice
    queryset = WUGDevice.objects.all()
    table = WUGDeviceTable
    template_name = 'netbox_wug_sync/wugdevice_list.html'
    filterset_class = None  # Would define custom filters
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'WhatsUp Gold Devices'
        return context


class WUGDeviceDetailView(generic.ObjectView):
    """Detail view for WUG Device"""
    
    model = WUGDevice
    queryset = WUGDevice.objects.all()
    template_name = 'netbox_wug_sync/wugdevice_detail.html'


class WUGSyncLogListView(generic.ObjectListView):
    """List view for WUG Sync Logs"""
    
    model = WUGSyncLog
    queryset = WUGSyncLog.objects.all()
    table = WUGSyncLogTable
    template_name = 'netbox_wug_sync/wugsynclog_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Sync Logs'
        return context


class WUGSyncLogDetailView(generic.ObjectView):
    """Detail view for WUG Sync Log"""
    
    model = WUGSyncLog
    queryset = WUGSyncLog.objects.all()
    template_name = 'netbox_wug_sync/wugsynclog_detail.html'


# AJAX and API Views

def test_connection_view(request, pk):
    """AJAX view to test WUG connection"""
    
    if not request.user.has_perm('netbox_wug_sync.view_wugconnection'):
        raise PermissionDenied
    
    connection = get_object_or_404(WUGConnection, pk=pk)
    
    try:
        # Test the connection using the API client
        with WUGAPIClient(
            host=connection.host,
            port=connection.port,
            username=connection.username,
            password=connection.password,
            use_ssl=connection.use_ssl,
            verify_ssl=connection.verify_ssl
        ) as client:
            result = client.test_connection()
            
            if result['success']:
                # Try to get additional info
                try:
                    devices = client.get_devices(include_details=False)
                    device_count = len(devices) if isinstance(devices, list) else 0
                    result['device_count'] = device_count
                except Exception:
                    result['device_count'] = 'unknown'
            
            return JsonResponse(result)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        })


def trigger_sync_view(request, pk):
    """AJAX view to trigger manual sync"""
    
    # More permissive permission check for debugging
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    if request.method not in ['POST', 'GET']:  # Allow GET for debugging
        return JsonResponse({
            'error': f'Method {request.method} not allowed. POST required.',
            'method': request.method,
            'path': request.path
        }, status=405)
    
    connection = get_object_or_404(WUGConnection, pk=pk)
    
    try:
        if request.method == 'GET':
            return JsonResponse({
                'message': f'Sync endpoint for {connection.name} is accessible (GET test)',
                'connection_id': pk,
                'connection_name': connection.name,
                'debug_version': 'v2.0-debug-detailed-sync'  # Version identifier
            })
        
        # Simple debug sync approach
        logger.info(f"Starting debug sync for connection {connection.name}")
        
        try:
            # Call the actual sync function instead of just discovering devices
            from .sync_utils import sync_wug_connection
            from datetime import datetime
            
            logger.info(f"Calling sync_wug_connection for {connection.name}")
            
            # Call the actual sync function
            result = sync_wug_connection(connection, sync_type='manual')
            
            logger.info(f"Sync result: {result}")
            
            if result['success']:
                messages.success(
                    request, 
                    f"Sync completed! {result['message']}"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': result['message'],
                    'devices_synced': result.get('devices_synced', 0),
                    'devices_discovered': result.get('devices_discovered', 0),
                    'errors': result.get('errors', 0)
                })
            else:
                messages.error(request, f"Sync failed: {result['message']}")
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
                
        except ImportError as import_error:
            error_msg = f"Import error: {str(import_error)}"
            logger.error(error_msg)
            messages.error(request, error_msg)
            return JsonResponse({
                'success': False,
                'message': error_msg
            })
            
        except Exception as sync_error:
            error_msg = f"Sync error: {str(sync_error)}"
            logger.error(f"Sync error: {error_msg}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            messages.error(request, error_msg)
            return JsonResponse({
                'success': False,
                'message': error_msg
            })
        
    except Exception as e:
        error_msg = f"View error: {str(e)}"
        logger.error(f"Error in trigger_sync_view: {error_msg}")
        messages.error(request, error_msg)
        return JsonResponse({
            'success': False,
            'message': error_msg
        })


def sync_status_view(request, pk):
    """AJAX view to get sync status"""
    
    connection = get_object_or_404(WUGConnection, pk=pk)
    
    # Get latest sync log
    latest_log = connection.sync_logs.first()
    
    if latest_log:
        data = {
            'status': latest_log.status,
            'start_time': latest_log.start_time.isoformat(),
            'end_time': latest_log.end_time.isoformat() if latest_log.end_time else None,
            'devices_discovered': latest_log.devices_discovered,
            'devices_created': latest_log.devices_created,
            'devices_updated': latest_log.devices_updated,
            'devices_errors': latest_log.devices_errors,
            'success_rate': latest_log.success_rate,
            'summary': latest_log.summary
        }
    else:
        data = {
            'status': 'none',
            'message': 'No sync logs found'
        }
    
    return JsonResponse(data)


def dashboard_view(request):
    """Dashboard view showing sync overview"""
    
    context = {
        'title': 'WhatsUp Gold Sync Dashboard',
        'connections': WUGConnection.objects.filter(is_active=True),
        'total_devices': WUGDevice.objects.count(),
        'synced_devices': WUGDevice.objects.filter(sync_status='success').count(),
        'pending_devices': WUGDevice.objects.filter(sync_status='pending').count(),
        'error_devices': WUGDevice.objects.filter(sync_status='error').count(),
        'recent_logs': WUGSyncLog.objects.all()[:10],
    }
    
    return render(request, 'netbox_wug_sync/dashboard.html', context)


# Device management views

def device_enable_sync_view(request, pk):
    """Enable sync for a specific device"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugdevice'):
        raise PermissionDenied
    
    device = get_object_or_404(WUGDevice, pk=pk)
    device.sync_enabled = True
    device.save()
    
    messages.success(request, f'Sync enabled for {device.wug_name}')
    return redirect('plugins:netbox_wug_sync:wugdevice', pk=device.pk)


def device_disable_sync_view(request, pk):
    """Disable sync for a specific device"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugdevice'):
        raise PermissionDenied
    
    device = get_object_or_404(WUGDevice, pk=pk)
    device.sync_enabled = False
    device.save()
    
    messages.success(request, f'Sync disabled for {device.wug_name}')
    return redirect('plugins:netbox_wug_sync:wugdevice', pk=device.pk)


def device_force_sync_view(request, pk):
    """Force sync for a specific device"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugdevice'):
        raise PermissionDenied
    
    device = get_object_or_404(WUGDevice, pk=pk)
    
    # In a real implementation, this would trigger a sync job for just this device
    device.sync_status = 'pending'
    device.last_sync_attempt = timezone.now()
    device.save()
    
    messages.success(request, f'Sync initiated for {device.wug_name}')
    return redirect('plugins:netbox_wug_sync:wugdevice', pk=device.pk)


# Bulk operations

def bulk_enable_sync_view(request):
    """Bulk enable sync for multiple devices"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugdevice'):
        raise PermissionDenied
    
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        if device_ids:
            count = WUGDevice.objects.filter(id__in=device_ids).update(sync_enabled=True)
            messages.success(request, f'Sync enabled for {count} devices')
    
    return redirect('plugins:netbox_wug_sync:wugdevice_list')


def bulk_disable_sync_view(request):
    """Bulk disable sync for multiple devices"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugdevice'):
        raise PermissionDenied
    
    if request.method == 'POST':
        device_ids = request.POST.getlist('device_ids')
        if device_ids:
            count = WUGDevice.objects.filter(id__in=device_ids).update(sync_enabled=False)
            messages.success(request, f'Sync disabled for {count} devices')
    
    return redirect('plugins:netbox_wug_sync:wugdevice_list')


# NetBox to WUG Export Views

def trigger_netbox_export_view(request, pk):
    """Trigger NetBox to WUG export for a connection"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugconnection'):
        raise PermissionDenied
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    connection = get_object_or_404(WUGConnection, pk=pk)
    
    try:
        # Use the new reverse sync functionality
        from .sync_utils import sync_netbox_to_wug
        from dcim.models import Device
        from dcim.choices import DeviceStatusChoices
        
        # Get all active NetBox devices with primary IP addresses
        devices = Device.objects.filter(
            status=DeviceStatusChoices.STATUS_ACTIVE,
            primary_ip4__isnull=False
        )
        
        logger.info(f"Starting NetBox to WUG export for connection {connection.name} - {devices.count()} candidate devices")
        
        # Call the sync function
        result = sync_netbox_to_wug(connection, devices.iterator())
        
        if result['success']:
            messages.success(request, f"NetBox export completed! {result['message']}")
            
            # Create sync log entry
            WUGSyncLog.objects.create(
                connection=connection,
                sync_type='netbox_to_wug',
                status='completed',
                start_time=timezone.now(),
                end_time=timezone.now(),
                devices_discovered=result.get('total_devices', 0),
                devices_created=result.get('devices_created', 0),
                devices_updated=result.get('devices_updated', 0),
                devices_errors=result.get('devices_failed', 0),
                summary=f"Manual NetBox export: {result['message']}"
            )
            
            return JsonResponse({
                'success': True,
                'message': result['message'],
                'devices_created': result.get('devices_created', 0),
                'devices_failed': result.get('devices_failed', 0),
                'total_devices': result.get('total_devices', 0)
            })
        else:
            messages.error(request, f"NetBox export failed: {result['message']}")
            
            # Create error sync log entry
            WUGSyncLog.objects.create(
                connection=connection,
                sync_type='netbox_to_wug',
                status='failed',
                start_time=timezone.now(),
                end_time=timezone.now(),
                devices_discovered=0,
                devices_created=0,
                devices_updated=0,
                devices_errors=1,
                summary=f"Manual NetBox export failed: {result['message']}"
            )
            
            return JsonResponse({
                'success': False,
                'message': result['message']
            })
        
    except Exception as e:
        error_msg = f"Failed to trigger NetBox export: {str(e)}"
        logger.error(error_msg)
        messages.error(request, error_msg)
        
        # Create error sync log entry
        WUGSyncLog.objects.create(
            connection=connection,
            sync_type='netbox_to_wug',
            status='error',
            start_time=timezone.now(),
            end_time=timezone.now(),
            devices_discovered=0,
            devices_created=0,
            devices_updated=0,
            devices_errors=1,
            summary=f"NetBox export exception: {error_msg}"
        )
        
        return JsonResponse({
            'success': False,
            'message': error_msg
        })


def sync_netbox_device_to_wug_view(request, device_id):
    """Sync a specific NetBox device to all active WUG connections"""
    
    if not request.user.has_perm('netbox_wug_sync.change_wugconnection'):
        raise PermissionDenied
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        from dcim.models import Device
        from .sync_utils import create_wug_device_from_netbox_data
        
        device = get_object_or_404(Device, pk=device_id)
        
        # Check if device is eligible for sync
        if not device.primary_ip4:
            return JsonResponse({
                'success': False,
                'message': f'Device {device.name} has no primary IPv4 address'
            })
        
        if device.status != 'active':
            return JsonResponse({
                'success': False,
                'message': f'Device {device.name} is not active (status: {device.status})'
            })
        
        # Get active WUG connections
        connections = WUGConnection.objects.filter(is_active=True)
        if not connections.exists():
            return JsonResponse({
                'success': False,
                'message': 'No active WUG connections found'
            })
        
        results = []
        for connection in connections:
            try:
                result = create_wug_device_from_netbox_data(device, connection)
                results.append({
                    'connection': connection.name,
                    'success': result['success'],
                    'message': result.get('error' if not result['success'] else 'message', ''),
                    'device_id': result.get('device_id')
                })
                
                if result['success']:
                    logger.info(f"Successfully synced device {device.name} to WUG connection {connection.name} (Device ID: {result.get('device_id')})")
                else:
                    logger.error(f"Failed to sync device {device.name} to WUG connection {connection.name}: {result.get('error')}")
            
            except Exception as e:
                error_msg = f"Exception syncing to {connection.name}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    'connection': connection.name,
                    'success': False,
                    'message': error_msg,
                    'device_id': None
                })
        
        # Check overall success
        successful_syncs = [r for r in results if r['success']]
        failed_syncs = [r for r in results if not r['success']]
        
        if successful_syncs:
            success_msg = f"Device {device.name} synced to {len(successful_syncs)} WUG connection(s)"
            if failed_syncs:
                success_msg += f" ({len(failed_syncs)} failed)"
            
            messages.success(request, success_msg)
            
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'results': results,
                'successful_connections': len(successful_syncs),
                'failed_connections': len(failed_syncs)
            })
        else:
            error_msg = f"Failed to sync device {device.name} to any WUG connections"
            messages.error(request, error_msg)
            
            return JsonResponse({
                'success': False,
                'message': error_msg,
                'results': results
            })
        
    except Exception as e:
        error_msg = f"Error syncing NetBox device: {str(e)}"
        logger.error(error_msg)
        messages.error(request, error_msg)
        
        return JsonResponse({
            'success': False,
            'message': error_msg
        })


def netbox_export_status_view(request, pk):
    """Get NetBox export status for a connection"""
    
    connection = get_object_or_404(WUGConnection, pk=pk)
    
    from .models import NetBoxIPExport
    
    # Get export statistics
    exports = NetBoxIPExport.objects.filter(connection=connection)
    
    stats = {
        'total_exports': exports.count(),
        'pending_exports': exports.filter(export_status='pending').count(),
        'completed_exports': exports.filter(export_status__in=['exported', 'scan_completed']).count(),
        'error_exports': exports.filter(export_status='error').count(),
        'scan_triggered': exports.filter(export_status='scan_triggered').count(),
    }
    
    # Recent export activity
    recent_exports = exports.order_by('-created')[:10]
    
    data = {
        'connection_id': connection.id,
        'connection_name': connection.name,
        'export_enabled': connection.enable_netbox_export,
        'last_export': connection.last_export.isoformat() if connection.last_export else None,
        'statistics': stats,
        'recent_exports': [
            {
                'ip_address': export.ip_address,
                'status': export.export_status,
                'created': export.created.isoformat(),
                'device_name': export.netbox_device.name if export.netbox_device else 'Unknown'
            }
            for export in recent_exports
        ]
    }
    
    return JsonResponse(data)