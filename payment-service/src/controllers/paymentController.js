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
 */
async function createCheckout(req, res) {
    const { user_id, plan, duration, user_email, user_name } = req.body;

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
            user_id,
            order_invoice_number: orderInvoiceNumber,
            plan,
            duration,
            duration_months: durationMonths,
            price,
            status: 'pending',
            payment_method: 'sepay_bank_transfer',
            user_email: user_email || null,
            user_name: user_name || null,
            sepay_transaction_id: null,
            created_at: new Date(),
            updated_at: new Date(),
        };

        const result = await paymentsCollection.insertOne(paymentDoc);
        const paymentId = result.insertedId.toString();

        logger.info(`Created payment record: ${paymentId} for user: ${user_id}`);

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

module.exports = {
    createCheckout,
    getPaymentStatus,
    getUserPayments,
};
