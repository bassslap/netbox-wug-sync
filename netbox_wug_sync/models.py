from django.db import models
from django.urls import reverse
from django.core.validators import URLValidator
from netbox.models import NetBoxModel
from dcim.models import Device, Site, DeviceType, DeviceRole
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class WUGConnection(NetBoxModel):
    """Model to store WhatsUp Gold connection configurations"""
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Friendly name for this WUG connection"
    )
    
    host = models.CharField(
        max_length=255,
        validators=[URLValidator()],
        help_text="WhatsUp Gold server hostname or IP address"
    )
    
    port = models.PositiveIntegerField(
        default=9644,
        help_text="WhatsUp Gold API port (default: 9644)"
    )
    
    username = models.CharField(
        max_length=100,
        help_text="WhatsUp Gold username for API access"
    )
    
    password = models.CharField(
        max_length=255,
        help_text="WhatsUp Gold password (stored encrypted)"
    )
    
    use_ssl = models.BooleanField(
        default=True,
        help_text="Use HTTPS for API connections"
    )
    
    verify_ssl = models.BooleanField(
        default=False,
        help_text="Verify SSL certificates"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Enable synchronization for this connection"
    )
    
    sync_interval_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Sync interval in minutes"
    )
    
    auto_create_sites = models.BooleanField(
        default=True,
        help_text="Automatically create sites for WUG groups"
    )
    
    auto_create_device_types = models.BooleanField(
        default=True,
        help_text="Automatically create device types for unknown devices"
    )
    
    default_device_role = models.ForeignKey(
        DeviceRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Default role for synced devices"
    )
    
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful sync"
    )
    
    # NetBox to WUG export settings
    enable_netbox_export = models.BooleanField(
        default=False,
        help_text="Enable exporting NetBox IPs to WhatsUp Gold"
    )
    
    export_interval_minutes = models.PositiveIntegerField(
        default=180,  # 3 hours default
        help_text="Export interval in minutes for NetBox to WUG sync"
    )
    
    last_export = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful NetBox export to WUG"
    )
    
    auto_scan_exported_ips = models.BooleanField(
        default=True,
        help_text="Automatically trigger WUG scans for exported IPs"
    )
    
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'WUG Connection'
        verbose_name_plural = 'WUG Connections'

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"

    def get_absolute_url(self):
        if not self.pk:
            return '#'  # Return placeholder if no primary key
        return reverse('plugins:netbox_wug_sync:wugconnection', args=[self.pk])

    @property
    def api_url(self):
        """Return the full API URL for this connection"""
        protocol = 'https' if self.use_ssl else 'http'
        return f"{protocol}://{self.host}:{self.port}"


class WUGDevice(NetBoxModel):
    """Model to store WhatsUp Gold device information and sync status"""
    
    # WhatsUp Gold device information
    wug_id = models.CharField(
        max_length=50,
        help_text="WhatsUp Gold device ID"
    )
    
    wug_name = models.CharField(
        max_length=255,
        help_text="Device name in WhatsUp Gold"
    )
    
    wug_display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Device display name in WhatsUp Gold"
    )
    
    wug_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Primary IP address in WhatsUp Gold"
    )
    
    wug_mac_address = models.CharField(
        max_length=17,
        blank=True,
        help_text="MAC address from WhatsUp Gold"
    )
    
    wug_device_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device type from WhatsUp Gold"
    )
    
    wug_vendor = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device vendor from WhatsUp Gold"
    )
    
    wug_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="Device model from WhatsUp Gold"
    )
    
    wug_os_version = models.CharField(
        max_length=255,
        blank=True,
        help_text="OS version from WhatsUp Gold"
    )
    
    wug_group = models.CharField(
        max_length=255,
        blank=True,
        help_text="WhatsUp Gold group/category"
    )
    
    wug_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Location from WhatsUp Gold"
    )
    
    wug_status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status in WhatsUp Gold"
    )
    
    wug_last_seen = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last seen timestamp from WhatsUp Gold"
    )
    
    # NetBox relationship
    netbox_device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wug_devices',
        help_text="Associated NetBox device"
    )
    
    # Sync configuration
    connection = models.ForeignKey(
        WUGConnection,
        on_delete=models.CASCADE,
        related_name='devices',
        help_text="WUG connection this device belongs to"
    )
    
    sync_enabled = models.BooleanField(
        default=True,
        help_text="Enable sync for this device"
    )
    
    # Sync status tracking
    last_sync_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last sync attempt timestamp"
    )
    
    last_sync_success = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last successful sync timestamp"
    )
    
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('syncing', 'Syncing'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('skipped', 'Skipped'),
        ],
        default='pending',
        help_text="Current sync status"
    )
    
    sync_error_message = models.TextField(
        blank=True,
        help_text="Last sync error message"
    )
    
    # Raw WUG data for troubleshooting
    wug_raw_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw device data from WhatsUp Gold API"
    )
    
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['wug_name']
        verbose_name = 'WUG Device'
        verbose_name_plural = 'WUG Devices'
        unique_together = ['connection', 'wug_id']

    def __str__(self):
        return f"{self.wug_name} ({self.wug_id})"

    def get_absolute_url(self):
        if not self.pk:
            return '#'  # Return placeholder if no primary key
        return reverse('plugins:netbox_wug_sync:wugdevice', args=[self.pk])

    @property
    def is_synced(self):
        """Check if device is successfully synced to NetBox"""
        return self.netbox_device is not None and self.sync_status == 'success'

    @property
    def sync_age_minutes(self):
        """Return minutes since last successful sync"""
        if not self.last_sync_success:
            return None
        
        from django.utils import timezone
        delta = timezone.now() - self.last_sync_success
        return int(delta.total_seconds() / 60)


