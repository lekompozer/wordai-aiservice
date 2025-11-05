/**
 * Logger Module
 * Winston-based logging with file and console transports
 */

const winston = require('winston');
const path = require('path');
const config = require('../config');

// Define log format
const logFormat = winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    winston.format.printf(({ timestamp, level, message, stack }) => {
        return `${timestamp} [${level.toUpperCase()}]: ${message}${stack ? '\n' + stack : ''}`;
    })
);

// Create logger
const logger = winston.createLogger({
    level: config.logging.level,
    format: logFormat,
    transports: [
        // Console transport
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                logFormat
            ),
        }),
        // File transport
        new winston.transports.File({
            filename: config.logging.file,
            maxsize: 10485760, // 10MB
            maxFiles: 5,
        }),
    ],
});

// Add request logging middleware
logger.logRequest = (req, res, next) => {
    const start = Date.now();

    res.on('finish', () => {
        const duration = Date.now() - start;
        logger.info(`${req.method} ${req.path} ${res.statusCode} - ${duration}ms`);
    });

    next();
};

module.exports = logger;
