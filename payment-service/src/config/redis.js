/**
 * Redis Client for Payment Service
 * Used to push payment events to the Python worker queue
 */

const Redis = require('ioredis');
const config = require('./index');
const logger = require('../utils/logger');

let redisClient = null;

function getRedisClient() {
    if (redisClient) return redisClient;

    redisClient = new Redis(config.redis.url, {
        maxRetriesPerRequest: 3,
        retryStrategy(times) {
            const delay = Math.min(times * 100, 2000);
            return delay;
        },
        lazyConnect: true,
    });

    redisClient.on('connect', () => {
        logger.info('✅ Payment service connected to Redis');
    });

    redisClient.on('error', (err) => {
        logger.error(`Redis connection error: ${err.message}`);
    });

    return redisClient;
}

module.exports = { getRedisClient };
