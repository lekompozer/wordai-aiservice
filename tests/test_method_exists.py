import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

try:
    from src.rag.chatbot import Chatbot
    
    # Kiểm tra method có tồn tại không
    chatbot = Chatbot()
    
    print("Available methods in Chatbot:")
    methods = [method for method in dir(chatbot) if not method.startswith('_')]
    for method in sorted(methods):
        print(f"  - {method}")
    
    # Kiểm tra method cụ thể
    if hasattr(chatbot, 'generate_response_with_files_streaming'):
        print("\n✅ generate_response_with_files_streaming exists")
    else:
        print("\n❌ generate_response_with_files_streaming NOT found")
        
    if hasattr(chatbot, 'generate_response_with_files'):
        print("✅ generate_response_with_files exists")
    else:
        print("❌ generate_response_with_files NOT found")
        
except Exception as e:
    print(f"Error importing chatbot: {e}")
    import traceback
    traceback.print_exc()