/**
 * Error Handler Middleware
 */

const logger = require('../utils/logger');

class AppError extends Error {
    constructor(message, statusCode) {
        super(message);
        this.statusCode = statusCode;
        this.isOperational = true;
        Error.captureStackTrace(this, this.constructor);
    }
}

/**
 * Global error handler middleware
 */
function errorHandler(err, req, res, next) {
    err.statusCode = err.statusCode || 500;
    err.status = err.status || 'error';

    // Log error
    if (err.statusCode >= 500) {
        logger.error(`${err.message}\n${err.stack}`);
    } else {
        logger.warn(`${err.message}`);
    }

    // Send error response
    res.status(err.statusCode).json({
        status: err.status,
        message: err.message,
        ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
    });
}

/**
 * Async handler wrapper
 */
function asyncHandler(fn) {
    return (req, res, next) => {
        Promise.resolve(fn(req, res, next)).catch(next);
    };
}

/**
 * 404 Not Found handler
 */
function notFoundHandler(req, res, next) {
    const error = new AppError(`Route not found: ${req.originalUrl}`, 404);
    next(error);
}

module.exports = {
    AppError,
    errorHandler,
    asyncHandler,
    notFoundHandler,
};
