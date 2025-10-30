#!/usr/bin/env python3
"""
NetBox WUG Sync Plugin - Installation Verification Script

This script verifies that the plugin is properly installed and configured.
Run this script from within your NetBox environment (Docker container or virtual environment).
"""

import sys
import os
import django

def setup_django():
    """Setup Django environment for NetBox"""
    try:
        # Try to setup Django environment
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
        django.setup()
        return True
    except Exception as e:
        print(f"❌ Failed to setup Django environment: {e}")
        return False

def test_plugin_import():
    """Test if the plugin can be imported"""
    try:
        import netbox_wug_sync
        print(f"✅ Plugin imported successfully - Version: {getattr(netbox_wug_sync, '__version__', 'Unknown')}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import plugin: {e}")
        return False

def test_django_app_loading():
    """Test if Django recognizes the plugin as an installed app"""
    try:
        from django.apps import apps
        app = apps.get_app_config('netbox_wug_sync')
        print(f"✅ Django app loaded successfully: {app.name}")
        return True
    except Exception as e:
        print(f"❌ Django app not loaded: {e}")
        return False

def test_database_tables():
    """Test if plugin database tables exist"""
    try:
        from netbox_wug_sync.models import WUGConnection, WUGDevice, WUGSyncLog
        
        # Check if we can query the tables (they exist)
        connection_count = WUGConnection.objects.count()
        device_count = WUGDevice.objects.count()
        log_count = WUGSyncLog.objects.count()
        
        print(f"✅ Database tables accessible:")
        print(f"   - WUG Connections: {connection_count}")
        print(f"   - WUG Devices: {device_count}")
        print(f"   - Sync Logs: {log_count}")
        return True
    except Exception as e:
        print(f"❌ Database tables not accessible: {e}")
        print("   Run 'python manage.py migrate' to create tables")
        return False

def test_static_files():
    """Test if static files are accessible"""
    try:
        from django.contrib.staticfiles.finders import find
        logo_path = find('netbox_wug_sync/img/wug-logo.svg')
        
        if logo_path:
            print(f"✅ Static files found: {logo_path}")
            return True
        else:
            print("❌ Static files not found")
            print("   Run 'python manage.py collectstatic --noinput' to collect static files")
            return False
    except Exception as e:
        print(f"❌ Static files test failed: {e}")
        return False

def test_url_routing():
    """Test if plugin URLs are properly configured"""
    try:
        from django.urls import reverse
        dashboard_url = reverse('plugins:netbox_wug_sync:dashboard')
        print(f"✅ URL routing configured: {dashboard_url}")
        return True
    except Exception as e:
        print(f"❌ URL routing failed: {e}")
        print("   Check that plugin is in PLUGINS list in configuration.py")
        return False

def test_wug_client():
    """Test if WUG client can be instantiated"""
    try:
        from netbox_wug_sync.wug_client import WUGClient
        # Just test instantiation, not actual connection
        client = WUGClient("http://example.com", "test", "test")
        print("✅ WUG client can be instantiated")
        return True
    except Exception as e:
        print(f"❌ WUG client test failed: {e}")
        return False

def run_all_tests():
    """Run all verification tests"""
    print("🔍 NetBox WUG Sync Plugin - Installation Verification")
    print("=" * 60)
    
    tests = [
        ("Django Environment Setup", setup_django),
        ("Plugin Import", test_plugin_import),
        ("Django App Loading", test_django_app_loading),
        ("Database Tables", test_database_tables),
        ("Static Files", test_static_files),
        ("URL Routing", test_url_routing),
        ("WUG Client", test_wug_client),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Testing: {test_name}")
        if test_func():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Plugin is properly installed and configured.")
        print("\n🌐 Next steps:")
        print("1. Access the dashboard at: /plugins/wug-sync/")
        print("2. Configure a WUG connection")
        print("3. Test API connectivity")
        return True
    else:
        print("⚠️  Some tests failed. Please address the issues above.")
        print("\n📖 For help, see the deployment guide: DEPLOYMENT.md")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)