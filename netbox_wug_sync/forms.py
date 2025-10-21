"""
Django Forms for NetBox WhatsUp Gold Sync Plugin

This module contains form classes for managing WUG sync objects.
"""

from django import forms
from django.core.exceptions import ValidationError

from netbox.forms import NetBoxModelForm
from dcim.models import DeviceRole
from .models import WUGConnection, WUGDevice
from .wug_client import WUGAPIClient


class WUGConnectionForm(NetBoxModelForm):
    """Form for creating/editing WUG Connections"""
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text="Password for WhatsUp Gold API access"
    )
    
    test_connection = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Test connection settings before saving"
    )
    
    class Meta:
        model = WUGConnection
        fields = [
            'name', 'host', 'port', 'username', 'password', 
            'use_ssl', 'verify_ssl', 'is_active',
            'sync_interval_minutes', 'auto_create_sites', 
            'auto_create_device_types', 'default_device_role',
            'test_connection'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'My WUG Server'}),
            'host': forms.TextInput(attrs={'placeholder': 'wug.example.com'}),
            'port': forms.NumberInput(attrs={'min': 1, 'max': 65535}),
            'username': forms.TextInput(attrs={'placeholder': 'wug_user'}),
            'sync_interval_minutes': forms.NumberInput(attrs={'min': 1, 'max': 10080}),
        }
        
        help_texts = {
            'name': 'Friendly name for this WhatsUp Gold connection',
            'host': 'WhatsUp Gold server hostname or IP address',
            'port': 'WhatsUp Gold API port (default: 9644)',
            'username': 'Username for WhatsUp Gold API access',
            'use_ssl': 'Use HTTPS for API connections',
            'verify_ssl': 'Verify SSL certificates (disable for self-signed certs)',
            'is_active': 'Enable synchronization for this connection',
            'sync_interval_minutes': 'Automatic sync interval in minutes (1-10080)',
            'auto_create_sites': 'Automatically create NetBox sites from WUG groups',
            'auto_create_device_types': 'Automatically create device types for unknown devices',
            'default_device_role': 'Default role for synced devices (leave blank for auto-detection)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize default_device_role queryset
        self.fields['default_device_role'].queryset = DeviceRole.objects.all().order_by('name')
        self.fields['default_device_role'].required = False
        
        # If editing existing connection, don't require password
        if self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].help_text = "Leave blank to keep existing password"
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If parent clean() failed, cleaned_data might be None
        if cleaned_data is None:
            return cleaned_data
        
        # Validate connection settings if test_connection is checked
        if cleaned_data.get('test_connection'):
            host = cleaned_data.get('host')
            port = cleaned_data.get('port')
            username = cleaned_data.get('username')
            password = cleaned_data.get('password')
            use_ssl = cleaned_data.get('use_ssl', True)
            verify_ssl = cleaned_data.get('verify_ssl', False)
            
            # If editing and password is blank, use existing password
            if not password and self.instance.pk:
                password = self.instance.password
            
            if all([host, port, username, password]):
                try:
                    with WUGAPIClient(
                        host=host,
                        port=port,
                        username=username,
                        password=password,
                        use_ssl=use_ssl,
                        verify_ssl=verify_ssl,
                        timeout=10  # Shorter timeout for form validation
                    ) as client:
                        result = client.test_connection()
                        
                        if not result['success']:
                            raise ValidationError({
                                'test_connection': f"Connection test failed: {result['message']}"
                            })
                
                except Exception as e:
                    raise ValidationError({
                        'test_connection': f"Connection test error: {str(e)}"
                    })
        
        return cleaned_data
    
    def clean_host(self):
        """Validate host field"""
        host = self.cleaned_data.get('host')
        if host:
            # Accept both URLs and hostnames
            # If it looks like a hostname, convert to URL format for the URLValidator
            if not host.startswith(('http://', 'https://')):
                # Assume HTTPS for hostname-only entries
                host = f'https://{host}'
            
            # Basic validation - the URLValidator in the model will do the rest
            if '://' in host:
                parts = host.split('://', 1)
                if len(parts) == 2:
                    protocol, hostname_part = parts
                    # Remove port if included in hostname
                    if ':' in hostname_part:
                        hostname_part = hostname_part.split(':')[0]
                    
                    # Basic hostname validation
                    if hostname_part and not hostname_part.replace('.', '').replace('-', '').replace('_', '').isalnum():
                        raise ValidationError("Enter a valid hostname or IP address")
                        
                    return host
            
            raise ValidationError("Enter a valid URL or hostname")
        
        return host
    
    def clean_port(self):
        """Validate port field"""
        port = self.cleaned_data.get('port')
        if port and (port < 1 or port > 65535):
            raise ValidationError("Port must be between 1 and 65535")
        return port
    
    def clean_sync_interval_minutes(self):
        """Validate sync interval"""
        interval = self.cleaned_data.get('sync_interval_minutes')
        if interval and (interval < 1 or interval > 10080):  # 1 week max
            raise ValidationError("Sync interval must be between 1 minute and 1 week (10080 minutes)")
        return interval


