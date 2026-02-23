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
        return_url: Joi.string().uri().optional(), // Optional return URL for redirect after payment
    }),

    // Song learning subscription (NEW)
    songLearningCheckout: Joi.object({
        plan_id: Joi.string().valid('monthly', '6_months', 'yearly').required(),
        duration_months: Joi.number().valid(1, 6, 12).required(),
        amount: Joi.number().valid(29000, 150000, 250000).required(),
    }),

    // Conversation Learning subscription
    conversationLearningCheckout: Joi.object({
        package_id: Joi.string().valid('3_months', '6_months', '12_months').required(),
        price_tier: Joi.string().valid('no_code', 'tier_1', 'tier_2').required(),
        amount: Joi.number().integer().min(100000).required(), // min 99k*3months=297k, but allow some flexibility
        affiliate_code: Joi.string().alphanum().max(30).optional().allow(null, ''),
        student_id: Joi.string().max(50).optional().allow(null, ''),
    }),

    // Webhook payload (basic validation, SePay signature will be verified separately)
    webhook: Joi.object().unknown(true),
};

module.exports = {
    validateBody,
    schemas,
};
