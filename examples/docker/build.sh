#!/bin/bash
# Build script for creating custom NetBox image with netbox-wug-sync plugin

set -e

# Configuration
NETBOX_VERSION=${NETBOX_VERSION:-v4.4.5}
IMAGE_NAME=${IMAGE_NAME:-mynetbox}
IMAGE_TAG=${IMAGE_TAG:-latest}

echo "Building NetBox ${NETBOX_VERSION} with netbox-wug-sync plugin..."

# Build the custom image
docker build \
    --build-arg NETBOX_VERSION=${NETBOX_VERSION} \
    -t ${IMAGE_NAME}:${IMAGE_TAG} \
    -f Dockerfile.plugin \
    .

echo "✅ Built image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "🚀 You can now use this image in your docker-compose.override.yml"