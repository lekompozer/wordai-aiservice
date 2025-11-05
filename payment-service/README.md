# WordAI Payment Service

Node.js microservice for handling SePay payment integration with WordAI subscription system.

## Features

- ✅ SePay QR code payment integration
- ✅ Webhook handling with signature verification
- ✅ Automatic subscription activation via Python service
- ✅ MongoDB payment record management
- ✅ Rate limiting and security headers
- ✅ Comprehensive logging with Winston
- ✅ Docker support
- ✅ Graceful shutdown

## Architecture

This service is part of a microservice architecture:
- **Payment Service (Node.js)**: Handles SePay integration (this service)
- **Main API (Python/FastAPI)**: Handles business logic, subscriptions, user management
- **NGINX**: API gateway routing requests to both services

## Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
```

## Configuration

See `.env.example` for all available environment variables.

**Required variables:**
- `SEPAY_API_KEY`: Your SePay API key
- `SEPAY_MERCHANT_CODE`: Your merchant code
- `SEPAY_SECRET_KEY`: Secret key for signature verification
- `MONGODB_URI`: MongoDB connection string
- `PYTHON_SERVICE_URL`: URL of Python service (for subscription activation)

## Development

```bash
# Run in development mode with auto-reload
npm run dev

# Run in production mode
npm start
```

## Docker

```bash
# Build image
docker build -t wordai-payment-service .

# Run container
docker run -p 3000:3000 --env-file .env wordai-payment-service
```

## API Endpoints

### Payment Endpoints

**POST /api/v1/payments/checkout**
Create new payment checkout with SePay

Request body:
```json
{
  "user_id": "firebase_uid",
  "plan": "premium",
  "duration": "3_months",
  "user_email": "user@example.com",
  "user_name": "John Doe"
}
```

**GET /api/v1/payments/status/:order_invoice_number**
Get payment status

**GET /api/v1/payments/user/:user_id**
Get all payments for a user

### Webhook Endpoints

**POST /api/v1/webhooks/sepay/callback**
SePay webhook callback (called by SePay after payment)

**GET /api/v1/webhooks/sepay/return**
Return URL after payment (user is redirected here)

**POST /api/v1/webhooks/retry-activation**
Manually retry subscription activation (admin only)

### Health Check

**GET /health**
Service health check

## Logging

Logs are written to:
- Console (with colors)
- File: `/app/logs/payment-service.log` (rotated at 10MB, 5 files kept)

## Security

- Helmet.js for security headers
- CORS with whitelist
- Rate limiting (100 requests per 15 minutes)
- SePay signature verification
- Service-to-service authentication

## Error Handling

All errors are caught and logged with appropriate status codes:
- 400: Bad request (validation errors)
- 401: Unauthorized (signature verification failed)
- 404: Not found
- 502: Payment gateway error
- 500: Internal server error

## Monitoring

Health check endpoint provides:
- Service status
- Uptime
- Timestamp

## License

MIT
