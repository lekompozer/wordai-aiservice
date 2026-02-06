/**
 * Payment Controller
 * Handles checkout and payment creation using SePay
 */

const crypto = require('crypto');
const axios = require('axios');
const { getDb } = require('../config/database');
const config = require('../config');
const logger = require('../utils/logger');
const { AppError } = require('../middleware/errorHandler');

// Plan pricing (matches Python service)
const PLAN_PRICING = {
    premium: {
        '3_months': 279000,
        '12_months': 990000,
    },
    pro: {
        '3_months': 447000,
        '12_months': 1699000,
    },
    vip: {
        '3_months': 747000,
        '12_months': 2799000,
    },
};

// Points packages pricing (NEW)
const POINTS_PRICING = {
    '50': 50000,    // 50 điểm = 50,000 VND
    '100': 95000,   // 100 điểm = 95,000 VND
    '200': 180000,  // 200 điểm = 180,000 VND
};

/**
 * Generate order invoice number
 * Format: WA-{timestamp}-{user_short}
 */
function generateOrderInvoiceNumber(user_id) {
    const timestamp = Date.now();
    const userShort = user_id.substring(0, 8);
    return `WA-${timestamp}-${userShort}`;
}

/**
 * Generate SePay signature according to documentation
 * Uses HMAC-SHA256 with specific field order
 */
function generateSignature(fields, secretKey) {
    // Fields that must be included in signature (in this exact order)
    const signedFields = [
        'merchant',
        'operation',
        'payment_method',
        'order_amount',
        'currency',
        'order_invoice_number',
        'order_description',
        'customer_id',
        'success_url',
        'error_url',
        'cancel_url'
    ];

    // Build signed string: field1=value1,field2=value2,...
    const signedString = signedFields
        .filter(field => fields[field] !== undefined && fields[field] !== null)
        .map(field => `${field}=${fields[field]}`)
        .join(',');

    logger.debug(`Signature string: ${signedString}`);

    // Create HMAC-SHA256 signature
    const hmac = crypto.createHmac('sha256', secretKey);
    hmac.update(signedString);
    const signature = hmac.digest('base64');

    logger.debug(`Generated signature: ${signature}`);

    return signature;
}

/**
 * Create SePay checkout
 * Returns form fields for frontend to submit to SePay
 * REQUIRES AUTHENTICATION - user_id extracted from Firebase token
 */
async function createCheckout(req, res) {
    // Get authenticated user from Firebase token (set by verifyFirebaseToken middleware)
    const authenticatedUser = req.user;

    if (!authenticatedUser || !authenticatedUser.uid) {
        throw new AppError('Authentication required', 401);
    }

    // Use authenticated user's information
    const user_id = authenticatedUser.uid;  // ✅ From verified Firebase token
    const user_email = authenticatedUser.email;  // ✅ From Firebase
    const user_name = authenticatedUser.name || authenticatedUser.email?.split('@')[0];  // ✅ From Firebase

    // Get plan and duration from request body
    const { plan, duration } = req.body;

    try {
        // Get price
        const price = PLAN_PRICING[plan]?.[duration];
        if (!price) {
            throw new AppError('Invalid plan or duration', 400);
        }

        // Parse duration for display
        const durationMonths = duration === '3_months' ? 3 : 12;

        // Generate order invoice number
        const orderInvoiceNumber = generateOrderInvoiceNumber(user_id);

        // Create payment record in database
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const paymentDoc = {
            user_id,  // ✅ Verified Firebase UID
            order_invoice_number: orderInvoiceNumber,
            plan,
            duration,
            duration_months: durationMonths,
            price,
            status: 'pending',
            payment_method: 'SEPAY_BANK_TRANSFER',
            user_email: user_email || null,  // ✅ From Firebase
            user_name: user_name || null,  // ✅ From Firebase
            sepay_transaction_id: null,
            created_at: new Date(),
            updated_at: new Date(),
        };

        const result = await paymentsCollection.insertOne(paymentDoc);
        const paymentId = result.insertedId.toString();

        logger.info(`Created payment record: ${paymentId} for user: ${user_id} (${user_email})`);

        // Prepare form fields for SePay checkout
        const formFields = {
            merchant: config.sepay.merchantId,
            operation: 'PURCHASE',
            payment_method: 'BANK_TRANSFER',
            order_amount: price.toString(),
            currency: 'VND',
            order_invoice_number: orderInvoiceNumber,
            order_description: `WordAI ${plan.toUpperCase()} - ${durationMonths} tháng`,
            customer_id: user_id,
            success_url: `https://wordai.pro/payment/success`,
            error_url: `https://wordai.pro/payment/error`,
            cancel_url: `https://wordai.pro/payment/cancel`,
        };

        // Generate signature
        formFields.signature = generateSignature(formFields, config.sepay.secretKey);

        logger.info(`Generated checkout form for order: ${orderInvoiceNumber}`);

        // Return form fields for frontend to submit
        res.status(201).json({
            success: true,
            data: {
                payment_id: paymentId,
                order_invoice_number: orderInvoiceNumber,
                checkout_url: config.sepay.checkoutUrl,
                form_fields: formFields,
                amount: price,
                plan,
                duration,
                duration_months: durationMonths,
            },
        });
    } catch (error) {
        logger.error(`Checkout error: ${error.message}`);
        throw error;
    }
}

