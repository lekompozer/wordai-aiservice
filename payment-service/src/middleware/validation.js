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
    checkout: Joi.object({
        user_id: Joi.string().required(),
        plan: Joi.string().valid('premium', 'pro', 'vip').required(),
        duration: Joi.string().valid('3_months', '12_months').required(),
        user_email: Joi.string().email().optional(),
        user_name: Joi.string().optional(),
    }),

    // Webhook payload (basic validation, SePay signature will be verified separately)
    webhook: Joi.object().unknown(true),
};

module.exports = {
    validateBody,
    schemas,
};