class WUGDeviceForm(NetBoxModelForm):
    """Form for editing WUG Device settings"""
    
    class Meta:
        model = WUGDevice
        fields = [
            'sync_enabled',
            'netbox_device'
        ]
        
        help_texts = {
            'sync_enabled': 'Enable synchronization for this device',
            'netbox_device': 'Manually associate with an existing NetBox device',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make most fields read-only since they come from WUG
        readonly_fields = [
            'wug_id', 'wug_name', 'wug_display_name', 'wug_ip_address',
            'wug_mac_address', 'wug_device_type', 'wug_vendor', 'wug_model',
            'wug_os_version', 'wug_group', 'wug_location', 'wug_status',
            'wug_last_seen', 'connection', 'sync_status', 'last_sync_attempt',
            'last_sync_success', 'sync_error_message'
        ]
        
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['readonly'] = True
                self.fields[field_name].disabled = True


class WUGConnectionTestForm(forms.Form):
    """Form for testing WUG connection without saving"""
    
    host = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'placeholder': 'wug.example.com'})
    )
    
    port = forms.IntegerField(
        initial=9644,
        min_value=1,
        max_value=65535
    )
    
    username = forms.CharField(max_length=100)
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'})
    )
    
    use_ssl = forms.BooleanField(
        initial=True,
        required=False,
        help_text="Use HTTPS for API connections"
    )
    
    verify_ssl = forms.BooleanField(
        initial=False,
        required=False,
        help_text="Verify SSL certificates"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Test the connection
        host = cleaned_data.get('host')
        port = cleaned_data.get('port')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        use_ssl = cleaned_data.get('use_ssl', True)
        verify_ssl = cleaned_data.get('verify_ssl', False)
        
        if all([host, port, username, password]):
            try:
                with WUGAPIClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    use_ssl=use_ssl,
                    verify_ssl=verify_ssl,
                    timeout=10
                ) as client:
                    result = client.test_connection()
                    
                    if not result['success']:
                        raise ValidationError(f"Connection test failed: {result['message']}")
                    
                    # Store result for display
                    cleaned_data['test_result'] = result
            
            except Exception as e:
                raise ValidationError(f"Connection test error: {str(e)}")
        
        return cleaned_data


class BulkSyncForm(forms.Form):
    """Form for bulk sync operations"""
    
    SYNC_ACTIONS = [
        ('enable', 'Enable sync'),
        ('disable', 'Disable sync'),
        ('force_sync', 'Force sync now'),
    ]
    
    action = forms.ChoiceField(
        choices=SYNC_ACTIONS,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    device_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    confirm = forms.BooleanField(
        required=True,
        help_text="Confirm that you want to perform this action"
    )
    
    def clean_device_ids(self):
        """Parse and validate device IDs"""
        device_ids_str = self.cleaned_data.get('device_ids', '')
        
        try:
            device_ids = [int(id.strip()) for id in device_ids_str.split(',') if id.strip()]
        except ValueError:
            raise ValidationError("Invalid device IDs")
        
        if not device_ids:
            raise ValidationError("No devices selected")
        
        # Validate that all device IDs exist
        existing_count = WUGDevice.objects.filter(id__in=device_ids).count()
        if existing_count != len(device_ids):
            raise ValidationError("Some selected devices do not exist")
        
        return device_ids


# Filter Forms (for use with django-filter)

class WUGConnectionFilterForm(forms.Form):
    """Filter form for WUG Connections list"""
    
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by name...'})
    )
    
    host = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by host...'})
    )
    
    is_active = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            (True, 'Active'),
            (False, 'Inactive')
        ])
    )


class WUGDeviceFilterForm(forms.Form):
    """Filter form for WUG Devices list"""
    
    wug_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by name...'})
    )
    
    wug_ip_address = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by IP...'})
    )
    
    connection = forms.ModelChoiceField(
        queryset=WUGConnection.objects.all(),
        required=False,
        empty_label="All Connections"
    )
    
    sync_status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Status'),
            ('pending', 'Pending'),
            ('syncing', 'Syncing'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('skipped', 'Skipped'),
        ]
    )
    
    sync_enabled = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=[
            ('', 'All'),
            (True, 'Sync Enabled'),
            (False, 'Sync Disabled')
        ])
    )
    
    wug_vendor = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by vendor...'})
    )
    
    wug_device_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Filter by type...'})
    )