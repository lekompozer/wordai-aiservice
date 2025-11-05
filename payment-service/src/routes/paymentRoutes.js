/**
 * Payment Routes
 */

const express = require('express');
const router = express.Router();
const { asyncHandler } = require('../middleware/errorHandler');
const { validateBody, schemas } = require('../middleware/validation');
const paymentController = require('../controllers/paymentController');

// Create checkout
router.post(
    '/checkout',
    validateBody(schemas.checkout),
    asyncHandler(paymentController.createCheckout)
);

// Get payment status
router.get(
    '/status/:order_invoice_number',
    asyncHandler(paymentController.getPaymentStatus)
);

// Get user payments
router.get(
    '/user/:user_id',
    asyncHandler(paymentController.getUserPayments)
);

module.exports = router;
