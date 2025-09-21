#!/bin/bash

# 🚀 AI Chatbot RAG - Production Deployment Script
# This script will update your server with the latest clean code from main branch

set -e

echo "🚀 Starting AI Chatbot RAG deployment..."

# Configuration
REPO_URL="https://github.com/lekompozer/ai-rag-chatbot.git"
APP_DIR="/opt/ai-chatbot-rag"
BACKUP_DIR="/opt/ai-chatbot-rag-backup-$(date +%Y%m%d_%H%M%S)"
DOCKER_IMAGE="ai-chatbot-rag:latest"
CONTAINER_NAME="ai-chatbot-rag"

# Function to create backup
create_backup() {
    echo "📦 Creating backup of current deployment..."
    if [ -d "$APP_DIR" ]; then
        sudo cp -r "$APP_DIR" "$BACKUP_DIR"
        echo "✅ Backup created at: $BACKUP_DIR"
    fi
}

# Function to stop existing services
stop_services() {
    echo "🛑 Stopping existing services..."
    
    # Stop Docker container if running
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        echo "Stopping Docker container: $CONTAINER_NAME"
        docker stop $CONTAINER_NAME || true
        docker rm $CONTAINER_NAME || true
    fi
    
    # Stop any process using port 8000
    if lsof -i :8000 -t >/dev/null 2>&1; then
        echo "Stopping processes on port 8000..."
        sudo kill -9 $(lsof -i :8000 -t) || true
    fi
    
    echo "✅ Services stopped"
}

# Function to deploy new code
deploy_code() {
    echo "📥 Deploying fresh code from main branch..."
    
    # Remove old directory if exists
    if [ -d "$APP_DIR" ]; then
        sudo rm -rf "$APP_DIR"
    fi
    
    # Clone fresh code
    sudo git clone -b main "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
    
    # Set proper permissions
    sudo chown -R $USER:$USER "$APP_DIR"
    
    echo "✅ Code deployed successfully"
}

# Function to setup environment
setup_environment() {
    echo "⚙️ Setting up environment..."
    cd "$APP_DIR"
    
    # Copy environment file from backup if exists
    if [ -f "$BACKUP_DIR/.env" ]; then
        echo "📋 Copying .env from backup..."
        cp "$BACKUP_DIR/.env" .
    else
        echo "⚠️  Please create .env file based on .env.example"
        cp .env.example .env
    fi
    
    # Preserve important data directories
    if [ -d "$BACKUP_DIR/data" ]; then
        echo "📋 Preserving data directory..."
        cp -r "$BACKUP_DIR/data/"* ./data/ 2>/dev/null || true
    fi
    
    if [ -d "$BACKUP_DIR/logs" ]; then
        echo "📋 Preserving logs directory..."
        cp -r "$BACKUP_DIR/logs/"* ./logs/ 2>/dev/null || true
    fi
    
    echo "✅ Environment setup completed"
}

# Function to build and start services
start_services() {
    echo "🔨 Building and starting services..."
    cd "$APP_DIR"
    
    # Build Docker image
    echo "Building Docker image..."
    docker build -t $DOCKER_IMAGE .
    
    # Start container
    echo "Starting Docker container..."
    docker run -d \
        --name $CONTAINER_NAME \
        -p 8000:8000 \
        --env-file .env \
        --add-host=host.docker.internal:host-gateway \
        --restart unless-stopped \
        -v $(pwd)/data:/app/data \
        -v $(pwd)/logs:/app/logs \
        $DOCKER_IMAGE
    
    echo "✅ Services started successfully"
}

# Function to verify deployment
verify_deployment() {
    echo "🔍 Verifying deployment..."
    
    # Wait a moment for container to start
    sleep 10
    
    # Check if container is running
    if docker ps -q -f name=$CONTAINER_NAME | grep -q .; then
        echo "✅ Container is running"
    else
        echo "❌ Container failed to start"
        docker logs $CONTAINER_NAME
        exit 1
    fi
    
    # Check health endpoint
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ Health check passed"
    else
        echo "⚠️  Health check failed, but container is running"
    fi
    
    # Show container status
    docker ps -f name=$CONTAINER_NAME
}

# Main deployment process
main() {
    echo "🚀 AI Chatbot RAG - Production Deployment"
    echo "========================================="
    
    # Ask for confirmation
    read -p "This will update your production server. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled"
        exit 1
    fi
    
    create_backup
    stop_services
    deploy_code
    setup_environment
    start_services
    verify_deployment
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo "📱 Application is running at: http://localhost:8000"
    echo "📊 Health check: http://localhost:8000/health"
    echo "📚 API docs: http://localhost:8000/docs"
    echo "🗂️  Backup location: $BACKUP_DIR"
    echo ""
    echo "🔧 To rollback if needed:"
    echo "   docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
    echo "   sudo rm -rf $APP_DIR"
    echo "   sudo mv $BACKUP_DIR $APP_DIR"
    echo ""
}

# Run main function
main "$@"
