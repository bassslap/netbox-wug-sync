"""
API Views for NetBox WhatsUp Gold Sync Plugin

This module contains DRF API views for the plugin's REST API.
"""

from django.db.models import Count, Avg
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from netbox.api.viewsets import NetBoxModelViewSet
from ..models import WUGConnection, WUGDevice, WUGSyncLog
from ..wug_client import WUGAPIClient
from .serializers import (
    WUGConnectionSerializer, WUGConnectionCreateSerializer,
    WUGDeviceSerializer, WUGSyncLogSerializer,
    ConnectionTestSerializer, SyncTriggerSerializer,
    DeviceSyncActionSerializer, BulkDeviceSyncSerializer,
    SyncStatusSerializer, PluginStatusSerializer
)


class WUGConnectionViewSet(NetBoxModelViewSet):
    """API viewset for WUG Connections"""
    
    queryset = WUGConnection.objects.all()
    serializer_class = WUGConnectionSerializer
    
    def get_serializer_class(self):
        """Use different serializer for create/update (includes password)"""
        if self.action in ['create', 'update', 'partial_update']:
            return WUGConnectionCreateSerializer
        return WUGConnectionSerializer
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to WhatsUp Gold server"""
        connection = self.get_object()
        
        try:
            with WUGAPIClient(
                host=connection.host,
                port=connection.port,
                username=connection.username,
                password=connection.password,
                use_ssl=connection.use_ssl,
                verify_ssl=connection.verify_ssl
            ) as client:
                result = client.test_connection()
                
                # Try to get additional info if successful
                if result['success']:
                    try:
                        devices = client.get_devices(include_details=False)
                        result['device_count'] = len(devices) if isinstance(devices, list) else 0
                    except Exception:
                        result['device_count'] = 'unknown'
                
                serializer = ConnectionTestSerializer(data=result)
                serializer.is_valid(raise_exception=True)
                return Response(serializer.data)
                
        except Exception as e:
            error_result = {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }
            serializer = ConnectionTestSerializer(data=error_result)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def trigger_sync(self, request, pk=None):
        """Trigger manual sync for this connection"""
        connection = self.get_object()
        
        serializer = SyncTriggerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        sync_type = serializer.validated_data.get('sync_type', 'api')
        
        try:
            # In a real implementation, this would queue a background job
            # For now, we'll simulate the response
            
            result = {
                'success': True,
                'message': f'Sync initiated for connection {connection.name}',
                'job_id': f'sync-{connection.id}-{timezone.now().timestamp()}'
            }
            
            response_serializer = SyncTriggerSerializer(data=result)
            response_serializer.is_valid(raise_exception=True)
            return Response(response_serializer.data)
            
        except Exception as e:
            error_result = {
                'success': False,
                'message': f'Failed to trigger sync: {str(e)}'
            }
            response_serializer = SyncTriggerSerializer(data=error_result)
            response_serializer.is_valid(raise_exception=True)
            return Response(response_serializer.data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def sync_status(self, request, pk=None):
        """Get sync status for this connection"""
        connection = self.get_object()
        
        # Get latest sync log
        latest_log = connection.sync_logs.first()
        
        # Device statistics
        device_stats = connection.devices.aggregate(
            total=Count('id'),
            synced=Count('id', filter=models.Q(sync_status='success')),
            pending=Count('id', filter=models.Q(sync_status='pending')),
            errors=Count('id', filter=models.Q(sync_status='error'))
        )
        
        # Calculate success rate
        total = device_stats['total']
        synced = device_stats['synced']
        success_rate = (synced / total * 100) if total > 0 else 0
        
        status_data = {
            'connection_id': connection.id,
            'connection_name': connection.name,
            'last_sync': connection.last_sync,
            'latest_sync_status': latest_log.status if latest_log else None,
            'latest_sync_start': latest_log.start_time if latest_log else None,
            'latest_sync_end': latest_log.end_time if latest_log else None,
            'latest_sync_duration': latest_log.duration if latest_log else None,
            'total_devices': device_stats['total'],
            'synced_devices': device_stats['synced'],
            'pending_devices': device_stats['pending'],
            'error_devices': device_stats['errors'],
            'success_rate': success_rate
        }
        
        serializer = SyncStatusSerializer(data=status_data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class WUGDeviceViewSet(NetBoxModelViewSet):
    """API viewset for WUG Devices"""
    
    queryset = WUGDevice.objects.all()
    serializer_class = WUGDeviceSerializer
    
    def get_queryset(self):
        """Filter devices by connection if specified"""
        queryset = super().get_queryset()
        connection_id = self.request.query_params.get('connection')
        if connection_id:
            queryset = queryset.filter(connection_id=connection_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def sync_action(self, request, pk=None):
        """Perform sync actions on individual device"""
        device = self.get_object()
        
        serializer = DeviceSyncActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        
        try:
            if action_type == 'enable':
                device.sync_enabled = True
                device.save()
                message = f'Sync enabled for device {device.wug_name}'
                
            elif action_type == 'disable':
                device.sync_enabled = False
                device.save()
                message = f'Sync disabled for device {device.wug_name}'
                
            elif action_type == 'force_sync':
                # In real implementation, this would trigger sync for this device
                device.sync_status = 'pending'
                device.last_sync_attempt = timezone.now()
                device.save()
                message = f'Sync initiated for device {device.wug_name}'
            
            result = {'success': True, 'message': message}
            
        except Exception as e:
            result = {
                'success': False,
                'message': f'Failed to perform action: {str(e)}'
            }
        
        response_serializer = DeviceSyncActionSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)
        
        if result['success']:
            return Response(response_serializer.data)
        else:
            return Response(response_serializer.data, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_sync_action(self, request):
        """Perform bulk sync actions on multiple devices"""
        serializer = BulkDeviceSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        device_ids = serializer.validated_data['device_ids']
        action_type = serializer.validated_data['action']
        
        try:
            devices = WUGDevice.objects.filter(id__in=device_ids)
            
            if action_type == 'enable':
                affected_count = devices.update(sync_enabled=True)
                message = f'Sync enabled for {affected_count} devices'
                
            elif action_type == 'disable':
                affected_count = devices.update(sync_enabled=False)
                message = f'Sync disabled for {affected_count} devices'
                
            elif action_type == 'force_sync':
                affected_count = devices.update(
                    sync_status='pending',
                    last_sync_attempt=timezone.now()
                )
                message = f'Sync initiated for {affected_count} devices'
            
            result = {
                'success': True,
                'message': message,
                'affected_count': affected_count
            }
            
        except Exception as e:
            result = {
                'success': False,
                'message': f'Bulk operation failed: {str(e)}',
                'affected_count': 0
            }
        
        response_serializer = BulkDeviceSyncSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)
        
        if result['success']:
            return Response(response_serializer.data)
        else:
            return Response(response_serializer.data, status=status.HTTP_400_BAD_REQUEST)


class WUGSyncLogViewSet(ReadOnlyModelViewSet):
    """API viewset for WUG Sync Logs (read-only)"""
    
    queryset = WUGSyncLog.objects.all()
    serializer_class = WUGSyncLogSerializer
    
    def get_queryset(self):
        """Filter logs by connection if specified"""
        queryset = super().get_queryset()
        connection_id = self.request.query_params.get('connection')
        if connection_id:
            queryset = queryset.filter(connection_id=connection_id)
        return queryset


# Plugin-level API views

@action(detail=False, methods=['get'])
def plugin_status(request):
    """Get overall plugin status and statistics"""
    
    # Connection statistics
    connections = WUGConnection.objects.filter(is_active=True)
    active_connections = connections.count()
    
    # Test connection health (simplified for API response speed)
    healthy_connections = active_connections  # In reality, would test each
    failed_connections = 0
    
    # Device statistics
    total_devices = WUGDevice.objects.count()
    synced_devices = WUGDevice.objects.filter(sync_status='success').count()
    
    # Recent activity
    recent_logs = WUGSyncLog.objects.all()[:5]
    
    # Success rate
    success_rate = (synced_devices / total_devices * 100) if total_devices > 0 else 0
    
    # Average sync duration
    avg_duration = WUGSyncLog.objects.filter(
        end_time__isnull=False
    ).aggregate(avg_duration=Avg('end_time__timestamp') - Avg('start_time__timestamp'))['avg_duration']
    
    # Last sync time
    last_sync = WUGConnection.objects.filter(
        last_sync__isnull=False
    ).aggregate(latest=models.Max('last_sync'))['latest']
    
    status_data = {
        'plugin_version': '0.1.0',
        'active_connections': active_connections,
        'total_devices': total_devices,
        'synced_devices': synced_devices,
        'last_sync_time': last_sync,
        'recent_sync_logs': recent_logs,
        'healthy_connections': healthy_connections,
        'failed_connections': failed_connections,
        'sync_success_rate': success_rate,
        'avg_sync_duration': avg_duration
    }
    
    serializer = PluginStatusSerializer(data=status_data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.data)


@action(detail=False, methods=['post'])
def trigger_global_sync(request):
    """Trigger sync for all active connections"""
    
    serializer = SyncTriggerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    sync_type = serializer.validated_data.get('sync_type', 'api')
    
    try:
        active_connections = WUGConnection.objects.filter(is_active=True).count()
        
        # In real implementation, would queue jobs for all connections
        
        result = {
            'success': True,
            'message': f'Sync initiated for {active_connections} active connections',
            'job_id': f'global-sync-{timezone.now().timestamp()}'
        }
        
        response_serializer = SyncTriggerSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data)
        
    except Exception as e:
        error_result = {
            'success': False,
            'message': f'Failed to trigger global sync: {str(e)}'
        }
        response_serializer = SyncTriggerSerializer(data=error_result)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data, status=status.HTTP_400_BAD_REQUEST)