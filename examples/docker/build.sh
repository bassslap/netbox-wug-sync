#!/bin/bash

# Build script for NetBox with WUG Sync plugin
# This script builds a custom NetBox Docker image with the plugin pre-installed

set -e

# Configuration
NETBOX_VERSION=${NETBOX_VERSION:-v4.0.8}
IMAGE_NAME=${IMAGE_NAME:-mynetbox}
IMAGE_TAG=${IMAGE_TAG:-latest}
TEST_MODE=${1:-""}

echo "Building NetBox with WUG Sync plugin..."
echo "NetBox version: $NETBOX_VERSION"
echo "Image name: $IMAGE_NAME:$IMAGE_TAG"

if [ "$TEST_MODE" = "--test" ]; then
    echo "Running in test mode - build only, no push"
fi

# Build the Docker image
docker build \
    --build-arg NETBOX_VERSION=$NETBOX_VERSION \
    -t $IMAGE_NAME:$IMAGE_TAG \
    -f Dockerfile.plugin \
    .

# Test the build if requested
if [ "$TEST_MODE" = "--test" ]; then
    echo "Testing Docker image..."
    
    # Test that the image can start
    CONTAINER_ID=$(docker run -d --rm $IMAGE_NAME:$IMAGE_TAG sleep 30)
    
    # Test that the plugin is installed
    docker exec $CONTAINER_ID python -c "import netbox_wug_sync; print('✅ Plugin import successful')" || {
        echo "❌ Plugin import failed"
        docker stop $CONTAINER_ID
        exit 1
    }
    
    # Cleanup
    docker stop $CONTAINER_ID
    echo "✅ Docker build test passed"
    exit 0
fi

echo "✅ Build completed: $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "To run NetBox with the plugin:"
echo "  docker-compose up -d"
echo ""
echo "To push to registry:"
echo "  docker tag $IMAGE_NAME:$IMAGE_TAG your-registry.com/$IMAGE_NAME:$IMAGE_TAG"
echo "  docker push your-registry.com/$IMAGE_NAME:$IMAGE_TAG"