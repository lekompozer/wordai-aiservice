import os
import io
import base64
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Try GEMINI_API_KEY instead of VERTEX_API_KEY
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("GEMINI_API_KEY not found")
    exit(1)

# Use AI Studio (NOT vertexai) with GEMINI_API_KEY
client = genai.Client(api_key=api_key)

# Load the specific image requested by the user
image_path = "docs/wordai/hoian.jpg"
if not os.path.exists(image_path):
    print(f"Image not found: {image_path}")
    exit(1)

with open(image_path, "rb") as f:
    img_bytes = f.read()

print(f"Loaded image: {image_path}, size: {len(img_bytes)} bytes")

# Try multiple models in order
models_to_try = [
    "gemini-2.5-flash-image",
    "gemini-3-pro-image-preview",
    "gemini-2.0-flash-exp",
]

for model_id in models_to_try:
    try:
        print(f"\nAttempting to use generate_content with model: {model_id}")

        image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        prompt = "Transform this image into anime style. Preserve the composition and key elements but apply vibrant anime aesthetic with clean lines and bold colors."

        response = client.models.generate_content(
            model=model_id,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],  # Requesting image output
            ),
        )

        print(f"✅ Success with {model_id}!")
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    print("Received inline image data")
                    output_file = f"output_{model_id.replace('-', '_')}.jpg"
                    with open(output_file, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Saved {output_file}")
                if part.text:
                    print(f"Received text: {part.text}")
        break  # Stop trying other models if successful

    except Exception as e:
        print(f"❌ {model_id} failed: {e}")
        if model_id == models_to_try[-1]:
            print("\n⚠️ All models failed!")
