"""
URL Configuration for NetBox WhatsUp Gold Sync Plugin

This module defines URL patterns for the plugin's web interface and API endpoints.
"""

from django.urls import path, include

from . import views


app_name = 'netbox_wug_sync'

# Web interface URLs
urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),
    
    # WUG Connections
    path('connections/', views.WUGConnectionListView.as_view(), name='wugconnection_list'),
    path('connections/add/', views.WUGConnectionCreateView.as_view(), name='wugconnection_add'),
    path('connections/<int:pk>/', views.WUGConnectionDetailView.as_view(), name='wugconnection'),
    path('connections/<int:pk>/edit/', views.WUGConnectionEditView.as_view(), name='wugconnection_edit'),
    path('connections/<int:pk>/delete/', views.WUGConnectionDeleteView.as_view(), name='wugconnection_delete'),
    
    # Connection management actions
    path('connections/<int:pk>/test/', views.test_connection_view, name='wugconnection_test'),
    path('connections/<int:pk>/sync/', views.trigger_sync_view, name='wugconnection_sync'),
    path('connections/<int:pk>/status/', views.sync_status_view, name='wugconnection_status'),
    
    # WUG Devices
    path('devices/', views.WUGDeviceListView.as_view(), name='wugdevice_list'),
    path('devices/<int:pk>/', views.WUGDeviceDetailView.as_view(), name='wugdevice'),
    
    # Device management actions
    path('devices/<int:pk>/enable-sync/', views.device_enable_sync_view, name='wugdevice_enable_sync'),
    path('devices/<int:pk>/disable-sync/', views.device_disable_sync_view, name='wugdevice_disable_sync'),
    path('devices/<int:pk>/force-sync/', views.device_force_sync_view, name='wugdevice_force_sync'),
    
    # Bulk device operations
    path('devices/bulk/enable-sync/', views.bulk_enable_sync_view, name='wugdevice_bulk_enable'),
    path('devices/bulk/disable-sync/', views.bulk_disable_sync_view, name='wugdevice_bulk_disable'),
    
    # Sync Logs
    path('logs/', views.WUGSyncLogListView.as_view(), name='wugsynclog_list'),
    path('logs/<int:pk>/', views.WUGSyncLogDetailView.as_view(), name='wugsynclog'),
    
    # NetBox to WUG Export
    path('connections/<int:pk>/export/', views.trigger_netbox_export_view, name='wugconnection_export'),
    path('connections/<int:pk>/export-status/', views.netbox_export_status_view, name='wugconnection_export_status'),
    
    # Individual device sync
    path('netbox-device/<int:device_id>/sync/', views.sync_netbox_device_to_wug_view, name='netbox_device_sync'),
]