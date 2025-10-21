# Generated migration to fix field name mismatches

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wug_sync', '0001_initial'),
    ]

    operations = [
        # Rename fields in WUGSyncLog to match current model
        migrations.RenameField(
            model_name='wugsynclog',
            old_name='started_at',
            new_name='start_time',
        ),
        migrations.RenameField(
            model_name='wugsynclog',
            old_name='completed_at',
            new_name='end_time',
        ),
        migrations.RenameField(
            model_name='wugsynclog',
            old_name='devices_processed',
            new_name='devices_discovered',
        ),
        migrations.RenameField(
            model_name='wugsynclog',
            old_name='errors',
            new_name='devices_errors',
        ),
        
        # Remove fields that don't exist in current model
        migrations.RemoveField(
            model_name='wugsynclog',
            name='error_details',
        ),
        migrations.RemoveField(
            model_name='wugsynclog',
            name='summary_data',
        ),
        migrations.RemoveField(
            model_name='wugsynclog',
            name='triggered_by',
        ),
        
        # Add new fields that exist in current model
        migrations.AddField(
            model_name='wugsynclog',
            name='error_message',
            field=models.TextField(blank=True, help_text='Error message if sync failed'),
        ),
        migrations.AddField(
            model_name='wugsynclog',
            name='summary',
            field=models.TextField(blank=True, help_text='Sync operation summary'),
        ),
        
        # Update choices for sync_type and status to match current model
        migrations.AlterField(
            model_name='wugsynclog',
            name='sync_type',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('scheduled', 'Scheduled'),
                    ('api', 'API Triggered'),
                ],
                help_text='Type of sync operation',
                max_length=20
            ),
        ),
        migrations.AlterField(
            model_name='wugsynclog',
            name='status',
            field=models.CharField(
                choices=[
                    ('running', 'Running'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                help_text='Sync operation status',
                max_length=20
            ),
        ),
        
        # Update ordering to use new field name
        migrations.AlterModelOptions(
            name='wugsynclog',
            options={'ordering': ['-start_time'], 'verbose_name': 'WUG Sync Log', 'verbose_name_plural': 'WUG Sync Logs'},
        ),
    ]