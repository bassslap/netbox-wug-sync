"""
Test URLs configuration for Django testing
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('netbox_wug_sync.api.urls')),
    path('plugins/wug-sync/', include('netbox_wug_sync.urls')),
]