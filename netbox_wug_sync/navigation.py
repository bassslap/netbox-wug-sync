"""
Navigation Configuration for NetBox WhatsUp Gold Sync Plugin

This module defines navigation menu items for the plugin.
"""

from netbox.plugins import PluginMenuButton, PluginMenuItem

# Define menu buttons
add_connection_button = PluginMenuButton(
    link='plugins:netbox_wug_sync:wugconnection_add',
    title='Add Connection',
    icon_class='mdi mdi-plus-thick'
)

# Define menu items
menu_items = (
    PluginMenuItem(
        link='plugins:netbox_wug_sync:dashboard',
        link_text='Dashboard',
    ),
    PluginMenuItem(
        link='plugins:netbox_wug_sync:wugdevice_list',
        link_text='Devices',
    ),
    PluginMenuItem(
        link='plugins:netbox_wug_sync:wugsynclog_list',
        link_text='Sync Logs',
    ),
)