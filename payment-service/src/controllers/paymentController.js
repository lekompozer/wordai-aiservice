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
 * Create SePay checkout
 */
async function createCheckout(req, res) {
    const { user_id, plan, duration, user_email, user_name } = req.body;

    try {
        // Get price
        const price = PLAN_PRICING[plan]?.[duration];
        if (!price) {
            throw new AppError('Invalid plan or duration', 400);
        }

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
            price,
            status: 'pending',
            payment_method: 'sepay_qr',
            user_email: user_email || null,
            user_name: user_name || null,
            sepay_order_id: null,
            sepay_transaction_id: null,
            sepay_response: null,
            created_at: new Date(),
            updated_at: new Date(),
        };

        const result = await paymentsCollection.insertOne(paymentDoc);
        const paymentId = result.insertedId.toString();

        logger.info(`Created payment record: ${paymentId} for user: ${user_id}`);

        // Prepare SePay request
        const sepayPayload = {
            merchant_code: config.sepay.merchantCode,
            order_invoice_number: orderInvoiceNumber,
            amount: price,
            description: `WordAI ${plan.toUpperCase()} - ${duration.replace('_', ' ')}`,
            customer_name: user_name || 'WordAI Customer',
            customer_email: user_email || '',
            return_url: `${config.webhook.url}/return`,
            callback_url: `${config.webhook.url}/callback`,
            sandbox: config.sepay.sandbox,
        };

        // Generate signature
        const signatureString = `${sepayPayload.merchant_code}|${sepayPayload.order_invoice_number}|${sepayPayload.amount}|${config.sepay.secretKey}`;
        const signature = crypto
            .createHash('sha256')
            .update(signatureString)
            .digest('hex');

        sepayPayload.signature = signature;

        logger.info(`Creating SePay order: ${orderInvoiceNumber}`);

        // Call SePay API
        const sepayResponse = await axios.post(
            `${config.sepay.apiUrl}/checkout`,
            sepayPayload,
            {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${config.sepay.apiKey}`,
                },
                timeout: 10000,
            }
        );

        const { order_id, qr_code_url, payment_url } = sepayResponse.data;

        // Update payment with SePay response
        await paymentsCollection.updateOne(
            { _id: result.insertedId },
            {
                $set: {
                    sepay_order_id: order_id,
                    sepay_response: sepayResponse.data,
                    updated_at: new Date(),
                },
            }
        );

        logger.info(`SePay order created: ${order_id} for payment: ${paymentId}`);

        // Return response
        res.status(201).json({
            success: true,
            data: {
                payment_id: paymentId,
                order_invoice_number: orderInvoiceNumber,
                sepay_order_id: order_id,
                qr_code_url,
                payment_url,
                amount: price,
                plan,
                duration,
            },
        });
    } catch (error) {
        logger.error(`Checkout error: ${error.message}`);

        if (error.response) {
            // SePay API error
            logger.error(`SePay API error: ${JSON.stringify(error.response.data)}`);
            throw new AppError(`Payment gateway error: ${error.response.data.message || 'Unknown error'}`, 502);
        }

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
