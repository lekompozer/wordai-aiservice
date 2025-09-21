import os

# Sử dụng biến môi trường để xác định môi trường
environment = os.getenv("ENVIRONMENT", "development")

if environment == "production":
    from config.production.config import *
    print(f"Loaded PRODUCTION configuration")
elif environment == "staging":
    from config.staging.config import *
    print(f"Loaded STAGING configuration")
else:
    # Fallback cho local development
    try:
        from config.development.config import *
        print(f"Loaded DEVELOPMENT configuration")
    except ImportError:
        print("No specific configuration found, using defaults")
        # Định nghĩa một số config mặc định
        DEBUG = True
        USE_MOCK_EMBEDDING = False
        LOG_LEVEL = "DEBUG"
