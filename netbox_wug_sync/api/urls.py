"""
API URL Configuration for NetBox WhatsUp Gold Sync Plugin

This module defines URL patterns for the plugin's REST API endpoints.
"""

from rest_framework.routers import DefaultRouter
from django.urls import path, include

from . import views

app_name = 'netbox_wug_sync-api'

# Create router for viewsets
router = DefaultRouter()
router.register(r'connections', views.WUGConnectionViewSet)
router.register(r'devices', views.WUGDeviceViewSet)
router.register(r'sync-logs', views.WUGSyncLogViewSet)

# URL patterns
urlpatterns = [
    # Plugin-level endpoints
    path('status/', views.plugin_status, name='plugin_status'),
    path('sync/', views.trigger_global_sync, name='trigger_global_sync'),
    
    # Include router URLs
    path('', include(router.urls)),
]