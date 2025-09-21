import sys
import os
import json
import time
import requests
from typing import Dict, Any

# Add the current directory to path for imports
sys.path.append(os.path.dirname(__file__))

class SimpleRealEstateTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.endpoint = f"{base_url}/real-estate/deepseek-reasoning"
        
        print(f"🏠 Simple Real Estate Test")
        print(f"📡 Endpoint: {self.endpoint}")

    def check_server(self) -> bool:
        """Check if server is running"""
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=5)
            if response.status_code == 200:
                print(f"✅ Server is running")
                return True
            else:
                print(f"❌ Server error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return False

    def test_question(self, question: str) -> bool:
        """Test a single question"""
        print(f"\n{'='*60}")
        print(f"🔍 TESTING: {question}")
        print(f"{'='*60}")
        
        # Create request
        request_data = {
            "question": question,
            "userId": f"test_user_{int(time.time())}",
            "deviceId": f"test_device_{int(time.time())}",
            "ai_provider": "deepseek",
            "use_backend_ocr": True
        }
        
        try:
            print(f"📤 Sending request...")
            start_time = time.time()
            
            # Stream response
            with requests.post(
                self.endpoint,
                json=request_data,
                stream=True,
                timeout=120,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status_code != 200:
                    print(f"❌ Request failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
                
                print(f"📡 Status: {response.status_code}")
                print(f"\n🔄 LIVE RESPONSE:")
                print("-" * 50)
                
                progress_count = 0
                ai_response = ""
                completion_info = None
                
                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    
                    try:
                        data = json.loads(line[6:])  # Remove "data: " prefix
                        
                        if 'progress' in data:
                            progress_count += 1
                            print(f"📊 [{progress_count:2d}] {data['progress']}")
                            
                        elif 'chunk' in data:
                            chunk = data['chunk']
                            ai_response += chunk
                            print(chunk, end='', flush=True)
                            
                        elif 'done' in data and data['done']:
                            completion_info = data
                            print(f"\n\n✅ COMPLETED")
                            break
                            
                        elif 'error' in data:
                            print(f"\n❌ ERROR: {data['error']}")
                            return False
                            
                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON error: {e}")
                        continue
                
                end_time = time.time()
                total_time = end_time - start_time
                
                # Results
                print(f"\n{'='*60}")
                print(f"📊 RESULTS")
                print(f"{'='*60}")
                print(f"⏱️  Time: {total_time:.2f}s")
                print(f"📈 Progress steps: {progress_count}")
                print(f"📝 AI response length: {len(ai_response)} chars")
                
                if completion_info:
                    print(f"\n✅ COMPLETION INFO:")
                    important_keys = ['web_properties_found', 'web_sources', 'primary_sources', 
                                    'fallback_sources', 'used_fallback', 'analysis_confidence']
                    for key in important_keys:
                        if key in completion_info:
                            print(f"   {key}: {completion_info[key]}")
                
                # Show first part of AI response
                if ai_response:
                    print(f"\n🤖 AI RESPONSE PREVIEW:")
                    print("-" * 50)
                    preview = ai_response[:300] + "..." if len(ai_response) > 300 else ai_response
                    print(preview)
                
                return True
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout after 120s")
            return False
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection error - server not running?")
            return False
        except Exception as e:
            print(f"❌ Test failed: {e}")
            return False

def main():
    """Main test function"""
    print("🏠 SIMPLE REAL ESTATE TEST")
    print("=" * 50)
    print("This will test the endpoint with real data:")
    print("- Real SerpAPI calls")
    print("- Real web scraping") 
    print("- Real DeepSeek AI")
    print("=" * 50)
    
    # Check server
    tester = SimpleRealEstateTest()
    if not tester.check_server():
        print("\n❌ Server not running. Start server first:")
        print("   cd /Users/user/Code/ai-chatbot-rag")
        print("   python serve.py")
        return
    
    # Default question
    default_question = "Định giá Căn hộ Bcons Solary 2PN 63m2 tại TP Dĩ An"
    
    print(f"\n🔍 ENTER YOUR QUESTION:")
    print(f"Default: {default_question}")
    
    user_input = input(f"\nYour question (or press Enter for default): ").strip()
    
    if not user_input:
        question = default_question
        print(f"📝 Using default: {question}")
    else:
        question = user_input
        print(f"📝 Using your question: {question}")
    
    # Test
    print(f"\n🚀 Starting test...")
    success = tester.test_question(question)
    
    if success:
        print(f"\n🎉 Test completed successfully!")
    else:
        print(f"\n💥 Test failed!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")