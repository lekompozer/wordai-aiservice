import os
os.environ['OMP_NUM_THREADS'] = '1'  # Quan trọng để tránh xung đột FAISS
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
try:
    from config.config import DEEPSEEK_API_KEY
except ImportError:
    from ..config.config import DEEPSEEK_API_KEY
from src.rag.chatbot import Chatbot
from src.utils.logger import setup_logger
import faiss

faiss.omp_set_num_threads(1)  # Giới hạn thread cho FAISS



logger = setup_logger()

def load_config(config_path: str = "./config/tone_config.json"):
    """Load JSON config file with error handling"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in {config_path}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to load config: {str(e)}")
        raise

# def ingest_documents(chatbot: Chatbot, data_folder: str = "./data"):
#     """Ingest all documents from folder using new processor"""
#     if not Path(data_folder).exists():
#         logger.error(f"Data folder not found: {data_folder}")
#         raise FileNotFoundError(f"Data folder not found: {data_folder}")

#     try:
#         # Sử dụng process_folder thay vì xử lý từng file
#         processed_files = chatbot.document_processor.process_folder(data_folder)
#         total_chunks = 0

#         for filename, chunks in processed_files.items():
#             if chunks:
#                 chatbot.vector_store.add_documents(chunks)
#                 total_chunks += len(chunks)
#                 logger.info(f"Ingested {len(chunks)} chunks from {filename}")
#                 print(f"\nFile: {filename}")
#                 print(f"Số chunks: {len(chunks)}")
#                 print("Mẫu dữ liệu:", chunks[0][:100] + "...")

#         if total_chunks == 0:
#             logger.warning("No valid documents were ingested")
#             print("Cảnh báo: Không có dữ liệu nào được ingest!")
#         else:
#             logger.info(f"Total ingested chunks: {total_chunks}")
#             print(f"\nTổng số chunks đã ingest: {total_chunks}")

#     except Exception as e:
#         logger.error(f"Ingestion failed: {str(e)}")
#         raise

def chat_loop(chatbot: Chatbot):
    """Improved chat loop with better error handling"""
    print("\n" + "="*50)
    print("AI Chatbot with RAG - Type 'exit' to quit")
    print("="*50 + "\n")
    
    while True:
        try:
            query = input("You: ").strip()
            if not query:
                continue
                
            if query.lower() == 'exit':
                break
            
            response = chatbot.generate_response(query)
            print(f"\nAI: {response}\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print("AI: Xin lỗi, hiện tôi đang gặp sự cố. Vui lòng thử lại sau.")

def main():
    try:
        # Load configuration first
        try:
            load_config()
        except Exception as e:
            logger.critical("Failed to load configuration")
            print("Lỗi hệ thống: Không thể tải cấu hình. Vui lòng kiểm tra file config.")
            return

        # Initialize chatbot
        try:
            chatbot = Chatbot(api_key=DEEPSEEK_API_KEY)
        except Exception as e:
            logger.critical(f"Failed to initialize chatbot: {e}")
            print("Lỗi hệ thống: Không thể khởi tạo chatbot.")
            return

        # Ingest documents
        print("\nĐang khởi tạo dữ liệu...")
        data_folder = "./data"
        print(f"Đang xử lý thư mục: {os.path.abspath(data_folder)}")
        
        # Đếm số file một cách an toàn hơn
        data_path = Path(data_folder)
        if data_path.exists() and data_path.is_dir():
            num_files = len([item for item in data_path.iterdir() if item.is_file()])
            print(f"Tìm thấy {num_files} files trong thư mục.")
        else:
            print(f"Thư mục dữ liệu '{data_folder}' không tồn tại hoặc không phải là thư mục.")
        
        try:
            # ✅ SỬA ĐỔI: Gọi phương thức ingest_documents của đối tượng chatbot
            files_ingested_count = chatbot.ingest_documents(data_folder)
            if files_ingested_count > 0:
                logger.info(f"Successfully ingested documents from {files_ingested_count} files.")
            else:
                logger.warning("No documents were ingested or an error occurred during ingestion.")
                print("Cảnh báo: Không có tài liệu nào được xử lý hoặc có lỗi xảy ra.")

        except Exception as e:
            logger.critical(f"Failed to ingest documents: {e}")
            print("Cảnh báo: Có vấn đề khi tải dữ liệu. Chatbot có thể hoạt động không chính xác.")

        # Start chat interface
        chat_loop(chatbot)
        
    except Exception as e:
        logger.critical(f"Critical application error: {e}", exc_info=True)
        print("Rất tiếc, có lỗi nghiêm trọng xảy ra. Vui lòng liên hệ hỗ trợ kỹ thuật.")
    finally:
        print("\nCảm ơn bạn đã sử dụng dịch vụ!")

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method('spawn', force=True)
    main()