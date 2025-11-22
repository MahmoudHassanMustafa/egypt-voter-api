#!/bin/bash

# Egypt Voter API - Docker Build and Run Script

set -e

echo "=========================================="
echo "Egypt Voter API - Docker Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose are installed${NC}"
echo ""

# Check if container is already running
if docker ps | grep -q "egypt-voter-api"; then
    echo -e "${YELLOW}⚠️  Container is already running${NC}"
    read -p "Do you want to rebuild and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping existing container..."
        docker-compose down
    else
        echo "Exiting..."
        exit 0
    fi
fi

# Build and start
echo "Building Docker image..."
docker-compose build

echo ""
echo "Starting container..."
docker-compose up -d

echo ""
echo -e "${GREEN}✅ Container started successfully!${NC}"
echo ""

# Wait for health check
echo "Waiting for API to be ready..."
sleep 5

# Check health
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API is healthy and ready!${NC}"
        break
    else
        echo "Waiting for API to start... (attempt $i/10)"
        sleep 3
    fi
done

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "API is running at: http://localhost:8000"
echo ""
echo "📚 Documentation:"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - ReDoc:      http://localhost:8000/redoc"
echo ""
echo "🧪 Test the API:"
echo '  curl -X POST "http://localhost:8000/lookup" \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"national_id": "29710260300314"}'"'"
echo ""
echo "📊 View logs:"
echo "  docker-compose logs -f"
echo ""
echo "🛑 Stop the API:"
echo "  docker-compose down"
echo ""
