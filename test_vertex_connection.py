import os
import logging
from google import genai
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

VERTEX_API_KEY = os.getenv("VERTEX_API_KEY")
PROJECT_ID = "wordai-6779e"
LOCATION = "us-central1"


def test_connection_with_project_location():
    print("\n--- Testing with API Key + Project + Location ---")
    try:
        client = genai.Client(
            vertexai=True,
            api_key=VERTEX_API_KEY,
            project=PROJECT_ID,
            location=LOCATION,
        )
        print("✅ Client initialized successfully")
        # Try a simple call if possible, or just check client config
        print(
            f"Client config: {client._api_client._client_info if hasattr(client, '_api_client') else 'N/A'}"
        )
    except Exception as e:
        print(f"❌ Failed: {e}")


def test_connection_only_api_key():
    print("\n--- Testing with Only API Key ---")
    try:
        client = genai.Client(
            vertexai=True,
            api_key=VERTEX_API_KEY,
            location=LOCATION,  # Maybe location is allowed/required?
        )
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed: {e}")


def test_connection_only_api_key_no_location():
    print("\n--- Testing with Only API Key (No Location) ---")
    try:
        client = genai.Client(vertexai=True, api_key=VERTEX_API_KEY)
        print("✅ Client initialized successfully")
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    if not VERTEX_API_KEY:
        print("❌ VERTEX_API_KEY not found in env")
    else:
        print(f"Found VERTEX_API_KEY: {VERTEX_API_KEY[:5]}...")
        test_connection_with_project_location()
        test_connection_only_api_key()
        test_connection_only_api_key_no_location()
