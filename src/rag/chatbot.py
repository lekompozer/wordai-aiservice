import os
import logging
from src.utils.logger import setup_logger

logger = setup_logger()
import requests
from typing import Dict, List, Optional, Tuple
from .vector_store import VectorStore, Document
from .document_processor import DocumentProcessor
from src.utils.tone_adjuster import ToneAdjuster
from src.rag.fallback_handler import FallbackHandler
from config.config import DEEPSEEK_API_KEY, RAG_SETTINGS
import os

os.environ["OMP_NUM_THREADS"] = "1"  # Quan trọng để tránh xung đột FAISS
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import faiss

faiss.omp_set_num_threads(1)  # Giới hạn thread cho FAISS
# Thêm imports
from src.database.db_manager import DBManager
from src.database.conversation_manager import ConversationManager


class Chatbot:
    def __init__(self, api_key: str = DEEPSEEK_API_KEY):
        self.api_key = api_key
        self.vector_store = VectorStore()
        self.document_processor = DocumentProcessor()
        self.tone_adjuster = ToneAdjuster()
        self.fallback_handler = FallbackHandler()
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.logger = logger

        # Khởi tạo database và conversation manager
        self.db_manager = DBManager()
        self.conversation_manager = ConversationManager(
            db_manager=self.db_manager,
            max_token_limit=64000,
            system_reserved_tokens=1000,
        )

    def _preprocess_query(self, query: str) -> str:
        """Chuẩn hóa thời gian và từ khóa trong câu hỏi"""
        import re

        # 1. Thay thế năm tương lai bằng năm hiện tại (2025)
        query = re.sub(r"(tháng\s*\d+\s*năm\s*)20[2-9][0-9]", r"\g<1>2025", query)

        # 2. Chuẩn hóa cách viết Vietcombank và kỳ hạn
        query = re.sub(
            r"viet\s*combank|vietcom\s*bank", "Vietcombank", query, flags=re.IGNORECASE
        )
        query = re.sub(r"ky\s*han|kỳ\s*hạn", "kỳ hạn", query, flags=re.IGNORECASE)

        # 3. Loại bỏ từ thừa (nếu cần)
        query = re.sub(r"là\s*\?", "", query).strip()

        return query

    def generate_response(self, query: str) -> str:
        try:
            # Chuẩn hóa câu hỏi
            processed_query = self._preprocess_query(query)
            self.logger.debug(f"Query sau chuẩn hóa: {processed_query}")

            # Tìm kiếm trong vector_store
            results, similarity_scores = self.vector_store.search_with_scores(
                processed_query, top_k=4
            )

            # Log kết quả tìm kiếm để debug
            self.logger.debug(f"Search results: {results}")
            self.logger.debug(f"Similarity scores: {similarity_scores}")

            print("\n=== DEBUG ===")
            print(
                "Top contexts:",
                [doc.content[:80] + "..." for doc in results] if results else "None",
            )
            print(
                "Similarity scores:", similarity_scores if similarity_scores else "None"
            )

            # Lấy các chunk liên quan nhất
            top_contexts = [doc.content for doc in results[:3]]

            # Kết hợp các chunk
            combined_context = "\n\n".join(top_contexts)
            response = self._generate_rag_response(processed_query, [combined_context])
            return f"[Theo dữ liệu ứng dụng] {response}"

        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return self.fallback_handler.get_fallback_response(
                query="Xin lỗi, tôi đang gặp sự cố", tone="neutral"
            )

    def _generate_rag_response(self, query: str, contexts: List[str]) -> str:
        # Kết hợp 3 chunk có điểm cao nhất thành một context duy nhất
        combined_context = contexts[0]
        prompt = self.conversation_manager._format_prompt(query, combined_context)
        self.logger.debug(
            f"Generated prompt: {prompt[:500]}..."
        )  # Log 500 ký tự đầu tiên của prompt
        contexts = None  # Giải phóng bộ nhớ
        return self._call_deepseek_api(prompt)

    def _call_deepseek_api(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 5000,
        }
        try:
            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=120
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            self.logger.error("Deepseek API timeout")
            return "Xin lỗi, hiện tôi không thể kết nối đến hệ thống. Vui lòng thử lại sau."
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Deepseek API error: {e}")
            return (
                "Xin lỗi, hiện tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau."
            )

    # Thêm phương thức streaming mới
    def _call_deepseek_api_streaming(self, prompt: str):
        """Phiên bản streaming của _call_deepseek_api"""
        import json

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 5000,
            "stream": True,  # Bật chế độ streaming
        }

        try:
            with requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=120,
                stream=True,  # Quan trọng để requests giữ kết nối
            ) as response:
                response.raise_for_status()

                # Xử lý từng chunk dữ liệu
                for line in response.iter_lines():
                    if line:
                        # Bỏ qua dòng "data: "
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]  # Bỏ 'data: '

                            # Nếu là [DONE] thì dừng
                            if line == "[DONE]":
                                break

                            try:
                                # Parse JSON từ mỗi chunk
                                chunk_data = json.loads(line)
                                # Kiểm tra nếu có dữ liệu
                                if (
                                    "choices" in chunk_data
                                    and len(chunk_data["choices"]) > 0
                                ):
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                self.logger.warning(
                                    f"Failed to parse JSON from line: {line}"
                                )
                                continue

        except requests.exceptions.Timeout:
            self.logger.error("Deepseek API timeout")
            yield "Xin lỗi, hiện tôi không thể kết nối đến hệ thống. Vui lòng thử lại sau."
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Deepseek API error: {e}")
            yield "Xin lỗi, hiện tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau."

    def clear_vector_store(self):
        """Xóa tất cả dữ liệu trong vector store để nạp lại từ đầu"""
        self.logger.info("Clearing vector store")
        if hasattr(self.vector_store, "clear"):
            self.vector_store.clear()
        else:
            self.vector_store = VectorStore()  # Tạo mới nếu không có phương thức clear
        self.logger.info("Vector store cleared")

    def ingest_document(self, file_path: str):
        """Xử lý một file và thêm vào vector store"""
        self.logger.info(f"Processing file: {file_path}")
        try:
            documents = self.document_processor.process_file(file_path)
            self.logger.info(f"Extracted {len(documents)} documents from {file_path}")
            self.vector_store.add_documents(documents)
            self.logger.info(f"Added {len(documents)} documents to vector store")
            return len(documents)
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return 0

    def ingest_documents(self, data_folder: str = None):
        """
        Ingest tất cả các file hợp lệ trong thư mục data_folder vào vector store,
        sử dụng cùng logic với main.py
        """
        # Sử dụng biến môi trường DATA_DIR nếu data_folder không được chỉ định
        if data_folder is None:
            data_folder = os.getenv("DATA_DIR", "./data")

        self.logger.info(f"Loading documents from {data_folder}")

        if not os.path.exists(data_folder):
            self.logger.warning(f"Directory not found: {data_folder}")
            return 0

        # Xóa dữ liệu cũ để đảm bảo nhất quán
        self.clear_vector_store()

        try:
            # Sử dụng process_folder giống main.py
            processed_files = self.document_processor.process_folder(data_folder)
            total_chunks = 0

            for filename, chunks in processed_files.items():
                if chunks:
                    self.vector_store.add_documents(chunks)
                total_chunks += len(chunks)
                self.logger.info(f"Ingested {len(chunks)} chunks from {filename}")

            self.logger.info(f"Total ingested chunks: {total_chunks}")
            return len(processed_files)
        except Exception as e:
            self.logger.error(f"Ingestion failed: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return 0

    def generate_response_streaming(self, query: str):
        """Phiên bản streaming của generate_response"""
        try:
            # Chuẩn hóa câu hỏi
            processed_query = self._preprocess_query(query)
            self.logger.debug(f"Query sau chuẩn hóa: {processed_query}")

            # Tìm kiếm trong vector_store
            results, similarity_scores = self.vector_store.search_with_scores(
                processed_query, top_k=4
            )

            # Log kết quả tìm kiếm để debug
            self.logger.debug(f"Search results: {results}")
            self.logger.debug(f"Similarity scores: {similarity_scores}")

            print("\n=== DEBUG ===")
            print(
                "Top contexts:",
                [doc.content[:80] + "..." for doc in results] if results else "None",
            )
            print(
                "Similarity scores:", similarity_scores if similarity_scores else "None"
            )

            # Lấy các chunk liên quan nhất
            top_contexts = [doc.content for doc in results[:3]]

            # Kết hợp các chunk
            combined_context = "\n\n".join(top_contexts)

            # ✅ SỬ DỤNG _format_prompt TỪ CONVERSATION_MANAGER
            prompt = self.conversation_manager._format_prompt(
                processed_query, combined_context
            )
            print(f"Prompt đã tạo (độ dài: {len(prompt)}):")
            print(
                f"--- Bắt đầu ---\n{prompt[:200]}...\n... {prompt[-200:]}\n--- Kết thúc ---"
            )

            # QUAN TRỌNG: Sử dụng yield from thay vì return
            yield from self._call_deepseek_api_streaming(prompt)

        except Exception as e:
            self.logger.error(f"Error generating streaming response: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            yield "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn."

    def generate_response_with_history(self, query: str, user_id: str) -> str:
        """
        Tạo câu trả lời với lịch sử hội thoại từ database

        Args:
            query: Câu hỏi của người dùng
            user_id: ID của người dùng

        Returns:
            str: Câu trả lời
        """
        try:
            # Chuẩn hóa câu hỏi
            processed_query = self._preprocess_query(query)
            self.logger.debug(f"Query sau chuẩn hóa: {processed_query}")

            # Tìm kiếm trong vector_store
            results, similarity_scores = self.vector_store.search_with_scores(
                processed_query, top_k=4
            )

            # Lấy các chunk liên quan nhất
            top_contexts = [doc.content for doc in results[:3]]

            # Kết hợp các chunk
            combined_context = "\n\n".join(top_contexts)

            # Format các tin nhắn với lịch sử hội thoại
            messages = self.conversation_manager.format_messages_for_api(
                user_id=user_id,
                rag_context=combined_context,
                current_query=processed_query,
                use_legacy_format=True,  # ← SỬ DỤNG _format_prompt
            )

            # Gọi API với messages đã format
            response = self._call_deepseek_api_with_messages(messages)

            # Lưu câu hỏi và câu trả lời vào database
            self.conversation_manager.add_message(user_id, "user", processed_query)
            self.conversation_manager.add_message(user_id, "assistant", response)

            return f"[Theo dữ liệu ứng dụng] {response}"

        except Exception as e:
            self.logger.error(f"Error generating response with history: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            return self.fallback_handler.get_fallback_response(
                query="Xin lỗi, tôi đang gặp sự cố", tone="neutral"
            )

    def _call_deepseek_api_with_messages(self, messages: List[Dict]) -> str:
        """Gọi DeepSeek API với messages đã format"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 5000,
        }

        try:
            response = requests.post(
                self.api_url, headers=headers, json=payload, timeout=120
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            self.logger.error("Deepseek API timeout")
            return "Xin lỗi, hiện tôi không thể kết nối đến hệ thống. Vui lòng thử lại sau."
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Deepseek API error: {e}")
            return (
                "Xin lỗi, hiện tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau."
            )

    # Thêm phương thức streaming với lịch sử
    def generate_response_streaming_with_history(self, query: str, user_id: str):
        """Phiên bản streaming với lịch sử hội thoại từ database"""
        try:
            # Chuẩn hóa câu hỏi
            processed_query = self._preprocess_query(query)

            # Tìm kiếm trong vector_store
            results, similarity_scores = self.vector_store.search_with_scores(
                processed_query, top_k=4
            )

            # Print debug info
            print("\n=== DEBUG ===")
            print(
                "Top contexts:",
                [doc.content[:80] + "..." for doc in results] if results else "None",
            )
            print(
                "Similarity scores:", similarity_scores if similarity_scores else "None"
            )

            # Lấy các chunk liên quan nhất
            top_contexts = [doc.content for doc in results[:3]]

            # Kết hợp các chunk
            combined_context = "\n\n".join(top_contexts)

            # Format tin nhắn với lịch sử hội thoại
            messages = self.conversation_manager.format_messages_for_api(
                user_id=user_id,
                rag_context=combined_context,
                current_query=processed_query,
                use_legacy_format=True,  # ← SỬ DỤNG _format_prompt
            )

            # Print debug về messages
            token_count = sum(
                self.conversation_manager.count_tokens(msg["content"])
                for msg in messages
            )
            print(f"Total message count: {len(messages)}, total tokens: {token_count}")

            # Thu thập response để lưu vào database
            full_response = ""

            # Gọi API streaming với messages
            for chunk in self._call_deepseek_api_streaming_with_messages(messages):
                full_response += chunk
                yield chunk

            # Lưu câu hỏi và câu trả lời vào database
            self.conversation_manager.add_message(user_id, "user", processed_query)
            self.conversation_manager.add_message(user_id, "assistant", full_response)

        except Exception as e:
            self.logger.error(f"Error generating streaming response with history: {e}")
            import traceback

            self.logger.error(traceback.format_exc())
            yield "Xin lỗi, tôi đang gặp sự cố khi xử lý câu hỏi của bạn."

    def _call_deepseek_api_streaming_with_messages(self, messages: List[Dict]):
        """Phiên bản streaming gọi API với messages đã format"""
        import json

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 5000,
            "stream": True,
        }

        try:
            with requests.post(
                self.api_url, headers=headers, json=payload, timeout=120, stream=True
            ) as response:
                response.raise_for_status()

                # Xử lý từng chunk dữ liệu
                for line in response.iter_lines():
                    if line:
                        # Bỏ qua dòng "data: "
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]  # Bỏ 'data: '

                            # Nếu là [DONE] thì dừng
                            if line == "[DONE]":
                                break

                            try:
                                # Parse JSON từ mỗi chunk
                                chunk_data = json.loads(line)
                                # Kiểm tra nếu có dữ liệu
                                if (
                                    "choices" in chunk_data
                                    and len(chunk_data["choices"]) > 0
                                ):
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                self.logger.warning(
                                    f"Failed to parse JSON from line: {line}"
                                )
                                continue

        except requests.exceptions.Timeout:
            self.logger.error("Deepseek API timeout")
            yield "Xin lỗi, hiện tôi không thể kết nối đến hệ thống. Vui lòng thử lại sau."
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Deepseek API error: {e}")
            yield "Xin lỗi, hiện tôi không thể trả lời câu hỏi này. Vui lòng thử lại sau."

    async def process_files_streaming(
        self,
        query: str,
        user_id: str,
        files: List[Dict],
        ai_provider: str,
        ai_provider_manager=None,
    ):
        """
        ✅ UNIFIED: Single method for all file processing with any AI provider
        """
        try:
            print(f"🔄 Processing with {ai_provider}")
            print(f"📁 Files: {len(files)}")
            print(f"👤 User: {user_id}")
            print(
                f"🔧 AI Provider Manager: {'Available' if ai_provider_manager else 'None'}"
            )

            # ✅ DEBUG: Log incoming files
            for i, file_data in enumerate(files):
                print(f"📄 File {i+1}: {file_data.get('filename', 'unknown')}")
                print(f"   Content-Type: {file_data.get('content_type', 'unknown')}")
                print(f"   Keys: {list(file_data.keys())}")

                # Log URL fields specifically
                url_fields = ["url", "public_url", "url_image"]
                for field in url_fields:
                    value = file_data.get(field, "")
                    print(f"   {field}: {value if value else 'EMPTY'}")
            # ✅ STEP 1: PREPROCESS QUERY
            processed_query = self._preprocess_query(query)
            print(f"🔍 Processed query: {processed_query[:100]}...")

            # ✅ STEP 2: GET RAG CONTEXT (SHARED)
            results, _ = self.vector_store.search_with_scores(processed_query, top_k=4)
            top_contexts = [doc.content for doc in results[:3]]
            combined_context = "\n\n".join(top_contexts)
            print(f"📚 RAG context: {len(combined_context)} chars")
            # ✅ STEP 3: PROCESS FILES (UNIFIED)
            file_content = await self._process_file_contents(files)
            print(f"📄 File content: {len(file_content)} chars")
            # ✅ STEP 4: CREATE ENHANCED QUERY
            enhanced_query = (
                processed_query + file_content if file_content else processed_query
            )
            print(f"🎯 Enhanced query: {len(enhanced_query)} chars")
            # ✅ STEP 5: CALL APPROPRIATE AI PROVIDER
            full_response = ""

            if ai_provider == "deepseek":
                # DeepSeek: Use legacy format
                messages = self.conversation_manager.format_messages_for_api(
                    user_id=user_id,
                    rag_context=combined_context,
                    current_query=enhanced_query,
                    use_legacy_format=True,
                )

                for chunk in self._call_deepseek_api_streaming_with_messages(messages):
                    full_response += chunk
                    yield chunk

            elif ai_provider == "chatgpt":
                # ✅ CHECK IF AI_PROVIDER_MANAGER IS PROVIDED
                if not ai_provider_manager:
                    print(f"❌ ai_provider_manager not provided for ChatGPT")
                    yield "Error: AI Provider Manager not available for ChatGPT"
                    return

                # ChatGPT: Use multimodal format
                print(f"🎬 Preparing multimodal messages...")
                messages = await self._prepare_multimodal_messages(
                    query=enhanced_query,
                    user_id=user_id,
                    files=files,
                    rag_context=combined_context,
                )
                print(f"📨 ChatGPT messages prepared: {len(messages)}")
                # ✅ COMPREHENSIVE PAYLOAD LOGGING
                print(f"🚀 === FULL CHATGPT PAYLOAD DEBUG ===")
                print(f"📊 Total messages: {len(messages)}")
                print(f"👤 User ID: {user_id}")
                print(f"🔧 AI Provider: {ai_provider}")
                print(f"📁 Files count: {len(files)}")

                # Log each message in detail
                for i, msg in enumerate(messages):
                    print(f"\n📋 Message {i+1}:")
                    print(f"   Role: {msg['role']}")

                    if msg["role"] == "system":
                        content = msg["content"]
                        print(f"   Content type: String")
                        print(f"   Content length: {len(content)} chars")
                        print(f"   Sample (first 150 chars): {content[:150]}...")
                        print(f"   Sample (last 150 chars): ...{content[-150:]}")

                    elif msg["role"] == "user":
                        if isinstance(msg["content"], list):
                            print(f"   Content type: Multimodal Array")
                            print(f"   Items count: {len(msg['content'])}")

                            for j, item in enumerate(msg["content"]):
                                print(f"     Item {j+1}:")
                                print(f"       Type: {item['type']}")

                                if item["type"] == "text":
                                    text_content = item["text"]
                                    print(
                                        f"       Text length: {len(text_content)} chars"
                                    )
                                    print(
                                        f"       Text sample (first 100): {text_content[:100]}..."
                                    )
                                    if len(text_content) > 200:
                                        print(
                                            f"       Text sample (last 100): ...{text_content[-100:]}"
                                        )

                                elif item["type"] == "image_url":
                                    image_info = item["image_url"]
                                    url = image_info["url"]
                                    detail = image_info.get("detail", "default")

                                    print(f"       Image URL: {url}")
                                    print(f"       Image detail: {detail}")
                                    print(
                                        f"       URL type: {'Public URL' if url.startswith('http') else 'Base64 Data URL'}"
                                    )

                                    if url.startswith("http"):
                                        print(
                                            f"       Domain: {url.split('/')[2] if len(url.split('/')) > 2 else 'unknown'}"
                                        )
                                        print(
                                            f"       Path: /{'/'.join(url.split('/')[3:]) if len(url.split('/')) > 3 else ''}"
                                        )
                                    else:
                                        print(f"       Data URL prefix: {url[:50]}...")

                        else:
                            content = msg["content"]
                            print(f"   Content type: String")
                            print(f"   Content length: {len(content)} chars")
                            print(f"   Sample: {content[:100]}...")

                    elif msg["role"] == "assistant":
                        content = msg["content"]
                        print(f"   Content type: String")
                        print(f"   Content length: {len(content)} chars")
                        print(f"   Sample: {content[:100]}...")

                # ✅ LOG RAW JSON PAYLOAD (for debugging)
                print(f"\n🔍 === RAW JSON STRUCTURE ===")
                import json

                try:
                    # Create a safe version for logging (truncate long content)
                    safe_messages = []
                    for msg in messages:
                        safe_msg = {"role": msg["role"]}

                        if msg["role"] == "system":
                            safe_msg["content"] = (
                                msg["content"][:200] + "...[TRUNCATED]"
                                if len(msg["content"]) > 200
                                else msg["content"]
                            )
                        elif msg["role"] == "user":
                            if isinstance(msg["content"], list):
                                safe_content = []
                                for item in msg["content"]:
                                    if item["type"] == "text":
                                        safe_item = {
                                            "type": "text",
                                            "text": (
                                                item["text"][:200] + "...[TRUNCATED]"
                                                if len(item["text"]) > 200
                                                else item["text"]
                                            ),
                                        }
                                    elif item["type"] == "image_url":
                                        safe_item = {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": (
                                                    item["image_url"]["url"][:100]
                                                    + "...[TRUNCATED]"
                                                    if len(item["image_url"]["url"])
                                                    > 100
                                                    else item["image_url"]["url"]
                                                ),
                                                "detail": item["image_url"].get(
                                                    "detail", "default"
                                                ),
                                            },
                                        }
                                    safe_content.append(safe_item)
                                safe_msg["content"] = safe_content
                            else:
                                safe_msg["content"] = (
                                    msg["content"][:200] + "...[TRUNCATED]"
                                    if len(msg["content"]) > 200
                                    else msg["content"]
                                )
                        else:
                            safe_msg["content"] = (
                                msg["content"][:200] + "...[TRUNCATED]"
                                if len(msg["content"]) > 200
                                else msg["content"]
                            )

                        safe_messages.append(safe_msg)

                    json_payload = json.dumps(
                        safe_messages, indent=2, ensure_ascii=False
                    )
                    print(f"JSON Payload (truncated):\n{json_payload}")

                except Exception as json_error:
                    print(f"❌ JSON serialization error: {json_error}")

                print(f"🚀 === END CHATGPT PAYLOAD DEBUG ===\n")
                # ✅ LOG TOKEN BREAKDOWN WITH MULTIMODAL SUPPORT
                try:
                    total_tokens = 0
                    system_tokens = 0
                    history_tokens = 0
                    query_tokens = 0

                    for msg in messages:
                        if msg["role"] == "system":
                            tokens = self.conversation_manager.count_tokens(
                                msg["content"]
                            )
                            system_tokens += tokens
                            total_tokens += tokens
                        elif msg["role"] == "user":
                            # Handle multimodal content
                            if isinstance(msg["content"], list):
                                for content_item in msg["content"]:
                                    if content_item["type"] == "text":
                                        tokens = self.conversation_manager.count_tokens(
                                            content_item["text"]
                                        )
                                        query_tokens += tokens
                                        total_tokens += tokens
                                    elif content_item["type"] == "image_url":
                                        # ChatGPT image token cost: ~1000 tokens per image
                                        image_tokens = 1000
                                        query_tokens += image_tokens
                                        total_tokens += image_tokens
                                        print(
                                            f"🖼️ Image detected: +{image_tokens} tokens"
                                        )
                            else:
                                tokens = self.conversation_manager.count_tokens(
                                    msg["content"]
                                )
                                query_tokens += tokens
                                total_tokens += tokens
                        elif msg["role"] == "assistant":
                            tokens = self.conversation_manager.count_tokens(
                                msg["content"]
                            )
                            history_tokens += tokens
                            total_tokens += tokens

                    # ✅ LOG DETAILED TOKEN BREAKDOWN
                    has_images = any(
                        isinstance(msg["content"], list)
                        and any(
                            item.get("type") == "image_url" for item in msg["content"]
                        )
                        for msg in messages
                        if msg["role"] == "user"
                    )

                    print(
                        f"📊 Token breakdown (Modern) - System: {system_tokens}, History: {history_tokens}, Query: {query_tokens}, Total: {total_tokens}"
                    )
                    print(
                        f"📨 ChatGPT request - Model: gpt-4o, Reasoning: False, Has Images: {has_images}, Messages: {len(messages)}"
                    )

                except Exception as token_error:
                    print(f"⚠️ Token counting error: {token_error}")

                print(f"🤖 Calling ChatGPT via ai_provider_manager")

                async for chunk in ai_provider_manager.chat_completion_stream(
                    messages, "chatgpt"
                ):
                    full_response += chunk
                    yield chunk

            # ✅ STEP 6: SAVE CONVERSATION (ONCE, AT END)
            print(f"💾 Saving conversation to database...")
            self.conversation_manager.add_message(user_id, "user", processed_query)
            self.conversation_manager.add_message(user_id, "assistant", full_response)
            print(f"✅ Conversation saved for {user_id}")

        except Exception as e:
            print(f"❌ Core processing error: {e}")
            import traceback

            print(f"🔍 Full traceback: {traceback.format_exc()}")
            yield f"Error: {str(e)}"

    async def _process_file_contents(self, files: List[Dict]) -> str:
        """
        ✅ UNIFIED FILE PROCESSING: Handle all file types
        """
        if not files:
            return ""

        file_text = "\n\n=== FILES ===\n"

        for file_data in files:
            filename = file_data.get("filename", "file")
            content_type = file_data.get("content_type", "")

            # Try OCR/extracted text first
            ocr_text = file_data.get("ocr_text", "")
            extracted_text = file_data.get("extracted_text", "")

            if ocr_text:
                file_text += f"\n--- {filename} ---\n{ocr_text}\n"
            elif extracted_text:
                file_text += f"\n--- {filename} ---\n{extracted_text}\n"
            else:
                # Extract from base64 if needed
                file_base64 = file_data.get("content", "")
                if file_base64 and content_type == "application/pdf":
                    extracted = await self._extract_pdf_text(file_base64, filename)
                    file_text += f"\n--- {filename} ---\n{extracted}\n"
                elif file_base64:
                    try:
                        import base64

                        decoded = base64.b64decode(file_base64).decode("utf-8")
                        file_text += f"\n--- {filename} ---\n{decoded}\n"
                    except:
                        file_text += f"\n--- {filename} (unprocessable) ---\n"

        return file_text

    async def _extract_pdf_text(self, file_base64: str, filename: str) -> str:
        """
        ⚠️ DEPRECATED: PDF extraction now uses Gemini AI instead of PyMuPDF
        This method should not be called anymore - use Gemini AI for PDF extraction
        """
        print(
            f"❌ _extract_pdf_text called but PyMuPDF is removed. Use Gemini AI for PDF extraction."
        )
        return f"⚠️ PDF extraction via PyMuPDF is deprecated. File: {filename} - Use Gemini AI for document extraction instead."

        # OLD CODE - REMOVED PyMuPDF implementation:
        # try:
        #     import base64
        #     pdf_bytes = base64.b64decode(file_base64)
        #     pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        #     ... [PyMuPDF processing code removed] ...
        # except Exception as e:
        #     return f"(PDF extraction failed: {str(e)})"

    def _clean_pdf_content(self, text: str) -> str:
        """
        ✅ CLEAN PDF CONTENT: Remove noise, keep important info
        """
        import re

        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove page numbers (standalone numbers)
        text = re.sub(r"^\d+$", "", text, flags=re.MULTILINE)

        # Remove excessive dots/dashes
        text = re.sub(r"[.\-_]{10,}", "", text)

        # Keep only Vietnamese + English + numbers + punctuation
        text = re.sub(r"[^\w\sÀ-ỹ.,!?()%\-:]", " ", text)

        # Remove very short lines (likely headers/footers)
        lines = text.split("\n")
        meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 10]

        return "\n".join(meaningful_lines)

    async def _prepare_multimodal_messages(
        self, query: str, user_id: str, files: List[Dict], rag_context: str
    ) -> List[Dict]:
        """
        ✅ CLEAN MULTIMODAL: Single responsibility
        """
        try:
            # Get conversation history
            messages = self.conversation_manager.format_messages_for_api(
                user_id=user_id,
                rag_context=rag_context,
                current_query="",  # Will be replaced
                use_legacy_format=False,
            )

            # Prepare multimodal content
            user_content = [{"type": "text", "text": query}]

            # Add files
            for i, file_data in enumerate(files):
                filename = file_data.get("filename", f"file_{i}")
                content_type = file_data.get("content_type", "")

                print(f"📄 Processing file {i+1}: {filename}")
                print(f"📄 Content type: {content_type}")

                # ✅ DEBUG: Log ALL URL-related fields
                print(f"🔍 ALL file_data keys: {list(file_data.keys())}")
                print(f"🔗 url: {file_data.get('url', 'NOT_FOUND')}")
                print(f"🔗 public_url: {file_data.get('public_url', 'NOT_FOUND')}")
                print(f"🔗 url_image: {file_data.get('url_image', 'NOT_FOUND')}")
                print(f"📦 content length: {len(file_data.get('content', ''))}")

                if content_type and content_type.startswith("image/"):
                    # ✅ PRIORITY ORDER: url, public_url, url_image
                    image_url = (
                        file_data.get("url", "")
                        or file_data.get("public_url", "")
                        or file_data.get("url_image", "")
                    )
                    file_base64 = file_data.get("content", "")

                    print(f"🎯 Selected image URL: '{image_url}'")
                    print(f"📦 Has base64: {'Yes' if file_base64 else 'No'}")

                    if image_url:
                        print(f"✅ Adding image URL to ChatGPT: {image_url}")
                        user_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": "high"},
                            }
                        )
                    elif file_base64:
                        print(f"✅ Adding base64 image to ChatGPT")
                        user_content.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{file_base64}",
                                    "detail": "high",
                                },
                            }
                        )
                    else:
                        print(f"❌ No image data found for {filename}")
                else:
                    # Add document text to main text
                    ocr_text = file_data.get("ocr_text", "")
                    extracted_text = file_data.get("extracted_text", "")
                    filename = file_data.get("filename", "")

                    if ocr_text:
                        user_content[0]["text"] += f"\n\n--- {filename} ---\n{ocr_text}"
                    elif extracted_text:
                        user_content[0][
                            "text"
                        ] += f"\n\n--- {filename} ---\n{extracted_text}"

            # Replace last user message
            messages[-1] = {"role": "user", "content": user_content}

            return messages

        except Exception as e:
            print(f"❌ Multimodal preparation error: {e}")
            return [
                {"role": "system", "content": f"AI assistant.\n\n{rag_context}"},
                {"role": "user", "content": [{"type": "text", "text": query}]},
            ]

    async def _stream_deepseek(self, messages: List[Dict]):
        """
        ✅ CLEAN DEEPSEEK STREAMING: Convert sync to async
        """
        import asyncio

        loop = asyncio.get_event_loop()

        def sync_stream():
            for chunk in self._call_deepseek_api_streaming_with_messages(messages):
                yield chunk

        # Convert sync generator to async
        for chunk in await loop.run_in_executor(None, lambda: list(sync_stream())):
            yield chunk

    # Thêm phương thức để dọn dẹp cuộc hội thoại cũ
    def cleanup_old_conversations(self, days: int = 3) -> int:
        """
        Dọn dẹp các cuộc hội thoại cũ hơn số ngày chỉ định

        Args:
            days: Số ngày tối đa giữ lịch sử

        Returns:
            int: Số lượng cuộc hội thoại đã xóa
        """
        return self.db_manager.cleanup_old_conversations(days)
