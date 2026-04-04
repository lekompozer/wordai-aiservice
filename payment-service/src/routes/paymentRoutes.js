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

// Create combo purchase - REQUIRES AUTHENTICATION
router.post(
    '/checkout/combos',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.comboPurchase),
    asyncHandler(paymentController.createComboPurchase)
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

// Create AI Bundle subscription - REQUIRES AUTHENTICATION
router.post(
    '/ai-bundle/checkout',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    validateBody(schemas.aiBundleCheckout),
    asyncHandler(paymentController.createAiBundleCheckout)
);

// Create audit purchase (Social Brand Compare) - REQUIRES AUTHENTICATION
router.post(
    '/audit-purchase',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    asyncHandler(paymentController.createAuditPurchase)
);

// Create content plan purchase (SEPAY cash payment) - REQUIRES AUTHENTICATION
router.post(
    '/content-plan/checkout',
    verifyFirebaseToken,  // ✅ Firebase auth middleware
    asyncHandler(paymentController.createContentPlanCheckout)
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
