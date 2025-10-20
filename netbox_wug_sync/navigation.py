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
        icon_class='mdi mdi-view-dashboard'
    ),
    PluginMenuItem(
        link='plugins:netbox_wug_sync:wugconnection_list',
        link_text='Connections',
        icon_class='mdi mdi-server-network',
        buttons=[add_connection_button]
    ),
    PluginMenuItem(
        link='plugins:netbox_wug_sync:wugdevice_list',
        link_text='Devices',
        icon_class='mdi mdi-devices'
    ),
    PluginMenuItem(
        link='plugins:netbox_wug_sync:wugsynclog_list',
        link_text='Sync Logs',
        icon_class='mdi mdi-clipboard-text'
    ),
)