/**
 * Webhook Controller
 * Handles SePay IPN (Instant Payment Notification) callbacks
 */

const crypto = require('crypto');
const axios = require('axios');
const { getDb } = require('../config/database');
const config = require('../config');
const logger = require('../utils/logger');
const { AppError } = require('../middleware/errorHandler');

/**
 * Verify SePay IPN using X-Secret-Key header
 * According to SePay docs, IPN uses secret key verification, not signature
 */
function verifySecretKey(req) {
    const secretKey = req.headers['x-secret-key'];

    if (!secretKey) {
        logger.error('Missing X-Secret-Key header in IPN request');
        throw new AppError('Missing X-Secret-Key header', 401);
    }

    if (secretKey !== config.sepay.secretKey) {
        logger.error('Invalid X-Secret-Key in IPN request');
        throw new AppError('Invalid secret key', 401);
    }

    return true;
}

/**
 * Handle SePay IPN callback
 * IPN format: { timestamp, notification_type, order, transaction, customer }
 */
async function handleWebhook(req, res) {
    try {
        const payload = req.body;

        logger.info(`Received IPN: ${JSON.stringify(payload)}`);

        // Verify secret key
        verifySecretKey(req);

        const { timestamp, notification_type, order, transaction, customer } = payload;

        if (!order || !order.order_invoice_number) {
            logger.error('Invalid IPN payload: missing order information');
            return res.status(200).json({ success: false, error: 'Invalid payload' });
        }

        const { order_invoice_number } = order;

        logger.info(`Processing IPN: ${notification_type} for order ${order_invoice_number}`);

        // Get payment from database
        const db = getDb();
        const paymentsCollection = db.collection('payments');

        const payment = await paymentsCollection.findOne({ order_invoice_number });

        if (!payment) {
            logger.error(`Payment not found: ${order_invoice_number}`);
            // Still return 200 to acknowledge receipt
            return res.status(200).json({ success: false, error: 'Payment not found' });
        }

        // Check if already processed
        if (payment.status === 'completed' && payment.subscription_activated) {
            logger.info(`Payment already processed and subscription activated: ${order_invoice_number}`);
            return res.status(200).json({ success: true, message: 'Already processed' });
        }

        // Handle different notification types
        if (notification_type === 'ORDER_PAID') {
            // Payment successful - update payment status
            await paymentsCollection.updateOne(
                { order_invoice_number },
                {
                    $set: {
                        status: 'completed',
                        sepay_transaction_id: transaction?.transaction_id || null,
                        completed_at: new Date(),
                        ipn_received_at: new Date(),
                        ipn_payload: payload,
                        updated_at: new Date(),
                    },
                }
            );

            logger.info(`Payment marked as completed: ${order_invoice_number}`);

            // Activate subscription via Python service
            try {
                logger.info(`Activating subscription for user: ${payment.user_id}`);

                const activationResponse = await axios.post(
                    `${config.pythonService.url}/api/v1/subscriptions/activate`,
                    {
                        user_id: payment.user_id,
                        plan: payment.plan,
                        duration_months: payment.duration_months,
                        payment_id: payment._id.toString(),
                        order_invoice_number,
                        payment_method: 'sepay_bank_transfer',
                        amount: payment.price,
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
                            activation_response: activationResponse.data,
                            updated_at: new Date(),
                        },
                    }
                );

                logger.info(`Subscription activation completed for order: ${order_invoice_number}`);
            } catch (error) {
                logger.error(`Failed to activate subscription: ${error.message}`);
                if (error.response) {
                    logger.error(`Python service error: ${JSON.stringify(error.response.data)}`);
                }

                // Don't fail webhook response, we can retry activation later
                await paymentsCollection.updateOne(
                    { order_invoice_number },
                    {
                        $set: {
                            subscription_activated: false,
                            activation_error: error.message,
                            activation_error_details: error.response?.data || null,
                            updated_at: new Date(),
                        },
                    }
                );

                // Still return success to SePay to prevent retries
                return res.status(200).json({
                    success: true,
                    message: 'Payment completed, subscription activation pending retry',
                });
            }

            // Success response to SePay
            return res.status(200).json({
                success: true,
                message: 'Payment and subscription processed successfully',
            });
        } else {
            // Other notification types (ORDER_CANCELLED, ORDER_EXPIRED, etc.)
            logger.info(`Unhandled notification type: ${notification_type}`);

            // Update payment with IPN info
            await paymentsCollection.updateOne(
                { order_invoice_number },
                {
                    $set: {
                        ipn_received_at: new Date(),
                        ipn_payload: payload,
                        updated_at: new Date(),
                    },
                }
            );

            return res.status(200).json({
                success: true,
                message: 'IPN received',
            });
        }
    } catch (error) {
        logger.error(`IPN processing error: ${error.message}`);

        // IMPORTANT: Always return 200 to SePay to prevent endless retries
        // Log error but acknowledge receipt
        return res.status(200).json({
            success: false,
            error: error.message,
        });
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
                duration_months: payment.duration_months,
                payment_id: payment._id.toString(),
                order_invoice_number,
                payment_method: 'sepay_bank_transfer',
                amount: payment.price,
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
                    activation_response: activationResponse.data,
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