/**
 * Get payment status
 */
async function getPaymentStatus(req, res) {
    const { order_invoice_number } = req.params;

    try {
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payment = await paymentsCollection.findOne({ order_invoice_number });

        if (!payment) {
            throw new AppError('Payment not found', 404);
        }

        res.json({
            success: true,
            data: {
                payment_id: payment._id.toString(),
                order_invoice_number: payment.order_invoice_number,
                status: payment.status,
                plan: payment.plan,
                duration: payment.duration,
                price: payment.price,
                created_at: payment.created_at,
                completed_at: payment.completed_at || null,
            },
        });
    } catch (error) {
        logger.error(`Get payment status error: ${error.message}`);
        throw error;
    }
}

/**
 * Get user payments
 */
async function getUserPayments(req, res) {
    const { user_id } = req.params;

    try {
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payments = await paymentsCollection
            .find({ user_id })
            .sort({ created_at: -1 })
            .toArray();

        res.json({
            success: true,
            data: payments.map(p => ({
                payment_id: p._id.toString(),
                order_invoice_number: p.order_invoice_number,
                status: p.status,
                plan: p.plan,
                duration: p.duration,
                price: p.price,
                created_at: p.created_at,
                completed_at: p.completed_at || null,
            })),
        });
    } catch (error) {
        logger.error(`Get user payments error: ${error.message}`);
        throw error;
    }
}

/**
 * Create Points Purchase Checkout
 * REQUIRES AUTHENTICATION - user_id extracted from Firebase token
 */
async function createPointsPurchase(req, res) {
    // Get authenticated user from Firebase token
    const authenticatedUser = req.user;

    if (!authenticatedUser || !authenticatedUser.uid) {
        throw new AppError('Authentication required', 401);
    }

    // Use authenticated user's information
    const user_id = authenticatedUser.uid;
    const user_email = authenticatedUser.email;
    const user_name = authenticatedUser.name || authenticatedUser.email?.split('@')[0];

    // Get points amount from request body
    const { points } = req.body;

    try {
        const db = getDb();
        const subscriptionsCollection = db.collection('user_subscriptions');
        const paymentsCollection = db.collection('payments');

        // Check user subscription status (may not exist for new/free users)
        const subscription = await subscriptionsCollection.findOne({ user_id });

        const currentPlan = subscription?.plan || 'free';
        const subscriptionExpiry = subscription?.expires_at;

        // Properly check if subscription is active (convert to boolean)
        const isSubscriptionActive = subscriptionExpiry
            ? new Date(subscriptionExpiry) > new Date()
            : false;

        // Count completed points purchases
        const completedPointsPurchases = await paymentsCollection.countDocuments({
            user_id,
            payment_type: 'points_purchase',
            status: 'completed'
        });

        logger.info(`User ${user_id} - Plan: ${currentPlan}, Active: ${isSubscriptionActive}, Expiry: ${subscriptionExpiry}, Points purchases: ${completedPointsPurchases}`);

        // BUSINESS RULES:
        // 1. FREE user (no subscription): Only 1 point purchase allowed
        // 2. Expired subscription: Only 1 point purchase allowed after expiry
        // 3. Active subscription: Unlimited point purchases

        if (!isSubscriptionActive) {
            // User is FREE or subscription expired
            if (completedPointsPurchases >= 1) {
                throw new AppError(
                    'Bạn đã mua điểm 1 lần. Vui lòng nâng cấp lên gói Premium, Pro hoặc VIP để tiếp tục sử dụng và mua thêm điểm.',
                    403
                );
            }

            logger.warn(`⚠️  User ${user_id} (${currentPlan}, expired/free) - Last chance point purchase`);
        } else {
            logger.info(`✅ User ${user_id} has active subscription - Point purchase allowed`);
        }

        // Get price
        const price = POINTS_PRICING[points];
        if (!price) {
            throw new AppError('Invalid points amount. Valid: 50, 100, 200', 400);
        }

        // Generate order invoice number
        const orderInvoiceNumber = generateOrderInvoiceNumber(user_id);

        // Create payment record

        const paymentDoc = {
            user_id,
            order_invoice_number: orderInvoiceNumber,
            payment_type: 'points_purchase',  // NEW: Distinguish from subscription
            points: parseInt(points),
            price,
            status: 'pending',
            payment_method: 'SEPAY_BANK_TRANSFER',
            user_email: user_email || null,
            user_name: user_name || null,
            sepay_transaction_id: null,
            created_at: new Date(),
            updated_at: new Date(),
        };

        const result = await paymentsCollection.insertOne(paymentDoc);
        const paymentId = result.insertedId.toString();

        logger.info(`Created points purchase payment: ${paymentId} for user: ${user_id} (${points} points)`);

        // Prepare form fields for SePay checkout
        const formFields = {
            merchant: config.sepay.merchantId,
            operation: 'PURCHASE',
            payment_method: 'BANK_TRANSFER',
            order_amount: price.toString(),
            currency: 'VND',
            order_invoice_number: orderInvoiceNumber,
            order_description: `Mua ${points} điểm WordAI`,
            customer_id: user_id,
            success_url: `https://wordai.pro/payment/success`,
            error_url: `https://wordai.pro/payment/error`,
            cancel_url: `https://wordai.pro/payment/cancel`,
        };

        // Generate signature
        formFields.signature = generateSignature(formFields, config.sepay.secretKey);

        logger.info(`Generated points purchase checkout: ${orderInvoiceNumber}`);

        // Return form fields for frontend
        res.status(201).json({
            success: true,
            data: {
                payment_id: paymentId,
                order_invoice_number: orderInvoiceNumber,
                checkout_url: config.sepay.checkoutUrl,
                form_fields: formFields,
                amount: price,
                payment_type: 'points_purchase',
                points: parseInt(points),
            },
        });
    } catch (error) {
        logger.error(`Points purchase checkout error: ${error.message}`);
        throw error;
    }
}

