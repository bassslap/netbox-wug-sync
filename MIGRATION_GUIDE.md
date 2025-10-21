# NetBox Plugin Development Tips

## Ongoing Migration Workflow

### Option A: Manual Migration Creation (What we just did)
- Create migration files manually when you change models
- Pro: Full control over migrations
- Con: More manual work

### Option B: Use Django Management Commands in Development
- Set up a separate Django project just for development
- Use regular Django makemigrations there
- Copy migrations to your plugin

### Option C: Schema Comparison Tools
- Use tools like django-migration-testcase
- Compare your models with current database schema
- Generate migration operations automatically

## Recommended Workflow for YOUR Plugin:

1. **Development Environment:**
   ```bash
   # Work in your plugin directory
   cd /home/bryan/REPOS/netbox-wug-sync
   
   # Make model changes
   vim netbox_wug_sync/models.py
   ```

2. **Create Migration:**
   ```bash
   # Use the helper script or create manually
   python3 dev_migration_helper.py
   
   # Or create a simple migration manually:
   # 1. Copy the last migration file
   # 2. Update the operations list
   # 3. Increment the migration number
   ```

3. **Test Migration:**
   ```bash
   # Copy updated plugin to NetBox
   cp -r netbox_wug_sync/* /home/bryan/REPOS/netbox/netbox/netbox_wug_sync/
   
   # Apply migration
   cd /home/bryan/REPOS/netbox/netbox
   source ../venv/bin/activate
   python3 manage.py migrate netbox_wug_sync
   ```

4. **Test Plugin:**
   ```bash
   # Start NetBox and test
   python3 manage.py runserver
   ```

## Migration Examples:

### Adding a Field:
```python
# In 0002_add_description_field.py
operations = [
    migrations.AddField(
        model_name='wugconnection',
        name='description',
        field=models.TextField(blank=True, help_text='Connection description'),
    ),
]
```

### Changing a Field:
```python
# In 0003_change_host_length.py
operations = [
    migrations.AlterField(
        model_name='wugconnection',
        name='host',
        field=models.CharField(max_length=512, help_text='WhatsUp Gold server hostname'),
    ),
]
```

### Adding a Model:
```python
# In 0004_add_wuginterface.py
operations = [
    migrations.CreateModel(
        name='WUGInterface',
        fields=[
            ('id', models.BigAutoField(primary_key=True)),
            ('name', models.CharField(max_length=100)),
            ('device', models.ForeignKey('WUGDevice', on_delete=models.CASCADE)),
        ],
    ),
]
```