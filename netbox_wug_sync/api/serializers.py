"""
API Serializers for NetBox WhatsUp Gold Sync Plugin

This module contains DRF serializers for the plugin's API endpoints.
"""

from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer

from ..models import WUGConnection, WUGDevice, WUGSyncLog


class WUGConnectionSerializer(NetBoxModelSerializer):
    """Serializer for WUGConnection model"""
    
    url = serializers.HyperlinkedIdentityField(
    view_name='plugins-api:netbox-wug-sync-api:wugconnection-detail'
    )
    
    device_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WUGConnection
        fields = [
            'id', 'url', 'display', 'name', 'host', 'port', 'username',
            'use_ssl', 'verify_ssl', 'is_active', 'sync_interval_minutes',
            'auto_create_sites', 'auto_create_device_types', 'default_device_role',
            'last_sync', 'device_count', 'created', 'last_updated'
        ]
    
    def get_device_count(self, obj):
        """Get count of associated devices"""
        return obj.devices.count()


class WUGConnectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating WUGConnection (includes password)"""
    
    class Meta:
        model = WUGConnection
        fields = [
            'name', 'host', 'port', 'username', 'password',
            'use_ssl', 'verify_ssl', 'is_active', 'sync_interval_minutes',
            'auto_create_sites', 'auto_create_device_types', 'default_device_role'
        ]
        extra_kwargs = {
            'password': {'write_only': True}
        }


class WUGDeviceSerializer(NetBoxModelSerializer):
    """Serializer for WUGDevice model"""
    
    url = serializers.HyperlinkedIdentityField(
    view_name='plugins-api:netbox-wug-sync-api:wugdevice-detail'
    )
    
    connection = serializers.StringRelatedField()
    netbox_device = serializers.StringRelatedField()
    
    class Meta:
        model = WUGDevice
        fields = [
            'id', 'url', 'display', 'wug_id', 'wug_name', 'wug_display_name',
            'wug_ip_address', 'wug_mac_address', 'wug_device_type', 'wug_vendor',
            'wug_model', 'wug_os_version', 'wug_group', 'wug_location',
            'wug_status', 'wug_last_seen', 'connection', 'netbox_device',
            'sync_enabled', 'sync_status', 'last_sync_attempt', 'last_sync_success',
            'sync_error_message', 'created', 'last_updated'
        ]


class WUGSyncLogSerializer(NetBoxModelSerializer):
    """Serializer for WUGSyncLog model"""
    
    url = serializers.HyperlinkedIdentityField(
    view_name='plugins-api:netbox-wug-sync-api:wugsynclog-detail'
    )
    
    connection = serializers.StringRelatedField()
    duration = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = WUGSyncLog
        fields = [
            'id', 'url', 'display', 'connection', 'sync_type', 'status',
            'start_time', 'end_time', 'duration', 'devices_discovered',
            'devices_created', 'devices_updated', 'devices_skipped',
            'devices_errors', 'success_rate', 'error_message', 'summary', 'created'
        ]
    
    def get_duration(self, obj):
        """Get sync duration in seconds"""
        return obj.duration
    
    def get_success_rate(self, obj):
        """Get sync success rate as percentage"""
        return obj.success_rate


# Nested serializers for related objects

class NestedWUGConnectionSerializer(serializers.ModelSerializer):
    """Nested serializer for WUGConnection references"""
    
    url = serializers.HyperlinkedIdentityField(
    view_name='plugins-api:netbox-wug-sync-api:wugconnection-detail'
    )
    
    class Meta:
        model = WUGConnection
        fields = ['id', 'url', 'display', 'name', 'host']


class NestedWUGDeviceSerializer(serializers.ModelSerializer):
    """Nested serializer for WUGDevice references"""
    
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_wug_sync-api:wugdevice-detail'
    )
    
    class Meta:
        model = WUGDevice
        fields = ['id', 'url', 'display', 'wug_name', 'wug_id', 'sync_status']


# Action serializers

class ConnectionTestSerializer(serializers.Serializer):
    """Serializer for connection test action"""
    
    success = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
    device_count = serializers.IntegerField(read_only=True, required=False)
    server_info = serializers.JSONField(read_only=True, required=False)


class SyncTriggerSerializer(serializers.Serializer):
    """Serializer for sync trigger action"""
    
    connection_id = serializers.IntegerField(required=False, help_text="Specific connection to sync")
    sync_type = serializers.ChoiceField(
        choices=['manual', 'api'],
        default='api',
        help_text="Type of sync operation"
    )
    
    success = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
    job_id = serializers.CharField(read_only=True, required=False)


class DeviceSyncActionSerializer(serializers.Serializer):
    """Serializer for device sync actions"""
    
    action = serializers.ChoiceField(
        choices=['enable', 'disable', 'force_sync'],
        help_text="Action to perform on device sync"
    )
    
    success = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)


class BulkDeviceSyncSerializer(serializers.Serializer):
    """Serializer for bulk device sync operations"""
    
    device_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of WUGDevice IDs to operate on"
    )
    
    action = serializers.ChoiceField(
        choices=['enable', 'disable', 'force_sync'],
        help_text="Action to perform on selected devices"
    )
    
    success = serializers.BooleanField(read_only=True)
    message = serializers.CharField(read_only=True)
    affected_count = serializers.IntegerField(read_only=True)


class SyncStatusSerializer(serializers.Serializer):
    """Serializer for sync status information"""
    
    connection_id = serializers.IntegerField()
    connection_name = serializers.CharField()
    last_sync = serializers.DateTimeField(allow_null=True)
    
    # Latest sync log info
    latest_sync_status = serializers.CharField(allow_null=True)
    latest_sync_start = serializers.DateTimeField(allow_null=True)
    latest_sync_end = serializers.DateTimeField(allow_null=True)
    latest_sync_duration = serializers.FloatField(allow_null=True)
    
    # Device statistics
    total_devices = serializers.IntegerField()
    synced_devices = serializers.IntegerField()
    pending_devices = serializers.IntegerField()
    error_devices = serializers.IntegerField()
    
    # Success rate
    success_rate = serializers.FloatField()


class PluginStatusSerializer(serializers.Serializer):
    """Serializer for overall plugin status"""
    
    plugin_version = serializers.CharField()
    active_connections = serializers.IntegerField()
    total_devices = serializers.IntegerField()
    synced_devices = serializers.IntegerField()
    last_sync_time = serializers.DateTimeField(allow_null=True)
    
    # Recent activity
    recent_sync_logs = WUGSyncLogSerializer(many=True)
    
    # Health status
    healthy_connections = serializers.IntegerField()
    failed_connections = serializers.IntegerField()
    
    # Statistics
    sync_success_rate = serializers.FloatField()
    avg_sync_duration = serializers.FloatField(allow_null=True)