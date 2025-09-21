import openai
from config.config import CHATGPT_API_KEY

def test_chatgpt_api():
    """Test ChatGPT API key và models"""
    
    if not CHATGPT_API_KEY:
        print("❌ CHATGPT_API_KEY not found in environment")
        return
    
    try:
        client = openai.OpenAI(api_key=CHATGPT_API_KEY)
        
        # Test 1: List models
        print("Testing ChatGPT API key...")
        models = client.models.list()
        print(f"✅ API key valid. Found {len(models.data)} models")
        
        # Print available models
        gpt_models = [m.id for m in models.data if 'gpt' in m.id.lower()][:5]
        print(f"Available GPT models: {gpt_models}")
        
        # Test 2: Simple completion
        print("\nTesting simple completion...")
        response = client.chat.completions.create(
            model="gpt-4o",  # hoặc "gpt-3.5-turbo"
            messages=[{"role": "user", "content": "Say hello in Vietnamese"}],
            max_tokens=50
        )
        
        print(f"✅ Response: {response.choices[0].message.content}")
        
        # Test 3: Streaming
        print("\nTesting streaming...")
        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Count from 1 to 5 in Vietnamese"}],
            max_tokens=100,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                print(chunk.choices[0].delta.content, end="")
        
        print("\n✅ Streaming test completed")
        
    except Exception as e:
        print(f"❌ ChatGPT API test failed: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    test_chatgpt_api()