/**
 * Payment Routes
 */

const express = require('express');
const router = express.Router();
const { asyncHandler } = require('../middleware/errorHandler');
const { validateBody, schemas } = require('../middleware/validation');
const { verifyFirebaseToken } = require('../middleware/firebaseAuth');
const paymentController = require('../controllers/paymentController');

// Create checkout - REQUIRES AUTHENTICATION
router.post(
    '/checkout',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.checkout),
    asyncHandler(paymentController.createCheckout)
);

// Create points purchase - REQUIRES AUTHENTICATION (NEW)
router.post(
    '/checkout/points',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.pointsPurchase),
    asyncHandler(paymentController.createPointsPurchase)
);

// Create book purchase - REQUIRES AUTHENTICATION
router.post(
    '/checkout/books',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.bookPurchase),
    asyncHandler(paymentController.createBookPurchase)
);

// Create song learning subscription - REQUIRES AUTHENTICATION (NEW)
router.post(
    '/song-learning/checkout',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.songLearningCheckout),
    asyncHandler(paymentController.createSongLearningCheckout)
);

// Create conversation learning subscription - REQUIRES AUTHENTICATION
router.post(
    '/conversation-learning/checkout',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.conversationLearningCheckout),
    asyncHandler(paymentController.createConversationLearningCheckout)
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
