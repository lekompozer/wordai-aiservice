/**
 * Validation Middleware
 * Request body validation using Joi
 */

const Joi = require('joi');
const { AppError } = require('./errorHandler');

/**
 * Validate request body
 */
function validateBody(schema) {
    return (req, res, next) => {
        const { error } = schema.validate(req.body, {
            abortEarly: false,
            stripUnknown: true,
        });

        if (error) {
            const message = error.details.map(detail => detail.message).join(', ');
            return next(new AppError(message, 400));
        }

        next();
    };
}

// Validation schemas
const schemas = {
    // Checkout request
    // Note: user_id, user_email, user_name come from Firebase token, not request body
    checkout: Joi.object({
        plan: Joi.string().valid('premium', 'pro', 'vip').required(),
        duration: Joi.string().valid('3_months', '12_months').required(),
    }),

    // Points purchase request (NEW)
    pointsPurchase: Joi.object({
        points: Joi.string().valid('50', '100', '200').required(),
    }),

    // Book purchase request
    bookPurchase: Joi.object({
        order_id: Joi.string().pattern(/^BOOK-/).required(),
    }),

    // Webhook payload (basic validation, SePay signature will be verified separately)
    webhook: Joi.object().unknown(true),
};

module.exports = {
    validateBody,
    schemas,
};