/**
 * Create Book Purchase Checkout
 * REQUIRES AUTHENTICATION - user_id extracted from Firebase token
 */
async function createBookPurchase(req, res) {
    // Get authenticated user from Firebase token
    const authenticatedUser = req.user;

    if (!authenticatedUser || !authenticatedUser.uid) {
        throw new AppError('Authentication required', 401);
    }

    const user_id = authenticatedUser.uid;
    const user_email = authenticatedUser.email;
    const user_name = authenticatedUser.name || authenticatedUser.email?.split('@')[0];

    const { order_id, return_url } = req.body;

    if (!order_id || !order_id.startsWith('BOOK-')) {
        throw new AppError('Invalid book order ID', 400);
    }

    try {
        const db = getDb();
        const bookOrdersCollection = db.collection('book_cash_orders');

        // Get order from book_cash_orders
        const order = await bookOrdersCollection.findOne({ order_id });

        if (!order) {
            throw new AppError('Order not found', 404);
        }

        // Verify order belongs to authenticated user
        if (order.user_id !== user_id) {
            throw new AppError('Unauthorized - Order does not belong to you', 403);
        }

        // Check order status
        if (order.status !== 'pending') {
            throw new AppError(`Order already ${order.status}`, 400);
        }

        // Check expiry
        if (order.expires_at && new Date(order.expires_at) < new Date()) {
            throw new AppError('Order expired', 400);
        }

        logger.info(`Creating book checkout: ${order_id} - Book: ${order.book_id}, Amount: ${order.price_vnd} VND`);

        // Use provided return_url or default to payment result pages
        const defaultSuccessUrl = `https://wordai.pro/payment/success`;
        const defaultErrorUrl = `https://wordai.pro/payment/error`;
        const defaultCancelUrl = `https://wordai.pro/payment/cancel`;

        // Prepare form fields for SePay checkout
        const formFields = {
            merchant: config.sepay.merchantId,
            operation: 'PURCHASE',
            payment_method: 'BANK_TRANSFER',
            order_amount: order.price_vnd.toString(),
            currency: 'VND',
            order_invoice_number: order_id,  // Use BOOK-xxx format for webhook detection
            order_description: `Mua sách: ${order.book_id} (${order.purchase_type})`,
            customer_id: user_id,
            success_url: return_url || defaultSuccessUrl,
            error_url: return_url || defaultErrorUrl,
            cancel_url: return_url || defaultCancelUrl,
        };

        // Generate signature
        formFields.signature = generateSignature(formFields, config.sepay.secretKey);

        logger.info(`✅ Generated book checkout: ${order_id}`);

        // Return form fields for frontend
        res.status(201).json({
            success: true,
            data: {
                order_id: order_id,
                book_id: order.book_id,
                purchase_type: order.purchase_type,
                checkout_url: config.sepay.checkoutUrl,
                form_fields: formFields,
                amount: order.price_vnd,
                payment_type: 'book_purchase',
            },
        });
    } catch (error) {
        logger.error(`Book purchase checkout error: ${error.message}`);
        throw error;
    }
}

module.exports = {
    createCheckout,
    createPointsPurchase,
    createBookPurchase,
    getPaymentStatus,
    getUserPayments,
};
