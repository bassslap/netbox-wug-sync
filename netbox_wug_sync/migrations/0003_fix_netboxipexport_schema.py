# Generated migration to fix NetBoxIPExport model schema

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0215_rackreservation_status'),
        ('netbox_wug_sync', '0002_fix_wugsynclog_fields'),
    ]

    operations = [
        # Drop the existing NetBoxIPExport table and recreate with new schema
        migrations.DeleteModel(
            name='NetBoxIPExport',
        ),
        
        # Recreate NetBoxIPExport with the correct schema for tracking individual exports
        migrations.CreateModel(
            name='NetBoxIPExport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(help_text='IP address exported from NetBox')),
                ('export_reason', models.CharField(
                    max_length=50,
                    choices=[
                        ('new_device', 'New Device'),
                        ('ip_change', 'IP Address Change'), 
                        ('manual', 'Manual Export'),
                        ('scheduled', 'Scheduled Export'),
                    ],
                    help_text='Reason for exporting this IP'
                )),
                ('export_status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending'),
                        ('exported', 'Exported'),
                        ('scan_triggered', 'Scan Triggered'),
                        ('scan_completed', 'Scan Completed'),
                        ('error', 'Error'),
                    ],
                    default='pending',
                    help_text='Current export status'
                )),
                ('wug_device_id', models.CharField(
                    max_length=50,
                    null=True,
                    blank=True,
                    help_text='WhatsUp Gold device ID if created'
                )),
                ('scan_requested_at', models.DateTimeField(
                    null=True,
                    blank=True,
                    help_text='When scan was requested in WUG'
                )),
                ('scan_completed_at', models.DateTimeField(
                    null=True,
                    blank=True,
                    help_text='When scan completed in WUG'
                )),
                ('error_message', models.TextField(
                    blank=True,
                    help_text='Error details if export failed'
                )),
                ('exported_data', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Data sent to WUG for this export'
                )),
                ('connection', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ip_exports',
                    to='netbox_wug_sync.wugconnection',
                    help_text='WUG connection this export belongs to'
                )),
                ('netbox_device', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    null=True,
                    blank=True,
                    related_name='wug_exports',
                    to='dcim.device',
                    help_text='Source NetBox device'
                )),
            ],
            options={
                'verbose_name': 'NetBox IP Export',
                'verbose_name_plural': 'NetBox IP Exports',
                'ordering': ['-created'],
            },
        ),
    ]