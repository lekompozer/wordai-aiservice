/**
 * Webhook Routes
 */

const express = require('express');
const router = express.Router();
const { asyncHandler } = require('../middleware/errorHandler');
const webhookController = require('../controllers/webhookController');

// SePay webhook callback
router.post(
    '/sepay/callback',
    asyncHandler(webhookController.handleWebhook)
);

// Return URL (after payment)
router.get(
    '/sepay/return',
    asyncHandler(webhookController.handleReturn)
);

// Retry activation (admin only)
router.post(
    '/retry-activation',
    asyncHandler(webhookController.retryActivation)
);

module.exports = router;
