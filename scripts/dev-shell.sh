#!/bin/bash
# Bash script to start the development environment
# Usage: ./scripts/dev-shell.sh

echo -e "\033[0;36mStarting RAGstone Development Environment...\033[0m"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "\033[0;31mError: Docker is not running. Please start Docker first.\033[0m"
    exit 1
fi

# Build and start the container
echo -e "\033[0;33mBuilding development container...\033[0m"
docker-compose -f docker-compose.dev.yml build

echo -e "\033[0;33mStarting development shell...\033[0m"
docker-compose -f docker-compose.dev.yml run --rm dev

echo -e "\033[0;36mDevelopment session ended.\033[0m"
