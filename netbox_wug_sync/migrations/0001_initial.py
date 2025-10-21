# Generated for netbox_wug_sync plugin

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import netbox.models.features


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('dcim', '0215_rackreservation_status'),
        ('extras', '0133_make_cf_minmax_decimal'),
    ]

    operations = [
        migrations.CreateModel(
            name='WUGConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('name', models.CharField(help_text='Friendly name for this WUG connection', max_length=100, unique=True)),
                ('host', models.CharField(help_text='WhatsUp Gold server hostname or IP address', max_length=255, validators=[django.core.validators.URLValidator()])),
                ('port', models.PositiveIntegerField(default=9644, help_text='WhatsUp Gold API port (default: 9644)')),
                ('username', models.CharField(help_text='WhatsUp Gold username for API access', max_length=100)),
                ('password', models.CharField(help_text='WhatsUp Gold password (stored encrypted)', max_length=255)),
                ('use_ssl', models.BooleanField(default=True, help_text='Use HTTPS for API connections')),
                ('verify_ssl', models.BooleanField(default=False, help_text='Verify SSL certificates')),
                ('is_active', models.BooleanField(default=True, help_text='Enable synchronization for this connection')),
                ('sync_interval_minutes', models.PositiveIntegerField(default=60, help_text='Sync interval in minutes')),
                ('auto_create_sites', models.BooleanField(default=True, help_text='Automatically create sites for WUG groups')),
                ('auto_create_device_types', models.BooleanField(default=True, help_text='Automatically create device types for unknown devices')),
                ('last_sync', models.DateTimeField(blank=True, help_text='Timestamp of last successful sync', null=True)),
                ('enable_netbox_export', models.BooleanField(default=False, help_text='Enable exporting NetBox IPs to WhatsUp Gold')),
                ('export_interval_minutes', models.PositiveIntegerField(default=180, help_text='Export interval in minutes for NetBox to WUG sync')),
                ('last_export', models.DateTimeField(blank=True, help_text='Timestamp of last successful NetBox export to WUG', null=True)),
                ('auto_scan_exported_ips', models.BooleanField(default=True, help_text='Automatically trigger WUG scans for exported IPs')),
                ('default_device_role', models.ForeignKey(blank=True, help_text='Default role for synced devices', null=True, on_delete=django.db.models.deletion.SET_NULL, to='dcim.devicerole')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'WUG Connection',
                'verbose_name_plural': 'WUG Connections',
                'ordering': ['name'],
            },
            bases=(netbox.models.features.ChangeLoggingMixin, netbox.models.features.CustomFieldsMixin, netbox.models.features.TagsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='WUGDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('wug_id', models.CharField(help_text='WhatsUp Gold device ID', max_length=50)),
                ('wug_name', models.CharField(help_text='Device name in WhatsUp Gold', max_length=255)),
                ('wug_display_name', models.CharField(blank=True, help_text='Device display name in WhatsUp Gold', max_length=255)),
                ('wug_ip_address', models.GenericIPAddressField(blank=True, help_text='Primary IP address in WhatsUp Gold', null=True)),
                ('wug_mac_address', models.CharField(blank=True, help_text='MAC address from WhatsUp Gold', max_length=17)),
                ('wug_device_type', models.CharField(blank=True, help_text='Device type from WhatsUp Gold', max_length=100)),
                ('wug_vendor', models.CharField(blank=True, help_text='Device vendor from WhatsUp Gold', max_length=100)),
                ('wug_model', models.CharField(blank=True, help_text='Device model from WhatsUp Gold', max_length=100)),
                ('wug_os_version', models.CharField(blank=True, help_text='OS version from WhatsUp Gold', max_length=255)),
                ('wug_group', models.CharField(blank=True, help_text='WhatsUp Gold group/category', max_length=255)),
                ('wug_location', models.CharField(blank=True, help_text='Location from WhatsUp Gold', max_length=255)),
                ('wug_status', models.CharField(blank=True, help_text='Status in WhatsUp Gold', max_length=50)),
                ('wug_last_seen', models.DateTimeField(blank=True, help_text='Last seen timestamp from WhatsUp Gold', null=True)),
                ('sync_enabled', models.BooleanField(default=True, help_text='Enable sync for this device')),
                ('last_sync_attempt', models.DateTimeField(blank=True, help_text='Last sync attempt timestamp', null=True)),
                ('last_sync_success', models.DateTimeField(blank=True, help_text='Last successful sync timestamp', null=True)),
                ('sync_status', models.CharField(choices=[('pending', 'Pending'), ('syncing', 'Syncing'), ('success', 'Success'), ('error', 'Error'), ('skipped', 'Skipped')], default='pending', help_text='Current sync status', max_length=20)),
                ('sync_error_message', models.TextField(blank=True, help_text='Last sync error message')),
                ('wug_raw_data', models.JSONField(blank=True, help_text='Raw device data from WhatsUp Gold API', null=True)),
                ('connection', models.ForeignKey(help_text='WUG connection this device belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='netbox_wug_sync.wugconnection')),
                ('netbox_device', models.ForeignKey(blank=True, help_text='Associated NetBox device', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wug_devices', to='dcim.device')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'WUG Device',
                'verbose_name_plural': 'WUG Devices',
                'ordering': ['wug_name'],
                'unique_together': {('connection', 'wug_id')},
            },
            bases=(netbox.models.features.ChangeLoggingMixin, netbox.models.features.CustomFieldsMixin, netbox.models.features.TagsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='WUGSyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('sync_type', models.CharField(choices=[('full', 'Full Sync'), ('incremental', 'Incremental'), ('export', 'NetBox Export')], default='incremental', help_text='Type of sync operation', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='pending', help_text='Sync operation status', max_length=20)),
                ('started_at', models.DateTimeField(help_text='When sync started')),
                ('completed_at', models.DateTimeField(blank=True, help_text='When sync completed', null=True)),
                ('devices_processed', models.PositiveIntegerField(default=0, help_text='Number of devices processed')),
                ('devices_created', models.PositiveIntegerField(default=0, help_text='Number of devices created in NetBox')),
                ('devices_updated', models.PositiveIntegerField(default=0, help_text='Number of devices updated in NetBox')),
                ('devices_skipped', models.PositiveIntegerField(default=0, help_text='Number of devices skipped')),
                ('errors', models.PositiveIntegerField(default=0, help_text='Number of errors encountered')),
                ('error_details', models.JSONField(blank=True, default=list, help_text='Detailed error information')),
                ('summary_data', models.JSONField(blank=True, default=dict, help_text='Summary statistics and metadata')),
                ('triggered_by', models.CharField(blank=True, help_text='User or system that triggered sync', max_length=100)),
                ('connection', models.ForeignKey(help_text='WUG connection for this sync', on_delete=django.db.models.deletion.CASCADE, related_name='sync_logs', to='netbox_wug_sync.wugconnection')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'WUG Sync Log',
                'verbose_name_plural': 'WUG Sync Logs',
                'ordering': ['-started_at'],
            },
            bases=(netbox.models.features.ChangeLoggingMixin, netbox.models.features.CustomFieldsMixin, netbox.models.features.TagsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='NetBoxIPExport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('name', models.CharField(help_text='Export configuration name', max_length=100, unique=True)),
                ('description', models.TextField(blank=True, help_text='Export description')),
                ('export_format', models.CharField(choices=[('json', 'JSON'), ('csv', 'CSV'), ('xml', 'XML')], default='json', help_text='Export file format', max_length=10)),
                ('include_devices', models.BooleanField(default=True, help_text='Include device IP addresses')),
                ('include_virtual_machines', models.BooleanField(default=True, help_text='Include VM IP addresses')),
                ('include_primary_only', models.BooleanField(default=False, help_text='Only export primary IP addresses')),
                ('include_management_only', models.BooleanField(default=False, help_text='Only export management interfaces')),
                ('exclude_inactive', models.BooleanField(default=True, help_text='Exclude inactive devices/VMs')),
                ('custom_fields_to_include', models.JSONField(blank=True, default=list, help_text='List of custom fields to include')),
                ('wug_connections', models.ManyToManyField(blank=True, help_text='Export to these WUG connections', related_name='ip_exports', to='netbox_wug_sync.wugconnection')),
                ('filter_sites', models.ManyToManyField(blank=True, help_text='Limit to these sites', related_name='ip_exports', to='dcim.site')),
                ('filter_device_roles', models.ManyToManyField(blank=True, help_text='Limit to these device roles', related_name='ip_exports', to='dcim.devicerole')),
                ('tags', models.ManyToManyField(blank=True, related_name='%(app_label)s_%(class)s_related', to='extras.tag')),
            ],
            options={
                'verbose_name': 'NetBox IP Export',
                'verbose_name_plural': 'NetBox IP Exports',
                'ordering': ['name'],
            },
            bases=(netbox.models.features.ChangeLoggingMixin, netbox.models.features.CustomFieldsMixin, netbox.models.features.TagsMixin, models.Model),
        ),
    ]
