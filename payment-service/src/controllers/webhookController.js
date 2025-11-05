/**
 * Webhook Controller
 * Handles SePay webhook callbacks and activates subscriptions
 */

const crypto = require('crypto');
const axios = require('axios');
const { getDb } = require('../config/database');
const config = require('../config');
const logger = require('../utils/logger');
const { AppError } = require('../middleware/errorHandler');

/**
 * Verify SePay webhook signature
 */
function verifySignature(payload, signature) {
    const signatureString = `${payload.merchant_code}|${payload.order_invoice_number}|${payload.amount}|${payload.status}|${config.sepay.secretKey}`;

    const expectedSignature = crypto
        .createHash('sha256')
        .update(signatureString)
        .digest('hex');

    return expectedSignature === signature;
}

/**
 * Handle SePay webhook callback
 */
async function handleWebhook(req, res) {
    try {
        const payload = req.body;
        const signature = req.headers['x-sepay-signature'];

        logger.info(`Received webhook: ${JSON.stringify(payload)}`);

        // Verify signature
        if (!verifySignature(payload, signature)) {
            logger.error('Invalid webhook signature');
            throw new AppError('Invalid signature', 401);
        }

        const {
            order_invoice_number,
            sepay_order_id,
            sepay_transaction_id,
            status,
            amount,
        } = payload;

        // Get payment from database
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payment = await paymentsCollection.findOne({ order_invoice_number });

        if (!payment) {
            logger.error(`Payment not found: ${order_invoice_number}`);
            throw new AppError('Payment not found', 404);
        }

        // Check if already processed
        if (payment.status === 'completed') {
            logger.info(`Payment already processed: ${order_invoice_number}`);
            return res.json({ success: true, message: 'Already processed' });
        }

        // Update payment status
        await paymentsCollection.updateOne(
            { order_invoice_number },
            {
                $set: {
                    status: status.toLowerCase(),
                    sepay_transaction_id,
                    completed_at: status === 'SUCCESS' ? new Date() : null,
                    webhook_received_at: new Date(),
                    webhook_payload: payload,
                    updated_at: new Date(),
                },
            }
        );

        logger.info(`Updated payment status: ${order_invoice_number} -> ${status}`);

        // If payment successful, activate subscription via Python service
        if (status === 'SUCCESS') {
            try {
                logger.info(`Activating subscription for user: ${payment.user_id}`);

                const activationResponse = await axios.post(
                    `${config.pythonService.url}/api/v1/subscriptions/activate`,
                    {
                        user_id: payment.user_id,
                        plan: payment.plan,
                        duration: payment.duration,
                        payment_id: payment._id.toString(),
                        order_invoice_number,
                        payment_method: 'sepay_qr',
                    },
                    {
                        headers: {
                            'Content-Type': 'application/json',
                            'X-Service-Secret': config.security.apiSecretKey,
                        },
                        timeout: config.pythonService.timeout,
                    }
                );

                logger.info(`Subscription activated: ${JSON.stringify(activationResponse.data)}`);

                // Mark payment as subscription_activated
                await paymentsCollection.updateOne(
                    { order_invoice_number },
                    {
                        $set: {
                            subscription_activated: true,
                            subscription_id: activationResponse.data.subscription_id,
                            updated_at: new Date(),
                        },
                    }
                );
            } catch (error) {
                logger.error(`Failed to activate subscription: ${error.message}`);

                // Don't fail webhook response, we can retry activation later
                await paymentsCollection.updateOne(
                    { order_invoice_number },
                    {
                        $set: {
                            subscription_activated: false,
                            activation_error: error.message,
                            updated_at: new Date(),
                        },
                    }
                );
            }
        }

        // Respond to SePay
        res.json({ success: true, message: 'Webhook processed' });
    } catch (error) {
        logger.error(`Webhook error: ${error.message}`);

        // Still respond with 200 to prevent SePay retries
        res.json({ success: false, error: error.message });
    }
}

/**
 * Handle return URL (user redirected after payment)
 */
async function handleReturn(req, res) {
    const { order_invoice_number } = req.query;

    try {
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payment = await paymentsCollection.findOne({ order_invoice_number });

        if (!payment) {
            return res.redirect(`https://ai.wordai.pro/payment/error?message=Payment not found`);
        }

        if (payment.status === 'completed') {
            return res.redirect(`https://ai.wordai.pro/payment/success?order=${order_invoice_number}`);
        } else {
            return res.redirect(`https://ai.wordai.pro/payment/pending?order=${order_invoice_number}`);
        }
    } catch (error) {
        logger.error(`Return URL error: ${error.message}`);
        return res.redirect(`https://ai.wordai.pro/payment/error?message=System error`);
    }
}

/**
 * Manually retry subscription activation (admin only)
 */
async function retryActivation(req, res) {
    const { order_invoice_number } = req.body;

    try {
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payment = await paymentsCollection.findOne({ order_invoice_number });

        if (!payment) {
            throw new AppError('Payment not found', 404);
        }

        if (payment.status !== 'completed') {
            throw new AppError('Payment not completed', 400);
        }

        if (payment.subscription_activated) {
            throw new AppError('Subscription already activated', 400);
        }

        logger.info(`Retrying activation for user: ${payment.user_id}`);

        const activationResponse = await axios.post(
            `${config.pythonService.url}/api/v1/subscriptions/activate`,
            {
                user_id: payment.user_id,
                plan: payment.plan,
                duration: payment.duration,
                payment_id: payment._id.toString(),
                order_invoice_number,
                payment_method: 'sepay_qr',
            },
            {
                headers: {
                    'Content-Type': 'application/json',
                    'X-Service-Secret': config.security.apiSecretKey,
                },
                timeout: config.pythonService.timeout,
            }
        );

        await paymentsCollection.updateOne(
            { order_invoice_number },
            {
                $set: {
                    subscription_activated: true,
                    subscription_id: activationResponse.data.subscription_id,
                    activation_retry_at: new Date(),
                    updated_at: new Date(),
                },
            }
        );

        logger.info(`Subscription activated on retry: ${activationResponse.data.subscription_id}`);

        res.json({
            success: true,
            message: 'Subscription activated successfully',
            data: activationResponse.data,
        });
    } catch (error) {
        logger.error(`Retry activation error: ${error.message}`);
        throw error;
    }
}

module.exports = {
    handleWebhook,
    handleReturn,
    retryActivation,
};
