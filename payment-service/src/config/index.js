/**
 * Configuration Module
 * Centralized configuration management
 */

require('dotenv').config();

const config = {
    // Server
    server: {
        port: parseInt(process.env.PORT, 10) || 3000,
        env: process.env.NODE_ENV || 'development',
        serviceName: process.env.SERVICE_NAME || 'wordai-payment-service',
    },

    // SePay
    sepay: {
        apiKey: process.env.SEPAY_API_KEY,
        merchantCode: process.env.SEPAY_MERCHANT_CODE,
        secretKey: process.env.SEPAY_SECRET_KEY,
        apiUrl: process.env.SEPAY_API_URL || 'https://api.sepay.vn/v1',
        sandbox: process.env.SEPAY_SANDBOX === 'true',
    },

    // MongoDB
    mongodb: {
        uri: process.env.MONGODB_URI || 'mongodb://admin:WordAIMongoRootPassword@localhost:27017',
        database: process.env.MONGODB_DATABASE || 'ai_service_db',
    },

    // Python Service
    pythonService: {
        url: process.env.PYTHON_SERVICE_URL || 'http://localhost:8081',
        timeout: 10000, // 10 seconds
    },

    // Webhook
    webhook: {
        url: process.env.WEBHOOK_URL,
        secret: process.env.WEBHOOK_SECRET,
    },

    // Security
    security: {
        apiSecretKey: process.env.API_SECRET_KEY,
        allowedOrigins: (process.env.ALLOWED_ORIGINS || '').split(',').filter(Boolean),
    },

    // Logging
    logging: {
        level: process.env.LOG_LEVEL || 'info',
        file: process.env.LOG_FILE || '/app/logs/payment-service.log',
    },

    // Rate Limiting
    rateLimit: {
        windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS, 10) || 900000, // 15 minutes
        maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS, 10) || 100,
    },
};

// Validate required configuration
const requiredConfigs = [
    { key: 'sepay.apiKey', value: config.sepay.apiKey, name: 'SEPAY_API_KEY' },
    { key: 'sepay.merchantCode', value: config.sepay.merchantCode, name: 'SEPAY_MERCHANT_CODE' },
    { key: 'sepay.secretKey', value: config.sepay.secretKey, name: 'SEPAY_SECRET_KEY' },
    { key: 'mongodb.uri', value: config.mongodb.uri, name: 'MONGODB_URI' },
];

const missingConfigs = requiredConfigs.filter(c => !c.value);

// Only exit on missing configs in production AND when SePay variables are actually needed
// For Phase 1 testing, we just log warnings
if (missingConfigs.length > 0) {
    console.warn('⚠️  Warning: Missing environment variables:');
    missingConfigs.forEach(c => console.warn(`  - ${c.name}`));
    
    if (process.env.NODE_ENV === 'production') {
        console.warn('⚠️  Running in production mode without full configuration');
        console.warn('⚠️  Payment features will not work until SePay credentials are configured');
    }
}

module.exports = config;
