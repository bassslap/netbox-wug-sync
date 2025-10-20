"""
Django Admin Configuration for NetBox WhatsUp Gold Sync Plugin

This module configures the Django admin interface for managing WUG sync objects.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import WUGConnection, WUGDevice, WUGSyncLog


@admin.register(WUGConnection)
class WUGConnectionAdmin(admin.ModelAdmin):
    """Admin interface for WUG Connections"""
    
    list_display = [
        'name', 
        'host', 
        'port', 
        'is_active', 
        'last_sync',
        'device_count',
        'connection_status'
    ]
    
    list_filter = [
        'is_active',
        'use_ssl',
        'auto_create_sites',
        'auto_create_device_types',
        'created',
        'last_updated'
    ]
    
    search_fields = [
        'name',
        'host',
        'username'
    ]
    
    readonly_fields = [
        'created',
        'last_updated',
        'last_sync',
        'connection_test_result'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active')
        }),
        ('Connection Settings', {
            'fields': (
                'host', 
                'port', 
                'username', 
                'password',
                'use_ssl',
                'verify_ssl'
            )
        }),
        ('Sync Configuration', {
            'fields': (
                'sync_interval_minutes',
                'auto_create_sites',
                'auto_create_device_types',
                'default_device_role'
            )
        }),
        ('Status', {
            'fields': (
                'last_sync',
                'created',
                'last_updated',
                'connection_test_result'
            )
        })
    )
    
    actions = ['test_connection', 'trigger_sync']
    
    def device_count(self, obj):
        """Display count of associated devices"""
        count = obj.devices.count()
        if count > 0:
            url = reverse('admin:netbox_wug_sync_wugdevice_changelist')
            return format_html(
                '<a href="{}?connection__id__exact={}">{} devices</a>',
                url, obj.id, count
            )
        return "0 devices"
    device_count.short_description = "Devices"
    
    def connection_status(self, obj):
        """Display connection status indicator"""
        if obj.is_active:
            return format_html(
                '<span style="color: green;">●</span> Active'
            )
        else:
            return format_html(
                '<span style="color: red;">●</span> Inactive'
            )
    connection_status.short_description = "Status"
    
    def connection_test_result(self, obj):
        """Display connection test result (read-only field)"""
        # This would be populated by a custom view or AJAX call
        return "Click 'Test Connection' action to check"
    connection_test_result.short_description = "Connection Test"
    
    def test_connection(self, request, queryset):
        """Admin action to test connections"""
        for connection in queryset:
            # This would trigger a background job or AJAX call
            self.message_user(
                request,
                f"Connection test initiated for {connection.name}"
            )
    test_connection.short_description = "Test selected connections"
    
    def trigger_sync(self, request, queryset):
        """Admin action to trigger sync"""
        for connection in queryset:
            # This would trigger the sync job
            self.message_user(
                request,
                f"Sync initiated for {connection.name}"
            )
    trigger_sync.short_description = "Trigger sync for selected connections"


@admin.register(WUGDevice)
class WUGDeviceAdmin(admin.ModelAdmin):
    """Admin interface for WUG Devices"""
    
    list_display = [
        'wug_name',
        'wug_id',
        'connection',
        'netbox_device_link',
        'sync_status',
        'sync_enabled',
        'last_sync_success',
        'wug_ip_address'
    ]
    
    list_filter = [
        'connection',
        'sync_status',
        'sync_enabled',
        'wug_device_type',
        'wug_vendor',
        'wug_group',
        'created',
        'last_updated'
    ]
    
    search_fields = [
        'wug_name',
        'wug_display_name',
        'wug_id',
        'wug_ip_address',
        'wug_mac_address',
        'wug_vendor',
        'wug_model'
    ]
    
    readonly_fields = [
        'wug_id',
        'wug_raw_data_formatted',
        'sync_status',
        'last_sync_attempt',
        'last_sync_success',
        'sync_error_message',
        'created',
        'last_updated'
    ]
    
    fieldsets = (
        ('WUG Device Information', {
            'fields': (
                'wug_id',
                'wug_name',
                'wug_display_name',
                'wug_ip_address',
                'wug_mac_address'
            )
        }),
        ('Device Details', {
            'fields': (
                'wug_device_type',
                'wug_vendor',
                'wug_model',
                'wug_os_version',
                'wug_group',
                'wug_location',
                'wug_status',
                'wug_last_seen'
            )
        }),
        ('NetBox Integration', {
            'fields': (
                'connection',
                'netbox_device',
                'sync_enabled'
            )
        }),
        ('Sync Status', {
            'fields': (
                'sync_status',
                'last_sync_attempt',
                'last_sync_success',
                'sync_error_message'
            )
        }),
        ('Raw Data', {
            'fields': ('wug_raw_data_formatted',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'created',
                'last_updated'
            )
        })
    )
    
    actions = ['enable_sync', 'disable_sync', 'force_sync']
    
    def netbox_device_link(self, obj):
        """Display link to NetBox device if exists"""
        if obj.netbox_device:
            # In a real NetBox environment, this would link to the device detail page
            return format_html(
                '<a href="/dcim/devices/{}/edit/">{}</a>',
                obj.netbox_device.id,
                obj.netbox_device.name
            )
        return format_html(
            '<span style="color: gray;">Not synced</span>'
        )
    netbox_device_link.short_description = "NetBox Device"
    
    def wug_raw_data_formatted(self, obj):
        """Display formatted raw WUG data"""
        if obj.wug_raw_data:
            import json
            formatted = json.dumps(obj.wug_raw_data, indent=2)
            return format_html(
                '<pre style="font-size: 12px; max-height: 300px; overflow: auto;">{}</pre>',
                formatted
            )
        return "No raw data"
    wug_raw_data_formatted.short_description = "Raw WUG Data"
    
    def enable_sync(self, request, queryset):
        """Admin action to enable sync"""
        updated = queryset.update(sync_enabled=True)
        self.message_user(
            request,
            f"Enabled sync for {updated} devices"
        )
    enable_sync.short_description = "Enable sync for selected devices"
    
    def disable_sync(self, request, queryset):
        """Admin action to disable sync"""
        updated = queryset.update(sync_enabled=False)
        self.message_user(
            request,
            f"Disabled sync for {updated} devices"
        )
    disable_sync.short_description = "Disable sync for selected devices"
    
    def force_sync(self, request, queryset):
        """Admin action to force sync"""
        for device in queryset:
            # This would trigger sync for specific devices
            self.message_user(
                request,
                f"Sync initiated for {device.wug_name}"
            )
    force_sync.short_description = "Force sync for selected devices"


@admin.register(WUGSyncLog)
class WUGSyncLogAdmin(admin.ModelAdmin):
    """Admin interface for WUG Sync Logs"""
    
    list_display = [
        'id',
        'connection',
        'sync_type',
        'status',
        'start_time',
        'duration_display',
        'devices_processed',
        'success_rate_display'
    ]
    
    list_filter = [
        'connection',
        'sync_type',
        'status',
        'start_time'
    ]
    
    search_fields = [
        'connection__name',
        'summary',
        'error_message'
    ]
    
    readonly_fields = [
        'connection',
        'sync_type',
        'status',
        'start_time',
        'end_time',
        'duration_display',
        'devices_discovered',
        'devices_created',
        'devices_updated',
        'devices_skipped',
        'devices_errors',
        'success_rate_display',
        'error_message',
        'summary',
        'created'
    ]
    
    fieldsets = (
        ('Sync Information', {
            'fields': (
                'connection',
                'sync_type',
                'status',
                'start_time',
                'end_time',
                'duration_display'
            )
        }),
        ('Results', {
            'fields': (
                'devices_discovered',
                'devices_created',
                'devices_updated',
                'devices_skipped',
                'devices_errors',
                'success_rate_display'
            )
        }),
        ('Details', {
            'fields': (
                'summary',
                'error_message'
            )
        }),
        ('Timestamps', {
            'fields': ('created',)
        })
    )
    
    def has_add_permission(self, request):
        """Sync logs should not be manually created"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Sync logs should be read-only"""
        return False
    
    def duration_display(self, obj):
        """Display sync duration in human-readable format"""
        duration = obj.duration
        if duration is None:
            return "N/A"
        
        if duration < 60:
            return f"{duration:.1f}s"
        elif duration < 3600:
            minutes = duration / 60
            return f"{minutes:.1f}m"
        else:
            hours = duration / 3600
            return f"{hours:.1f}h"
    duration_display.short_description = "Duration"
    
    def devices_processed(self, obj):
        """Display total devices processed"""
        return obj.devices_discovered
    devices_processed.short_description = "Processed"
    
    def success_rate_display(self, obj):
        """Display success rate with color coding"""
        rate = obj.success_rate
        
        if rate >= 90:
            color = 'green'
        elif rate >= 70:
            color = 'orange'
        else:
            color = 'red'
            
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    success_rate_display.short_description = "Success Rate"