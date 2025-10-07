// MongoDB Initialization Script
// This script runs automatically when MongoDB container starts for the first time
// It creates the application user with read/write permissions

db = db.getSiblingDB('admin');

// Check if app user already exists
const userExists = db.getUser('ai_service_user');

if (!userExists) {
    print('Creating application user: ai_service_user');

    db.createUser({
        user: 'ai_service_user',
        pwd: 'ai_service_2025_secure_password',
        roles: [
            {
                role: 'readWrite',
                db: 'ai_service_db'
            },
            {
                role: 'dbAdmin',
                db: 'ai_service_db'
            }
        ]
    });

    print('✅ Application user created successfully');
} else {
    print('ℹ️  Application user already exists');
}

// Switch to application database
db = db.getSiblingDB('ai_service_db');

print('✅ MongoDB initialization completed');
