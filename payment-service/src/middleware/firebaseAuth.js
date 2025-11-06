/**
 * Firebase Authentication Middleware
 * Verifies Firebase ID tokens and extracts user information
 */

const admin = require('firebase-admin');
const logger = require('../config/logger');
const { AppError } = require('./errorHandler');

let isInitialized = false;

/**
 * Initialize Firebase Admin SDK
 */
function initializeFirebase() {
    if (isInitialized) {
        return;
    }

    try {
        // Check if Firebase credentials are provided
        const credentialsPath = process.env.FIREBASE_CREDENTIALS_PATH || '../../../firebase-credentials.json';

        // Try to initialize with service account
        try {
            const serviceAccount = require(credentialsPath);
            admin.initializeApp({
                credential: admin.credential.cert(serviceAccount),
            });
            logger.info('✅ Firebase Admin SDK initialized with service account');
        } catch (error) {
            // Fallback to application default credentials
            admin.initializeApp({
                credential: admin.credential.applicationDefault(),
            });
            logger.info('✅ Firebase Admin SDK initialized with default credentials');
        }

        isInitialized = true;
    } catch (error) {
        logger.error(`❌ Failed to initialize Firebase Admin SDK: ${error.message}`);
        throw error;
    }
}

/**
 * Middleware to verify Firebase ID token
 * Extracts and attaches user information to req.user
 */
async function verifyFirebaseToken(req, res, next) {
    try {
        // Initialize Firebase if not already done
        if (!isInitialized) {
            initializeFirebase();
        }

        // Get token from Authorization header
        const authHeader = req.headers.authorization;

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            throw new AppError('Missing or invalid Authorization header. Expected format: Bearer <token>', 401);
        }

        const idToken = authHeader.split('Bearer ')[1];

        if (!idToken) {
            throw new AppError('No Firebase ID token provided', 401);
        }

        // Verify the token
        const decodedToken = await admin.auth().verifyIdToken(idToken);

        // Attach user information to request
        req.user = {
            uid: decodedToken.uid,
            email: decodedToken.email || null,
            emailVerified: decodedToken.email_verified || false,
            name: decodedToken.name || null,
            picture: decodedToken.picture || null,
        };

        logger.info(`✅ Authenticated user: ${req.user.uid} (${req.user.email})`);
        next();
    } catch (error) {
        if (error.code === 'auth/id-token-expired') {
            return next(new AppError('Firebase token has expired', 401));
        }
        if (error.code === 'auth/argument-error') {
            return next(new AppError('Invalid Firebase token format', 401));
        }
        if (error instanceof AppError) {
            return next(error);
        }

        logger.error(`Firebase auth error: ${error.message}`);
        return next(new AppError('Authentication failed', 401));
    }
}

/**
 * Optional authentication middleware
 * Does not fail if token is missing, but verifies if present
 */
async function optionalFirebaseAuth(req, res, next) {
    try {
        const authHeader = req.headers.authorization;

        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            // No token provided, continue without authentication
            return next();
        }

        // Token provided, verify it
        await verifyFirebaseToken(req, res, next);
    } catch (error) {
        // Authentication failed, but continue anyway
        logger.warn(`Optional auth failed: ${error.message}`);
        next();
    }
}

module.exports = {
    initializeFirebase,
    verifyFirebaseToken,
    optionalFirebaseAuth,
};
