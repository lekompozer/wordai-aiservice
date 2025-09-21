version: '3.8'

services:
  mongodb:
    image: mongo:7.0
    container_name: agent8x-mongodb
    restart: unless-stopped
    environment:
      MONGO_INITDB_ROOT_USERNAME: agent8x_user
      MONGO_INITDB_ROOT_PASSWORD: Agent8xSecure2024
      MONGO_INITDB_DATABASE: agent8x_db
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
      - ./mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
    networks:
      - agent8x-network

  agent8x-backend:
    build: .
    container_name: agent8x-backend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: production
      MONGODB_URL: mongodb://agent8x_user:Agent8xSecure2024@mongodb:27017/agent8x_db?authSource=admin
      PORT: 3000
    depends_on:
      - mongodb
    networks:
      - agent8x-network
    volumes:
      - ./public/uploads:/app/public/uploads

volumes:
  mongodb_data:


networks:
  agent8x-network:
    driver: bridge