class WUGSyncLog(NetBoxModel):
    """Model to store sync operation logs"""
    
    connection = models.ForeignKey(
        WUGConnection,
        on_delete=models.CASCADE,
        related_name='sync_logs',
        help_text="WUG connection for this sync operation"
    )
    
    sync_type = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('scheduled', 'Scheduled'),
            ('api', 'API Triggered'),
        ],
        help_text="Type of sync operation"
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        help_text="Sync operation status"
    )
    
    start_time = models.DateTimeField(
        help_text="Sync start timestamp"
    )
    
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Sync end timestamp"
    )
    
    devices_discovered = models.PositiveIntegerField(
        default=0,
        help_text="Number of devices discovered in WUG"
    )
    
    devices_created = models.PositiveIntegerField(
        default=0,
        help_text="Number of new devices created in NetBox"
    )
    
    devices_updated = models.PositiveIntegerField(
        default=0,
        help_text="Number of devices updated in NetBox"
    )
    
    devices_skipped = models.PositiveIntegerField(
        default=0,
        help_text="Number of devices skipped during sync"
    )
    
    devices_errors = models.PositiveIntegerField(
        default=0,
        help_text="Number of devices with sync errors"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if sync failed"
    )
    
    summary = models.TextField(
        blank=True,
        help_text="Sync operation summary"
    )
    
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_time']
        verbose_name = 'WUG Sync Log'
        verbose_name_plural = 'WUG Sync Logs'

    def __str__(self):
        return f"Sync {self.id} - {self.connection.name} ({self.status})"

    def get_absolute_url(self):
        if not self.pk:
            return '#'  # Return placeholder if no primary key
        return reverse('plugins:netbox_wug_sync:wugsynclog', args=[self.pk])

    @property
    def duration(self):
        """Return sync duration in seconds"""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self):
        """Return sync success rate as percentage"""
        total = self.devices_discovered
        if total == 0:
            return 0
        success = self.devices_created + self.devices_updated
        return round((success / total) * 100, 2)


class NetBoxIPExport(NetBoxModel):
    """Model to track NetBox IP addresses exported to WhatsUp Gold"""
    
    connection = models.ForeignKey(
        WUGConnection,
        on_delete=models.CASCADE,
        related_name='ip_exports',
        help_text="WUG connection this export belongs to"
    )
    
    ip_address = models.GenericIPAddressField(
        help_text="IP address exported from NetBox"
    )
    
    netbox_device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wug_exports',
        help_text="Source NetBox device"
    )
    
    # Export metadata
    export_reason = models.CharField(
        max_length=50,
        choices=[
            ('new_device', 'New Device'),
            ('ip_change', 'IP Address Change'),
            ('manual', 'Manual Export'),
            ('scheduled', 'Scheduled Export'),
        ],
        help_text="Reason for exporting this IP"
    )
    
    export_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('exported', 'Exported'),
            ('scan_triggered', 'Scan Triggered'),
            ('scan_completed', 'Scan Completed'),
            ('error', 'Error'),
        ],
        default='pending',
        help_text="Current export status"
    )
    
    # WUG scan information
    wug_scan_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="WhatsUp Gold scan ID if scan was triggered"
    )
    
    wug_scan_status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Status of WUG scan operation"
    )
    
    wug_device_discovered = models.BooleanField(
        default=False,
        help_text="Whether WUG discovered a device at this IP"
    )
    
    wug_device_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="WUG device ID if device was discovered"
    )
    
    # Timestamps
    exported_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when IP was exported to WUG"
    )
    
    scan_triggered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when WUG scan was triggered"
    )
    
    scan_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when WUG scan completed"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if export/scan failed"
    )
    
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'NetBox IP Export'
        verbose_name_plural = 'NetBox IP Exports'
        unique_together = ['connection', 'ip_address']

    def __str__(self):
        device_name = 'Unknown'
        if self.netbox_device and hasattr(self.netbox_device, 'name') and self.netbox_device.name:
            device_name = self.netbox_device.name
        return f"{self.ip_address} ({device_name}) -> {self.connection.name}"

    def get_absolute_url(self):
        if not self.pk:
            return '#'  # Return placeholder if no primary key
        return reverse('plugins:netbox_wug_sync:netboxipexport', args=[self.pk])

    @property
    def is_completed(self):
        """Check if export and scan process is completed"""
        return self.export_status in ['scan_completed', 'exported']

    @property
    def total_duration(self):
        """Return total time from export to scan completion"""
        if self.exported_at and self.scan_completed_at:
            return (self.scan_completed_at - self.exported_at).total_seconds()
        return None