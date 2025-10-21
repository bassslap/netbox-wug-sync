from netbox.plugins import PluginConfig


class WUGSyncConfig(PluginConfig):
    name = 'netbox_wug_sync'
    verbose_name = 'NetBox WhatsUp Gold Sync'
    description = 'Synchronize devices between NetBox and WhatsUp Gold'
    version = '0.1.0'
    author = 'NetBox Admin'
    author_email = 'admin@example.com'
    base_url = 'wug-sync'
    
    # Required configuration parameters that must be set in NetBox config
    required_settings = [
        'wug_host',
        'wug_username',
        'wug_password',
    ]
    
    # Default configuration parameters
    default_settings = {
        'wug_port': 9644,
        'wug_use_ssl': True,
        'wug_verify_ssl': False,
        'sync_interval_minutes': 60,
        'auto_create_sites': True,
        'auto_create_device_types': True,
        'default_device_role': 'server',
        'default_device_status': 'active',
        'sync_device_tags': True,
        'debug_mode': False,
    }
    
    # Minimum and maximum NetBox versions
    min_version = '4.0.0'
    max_version = '4.9.99'
    
    # Custom background task queues
    queues = [
        'wug_sync_queue'
    ]


config = WUGSyncConfig