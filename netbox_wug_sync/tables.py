"""
Django Tables2 table definitions for NetBox WhatsUp Gold Sync Plugin

This module contains table classes for displaying plugin data in list views.
"""

import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from netbox.tables import NetBoxTable, BooleanColumn, ChoiceFieldColumn
from .models import WUGConnection, WUGDevice, WUGSyncLog


class WUGConnectionTable(NetBoxTable):
    """Table for displaying WUG Connections"""
    
    name = tables.LinkColumn(
        'plugins:netbox_wug_sync:wugconnection',
        args=[tables.A('pk')],
        verbose_name='Name'
    )
    
    host = tables.Column(
        verbose_name='Host'
    )
    
    port = tables.Column(
        verbose_name='Port'
    )
    
    is_active = BooleanColumn(
        verbose_name='Active'
    )
    
    use_ssl = BooleanColumn(
        verbose_name='SSL'
    )
    
    last_sync = tables.DateTimeColumn(
        verbose_name='Last Sync',
        format='M d, Y H:i'
    )
    
    sync_interval_minutes = tables.Column(
        verbose_name='Sync Interval (min)'
    )
    
    actions = tables.TemplateColumn(
        template_code='''
        <div class="btn-group btn-group-sm" role="group">
            <a href="{% url 'plugins:netbox_wug_sync:wugconnection_edit' pk=record.pk %}" 
               class="btn btn-outline-warning btn-sm" title="Edit">
                <i class="mdi mdi-pencil"></i>
            </a>
            <button onclick="testConnection({{ record.pk }})" 
                    class="btn btn-outline-primary btn-sm" title="Test Connection">
                <i class="mdi mdi-connection"></i>
            </button>
            <button onclick="triggerSync({{ record.pk }})" 
                    class="btn btn-outline-success btn-sm" title="Trigger Sync">
                <i class="mdi mdi-sync"></i>
            </button>
        </div>
        ''',
        verbose_name='Actions',
        orderable=False
    )

    class Meta(NetBoxTable.Meta):
        model = WUGConnection
        fields = (
            'pk', 'name', 'host', 'port', 'is_active', 'use_ssl', 
            'last_sync', 'sync_interval_minutes', 'actions'
        )
        default_columns = (
            'name', 'host', 'port', 'is_active', 'use_ssl', 
            'last_sync', 'sync_interval_minutes', 'actions'
        )


class WUGDeviceTable(NetBoxTable):
    """Table for displaying WUG Devices"""
    
    name = tables.LinkColumn(
        'plugins:netbox_wug_sync:wugdevice',
        args=[tables.A('pk')],
        verbose_name='Device Name'
    )
    
    wug_connection = tables.LinkColumn(
        'plugins:netbox_wug_sync:wugconnection',
        args=[tables.A('wug_connection.pk')],
        verbose_name='WUG Server',
        accessor='wug_connection.name'
    )
    
    netbox_device = tables.LinkColumn(
        'dcim:device',
        args=[tables.A('netbox_device.pk')],
        verbose_name='NetBox Device',
        accessor='netbox_device.name'
    )
    
    device_type = tables.Column(
        verbose_name='Device Type'
    )
    
    ip_address = tables.Column(
        verbose_name='IP Address'
    )
    
    sync_enabled = BooleanColumn(
        verbose_name='Sync Enabled'
    )
    
    last_sync = tables.DateTimeColumn(
        verbose_name='Last Sync',
        format='M d, Y H:i'
    )
    
    sync_status = ChoiceFieldColumn(
        verbose_name='Status'
    )
    
    actions = tables.TemplateColumn(
        template_code='''
        <div class="btn-group btn-group-sm" role="group">
            <a href="{% url 'plugins:netbox_wug_sync:wugdevice_edit' pk=record.pk %}" 
               class="btn btn-outline-warning btn-sm" title="Edit">
                <i class="mdi mdi-pencil"></i>
            </a>
            {% if record.netbox_device %}
            <a href="{% url 'dcim:device' pk=record.netbox_device.pk %}" 
               class="btn btn-outline-info btn-sm" title="View in NetBox">
                <i class="mdi mdi-open-in-new"></i>
            </a>
            {% endif %}
        </div>
        ''',
        verbose_name='Actions',
        orderable=False
    )

    class Meta(NetBoxTable.Meta):
        model = WUGDevice
        fields = (
            'pk', 'name', 'wug_connection', 'netbox_device', 'device_type',
            'ip_address', 'sync_enabled', 'last_sync', 'sync_status', 'actions'
        )
        default_columns = (
            'name', 'wug_connection', 'netbox_device', 'device_type',
            'ip_address', 'sync_enabled', 'last_sync', 'sync_status', 'actions'
        )


class WUGSyncLogTable(NetBoxTable):
    """Table for displaying WUG Sync Logs"""
    
    connection = tables.LinkColumn(
        'plugins:netbox_wug_sync:wugconnection',
        args=[tables.A('connection.pk')],
        verbose_name='Connection',
        accessor='connection.name'
    )
    
    sync_type = ChoiceFieldColumn(
        verbose_name='Type'
    )
    
    status = ChoiceFieldColumn(
        verbose_name='Status'
    )
    
    start_time = tables.DateTimeColumn(
        verbose_name='Started',
        format='M d, Y H:i:s'
    )
    
    end_time = tables.DateTimeColumn(
        verbose_name='Completed',
        format='M d, Y H:i:s'
    )
    
    duration = tables.Column(
        verbose_name='Duration',
        accessor='duration'
    )
    
    devices_discovered = tables.Column(
        verbose_name='Discovered'
    )
    
    devices_created = tables.Column(
        verbose_name='Created'
    )
    
    devices_updated = tables.Column(
        verbose_name='Updated'
    )
    
    devices_errors = tables.Column(
        verbose_name='Errors'
    )
    
    message = tables.Column(
        verbose_name='Message',
        attrs={'td': {'class': 'text-truncate', 'style': 'max-width: 200px;'}}
    )
    
    actions = tables.TemplateColumn(
        template_code='''
        <div class="btn-group btn-group-sm" role="group">
            <a href="{% url 'plugins:netbox_wug_sync:wugsynclog' pk=record.pk %}" 
               class="btn btn-outline-info btn-sm" title="View Details">
                <i class="mdi mdi-eye"></i>
            </a>
        </div>
        ''',
        verbose_name='Actions',
        orderable=False
    )

    class Meta(NetBoxTable.Meta):
        model = WUGSyncLog
        fields = (
            'pk', 'connection', 'sync_type', 'status', 'start_time', 'end_time',
            'duration', 'devices_discovered', 'devices_created', 'devices_updated',
            'devices_errors', 'message', 'actions'
        )
        default_columns = (
            'connection', 'sync_type', 'status', 'start_time', 'duration',
            'devices_discovered', 'devices_created', 'devices_updated', 'devices_errors', 'actions'
        )