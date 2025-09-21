import sys
from pathlib import Path
import base64
sys.path.append(str(Path(__file__).parent))

try:
    from src.rag.chatbot import Chatbot
    
    chatbot = Chatbot()
    
    # Tạo test file data
    test_content = "Lãi suất Vietcombank 12 tháng: 4.8%/năm"
    file_base64 = base64.b64encode(test_content.encode('utf-8')).decode('utf-8')
    
    file_contents = [
        {
            "content": file_base64,
            "content_type": "text/plain",
            "filename": "test.txt",
            "size": len(test_content)
        }
    ]
    
    print("Testing generate_response_with_files_streaming...")
    
    try:
        # Test streaming method
        response_chunks = []
        for chunk in chatbot.generate_response_with_files_streaming(
            query="Lãi suất 12 tháng là bao nhiêu?",
            user_id="test_user",
            file_contents=file_contents
        ):
            response_chunks.append(chunk)
            print(f"Chunk: {chunk[:50]}...")
        
        print(f"\n✅ Streaming completed. Total chunks: {len(response_chunks)}")
        print(f"Full response: {' '.join(response_chunks)}")
        
    except Exception as e:
        print(f"❌ Error in streaming method: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print("Testing generate_response_with_files...")
    
    try:
        # Test non-streaming method  
        response = chatbot.generate_response_with_files(
            query="Lãi suất 12 tháng là bao nhiêu?",
            user_id="test_user",
            file_contents=file_contents
        )
        
        print(f"✅ Non-streaming completed")
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"❌ Error in non-streaming method: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"Error importing or initializing chatbot: {e}")
    import traceback
    traceback.print_exc()