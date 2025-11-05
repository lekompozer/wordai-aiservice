/**
 * Webhook Routes
 */

const express = require('express');
const router = express.Router();
const { asyncHandler } = require('../middleware/errorHandler');
const webhookController = require('../controllers/webhookController');

// SePay IPN (Instant Payment Notification)
// Mounted at /sepay in index.js, so this becomes /sepay/ipn
router.post(
    '/ipn',
    asyncHandler(webhookController.handleWebhook)
);

// Return URL (after payment)
router.get(
    '/return',
    asyncHandler(webhookController.handleReturn)
);

// Retry activation (admin only)
router.post(
    '/retry-activation',
    asyncHandler(webhookController.retryActivation)
);

module.exports = router;
