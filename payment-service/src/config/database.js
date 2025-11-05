/**
 * MongoDB Connection Module
 */

const { MongoClient } = require('mongodb');
const config = require('../config');
const logger = require('../utils/logger');

let client;
let db;

/**
 * Connect to MongoDB
 */
async function connect() {
    try {
        client = new MongoClient(config.mongodb.uri, {
            maxPoolSize: 10,
            minPoolSize: 2,
            serverSelectionTimeoutMS: 5000,
        });

        await client.connect();
        db = client.db(config.mongodb.database);

        logger.info(`✅ Connected to MongoDB: ${config.mongodb.database}`);

        // Test connection
        await db.admin().ping();
        logger.info('✅ MongoDB ping successful');

        return db;
    } catch (error) {
        logger.error(`❌ MongoDB connection error: ${error.message}`);
        throw error;
    }
}

/**
 * Get database instance
 */
function getDb() {
    if (!db) {
        throw new Error('Database not initialized. Call connect() first.');
    }
    return db;
}

/**
 * Close MongoDB connection
 */
async function close() {
    if (client) {
        await client.close();
        logger.info('✅ MongoDB connection closed');
    }
}

module.exports = {
    connect,
    getDb,
    close,
};
