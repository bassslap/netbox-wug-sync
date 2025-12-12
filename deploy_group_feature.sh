#!/bin/bash
# Deploy updated files to NetBox server

SERVER="ubuntu@192.168.220.251"
SSH_KEY="$HOME/.ssh/vm_private_key.pem"
CONTAINER="netbox-netbox-1"
PLUGIN_PATH="/opt/netbox/netbox/netbox_wug_sync"

echo "Deploying group auto-creation feature to NetBox server..."

# Copy files to server
echo "Step 1: Copying files to server..."
scp -i "$SSH_KEY" netbox_wug_sync/wug_client.py netbox_wug_sync/sync_utils.py "$SERVER:/tmp/"

# Copy files into container and restart
echo "Step 2: Deploying to container..."
ssh -i "$SSH_KEY" "$SERVER" << 'ENDSSH'
    echo "Copying files to container..."
    sudo docker cp /tmp/wug_client.py netbox-netbox-1:/opt/netbox/netbox-wug-sync/netbox_wug_sync/wug_client.py
    sudo docker cp /tmp/sync_utils.py netbox-netbox-1:/opt/netbox/netbox-wug-sync/netbox_wug_sync/sync_utils.py
    
    echo "Restarting NetBox container..."
    sudo docker restart netbox-netbox-1
    
    echo "Waiting for container to be ready..."
    sleep 10
    
    echo "Deployment complete!"
ENDSSH

echo "Done! Group auto-creation feature has been deployed."
