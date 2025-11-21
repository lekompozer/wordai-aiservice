from google.genai import types
import inspect

print("Inspecting google.genai.types.Image")
if hasattr(types, "Image"):
    print("types.Image exists")
    print(dir(types.Image))

    # Check fields
    try:
        print("Fields:", list(types.Image.model_fields.keys()))
    except:
        pass

    # Check if it has image_bytes or data
    if hasattr(types.Image, "image_bytes"):
        print("types.Image has image_bytes")
    if hasattr(types.Image, "data"):
        print("types.Image has data")


print("\nInspecting google.genai.types.GeneratedImage")
if hasattr(types, "GeneratedImage"):
    print("types.GeneratedImage exists")
    print(dir(types.GeneratedImage))
    if hasattr(types.GeneratedImage, "image"):
        print("types.GeneratedImage has image attribute")
