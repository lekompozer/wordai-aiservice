/**
 * WordAI Payment Service
 * Node.js microservice for SePay payment integration
 */

const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const rateLimit = require('express-rate-limit');
const config = require('./config');
const logger = require('./utils/logger');
const database = require('./config/database');
const {
    errorHandler,
    notFoundHandler,
} = require('./middleware/errorHandler');

// Import routes
const paymentRoutes = require('./routes/paymentRoutes');
const webhookRoutes = require('./routes/webhookRoutes');

// Create Express app
const app = express();

// Trust proxy (for rate limiting behind NGINX)
app.set('trust proxy', 1);

// Security headers
app.use(helmet());

// CORS
app.use(
    cors({
        origin: config.security.allowedOrigins,
        credentials: true,
    })
);

// Rate limiting
const limiter = rateLimit({
    windowMs: config.rateLimit.windowMs,
    max: config.rateLimit.maxRequests,
    message: 'Too many requests from this IP, please try again later.',
    standardHeaders: true,
    legacyHeaders: false,
});

app.use('/api/', limiter);

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Request logging
app.use(logger.logRequest);

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'healthy',
        service: config.server.serviceName,
        timestamp: new Date().toISOString(),
        uptime: process.uptime(),
    });
});

// API routes
app.use('/api/v1/payments', paymentRoutes);
app.use('/api/v1/webhooks', webhookRoutes);

// 404 handler
app.use(notFoundHandler);

// Error handler
app.use(errorHandler);

// Start server
async function startServer() {
    try {
        // Connect to MongoDB
        await database.connect();

        // Start Express server
        const server = app.listen(config.server.port, '0.0.0.0', () => {
            logger.info(`🚀 ${config.server.serviceName} running on port ${config.server.port}`);
            logger.info(`📦 Environment: ${config.server.env}`);
            logger.info(`🏦 SePay Sandbox: ${config.sepay.sandbox ? 'ENABLED' : 'DISABLED'}`);
        });

        // Graceful shutdown
        process.on('SIGTERM', async () => {
            logger.info('SIGTERM signal received: closing HTTP server');
            server.close(async () => {
                logger.info('HTTP server closed');
                await database.close();
                process.exit(0);
            });
        });

        process.on('SIGINT', async () => {
            logger.info('SIGINT signal received: closing HTTP server');
            server.close(async () => {
                logger.info('HTTP server closed');
                await database.close();
                process.exit(0);
            });
        });
    } catch (error) {
        logger.error(`Failed to start server: ${error.message}`);
        process.exit(1);
    }
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
    logger.error(`Uncaught Exception: ${error.message}`);
    logger.error(error.stack);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    logger.error(`Unhandled Rejection at: ${promise}, reason: ${reason}`);
    process.exit(1);
});

// Start the server
startServer();

module.exports = app;
