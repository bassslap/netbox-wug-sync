# Feature: Device Sync Improvements

## Branch: feature/device-sync-improvements

### Changes Made

#### 1. Fixed Duplicates Issue

**Problem**: Devices from WhatsUp Gold could create duplicate NetBox devices if multiple WUG devices had the same name, or if a NetBox device already existed with the same name.

**Solution**: Enhanced `create_or_update_netbox_device()` in `sync_utils.py` to:
- Check if another WUGDevice already points to an existing NetBox device before linking
- Log a warning when a duplicate is detected
- Return 'skipped' action to prevent duplicate associations
- Preserve existing WUG device links while preventing new duplicates

**Files Modified**:
- `netbox_wug_sync/sync_utils.py` - Added duplicate detection logic in `create_or_update_netbox_device()`

**Behavior**:
- When a WUG device tries to link to a NetBox device that's already linked to another WUG device, it will be skipped
- A warning is logged with details about the conflict
- The sync continues without creating duplicate NetBox devices

#### 2. Device Deletion/Deactivation Sync to WUG

**Problem**: When a device was deleted from NetBox or its status changed to non-active, it remained in WhatsUp Gold.

**Solution**: 
- **Status Change Detection**: Modified `device_saved_handler()` to detect when a device status changes to non-active (failed, offline, planned, decommissioning, etc.) and automatically remove it from WUG
- **Device Deletion**: Enabled `device_deleted_handler()` to remove devices from WUG when they're deleted from NetBox
- **API Integration**: Fixed `remove_device_from_wug()` to properly call WUG API's delete_device endpoint

**Files Modified**:
- `netbox_wug_sync/signals.py`:
  - Enhanced `device_saved_handler()` to handle status changes
  - Enabled and fixed `device_deleted_handler()` 
  - Fixed `remove_device_from_wug()` to use correct field names and handle API response properly

**Behavior**:
- When a NetBox device status changes from 'active' to any other status, it's automatically removed from WUG
- When a NetBox device is deleted, it's automatically removed from WUG
- Associated WUGDevice records are deleted after successful removal from WUG
- Sync logs are created for all removal operations
- All errors are logged and handled gracefully without breaking NetBox

### Testing Recommendations

1. **Test Duplicate Prevention**:
   - Create a device in NetBox manually
   - Sync from WUG where a device has the same name
   - Verify that a duplicate is not created and a warning is logged
   - Check that the original NetBox device is preserved

2. **Test Status Change Removal**:
   - Create/sync a device in NetBox with status 'active'
   - Verify device appears in WUG
   - Change NetBox device status to 'failed', 'offline', or 'decommissioning'
   - Verify device is removed from WUG
   - Check WUGDevice record is deleted
   - Verify sync log entry is created

3. **Test Device Deletion**:
   - Create/sync a device in NetBox
   - Verify device appears in WUG
   - Delete device from NetBox
   - Verify device is removed from WUG
   - Check WUGDevice record is deleted
   - Verify sync log entry is created

4. **Test Error Handling**:
   - Test with WUG connection unavailable
   - Test with invalid device IDs
   - Verify errors are logged but don't break NetBox operations

### API Compatibility

These changes use the existing WUG API `delete_device()` method which calls:
```
DELETE /api/v1/devices/{device_id}
```

### Migration Notes

No database migrations required - only behavioral changes to existing signal handlers and sync logic.

### Backward Compatibility

- All existing functionality is preserved
- New features are additive and don't break existing sync workflows
- Duplicate detection only prevents new duplicates, doesn't affect existing associations
