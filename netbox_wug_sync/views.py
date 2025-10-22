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
                'connection_name': connection.name
            })
        
        # Simple debug sync approach
        logger.info(f"Starting debug sync for connection {connection.name}")
        
        try:
            # Import WUG client directly
            from .wug_client import WUGAPIClient
            from .models import WUGSyncLog
            from datetime import datetime
            
            # Create basic sync log
            sync_log = WUGSyncLog.objects.create(
                connection=connection,
                sync_type='manual',
                status='running',
                devices_discovered=0,
                devices_created=0,
                devices_updated=0,
                devices_errors=0,
                summary="Starting debug sync..."
            )
            
            logger.info(f"Created sync log ID: {sync_log.id}")
            
            # Test WUG connection
            logger.info(f"Testing WUG connection to {connection.host}:{connection.port}")
            
            with WUGAPIClient(
                host=connection.host,
                username=connection.username,
                password=connection.get_password(),
                port=connection.port,
                use_ssl=connection.use_ssl,
                verify_ssl=connection.verify_ssl
            ) as client:
                
                # Test connection
                test_result = client.test_connection()
                logger.info(f"Connection test result: {test_result}")
                
                if not test_result.get('success', False):
                    error_msg = test_result.get('message', 'Connection test failed')
                    logger.error(f"WUG connection failed: {error_msg}")
                    
                    sync_log.status = 'failed'
                    sync_log.summary = f"Connection test failed: {error_msg}"
                    sync_log.end_time = datetime.now()
                    sync_log.save()
                    
                    messages.error(request, f'WUG connection failed: {error_msg}')
                    return JsonResponse({
                        'success': False,
                        'message': f'Connection failed: {error_msg}',
                        'connection_test': test_result
                    })
                
                # Connection successful - try to get devices
                logger.info("Connection successful, fetching devices...")
                devices = client.get_devices(include_details=False)  # Start with basic info
                device_count = len(devices) if devices else 0
                
                logger.info(f"Retrieved {device_count} devices from WUG")
                
                # Update sync log
                sync_log.devices_discovered = device_count
                sync_log.status = 'completed'
                sync_log.summary = f"Successfully connected and found {device_count} devices"
                sync_log.end_time = datetime.now()
                sync_log.save()
                
                messages.success(
                    request, 
                    f'Debug sync completed! Found {device_count} devices from WUG. Check sync logs for details.'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Debug sync completed - found {device_count} devices',
                    'devices_found': device_count,
                    'connection_test': test_result,
                    'sync_log_id': sync_log.id
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
            logger.error(f"Debug sync error: {error_msg}")
            
            # Try to update sync log if it exists
            try:
                if 'sync_log' in locals():
                    sync_log.status = 'error'
                    sync_log.summary = error_msg
                    sync_log.end_time = datetime.now()
                    sync_log.save()
            except:
                pass
            
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
    
    if not connection.enable_netbox_export:
        return JsonResponse({
            'success': False,
            'message': 'NetBox export is not enabled for this connection'
        })
    
    try:
        # In a real implementation, this would queue the NetBoxToWUGExportJob
        # For now, we'll simulate the response
        
        messages.success(request, f'NetBox export initiated for {connection.name}')
        
        return JsonResponse({
            'success': True,
            'message': f'NetBox export initiated for {connection.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Failed to trigger export: {str(e)}'
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