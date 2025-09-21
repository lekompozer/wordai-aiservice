"""
Information Agent with RAG capabilities
Agent thông tin với khả năng RAG để trả lời về thông tin công ty/sản phẩm/dịch vụ
"""

import json
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime

from src.models.unified_models import Language, Industry
from src.providers.ai_provider_manager import AIProviderManager
from src.services.qdrant_company_service import QdrantCompanyDataService


class InformationAgent:
    """
    Information agent for company-specific Q&A using RAG
    Agent thông tin cho hỏi đáp theo công ty sử dụng RAG
    """

    def __init__(self):
        # Initialize AI provider / Khởi tạo AI provider
        from src.core.config import APP_CONFIG

        self.ai_manager = AIProviderManager(
            deepseek_api_key=APP_CONFIG.get("deepseek_api_key"),
            chatgpt_api_key=APP_CONFIG.get("chatgpt_api_key"),
        )

        # Initialize Qdrant service for RAG / Khởi tạo Qdrant service cho RAG
        self.qdrant_service = QdrantCompanyDataService(
            qdrant_url=APP_CONFIG.get("qdrant_cloud_url"),
            qdrant_api_key=APP_CONFIG.get("qdrant_api_key"),
        )

    async def process_message(self, request) -> Dict[str, Any]:
        """
        Process information request with chat history context from UnifiedChatRequest
        Xử lý yêu cầu thông tin với ngữ cảnh lịch sử chat từ UnifiedChatRequest
        """
        try:
            # Get chat history for context
            chat_history = await self._get_user_chat_history(
                user_id=request.user_info.user_id,
                session_id=request.session_id,
                limit=10,
            )

            # Call the existing process_query method
            return await self.process_query(
                query=request.message,
                company_id=request.company_id,
                session_id=request.session_id,
                language=request.language,
                industry=request.industry,
                user_id=request.user_info.user_id,
            )

        except Exception as e:
            print(f"❌ InformationAgent processing error: {e}")
            raise

    async def process_query(
        self,
        query: str,
        company_id: str,
        session_id: str,
        language: Language = Language.VIETNAMESE,
        industry: Industry = Industry.BANKING,
        user_id: str = None,
    ) -> Dict[str, Any]:
        """
        Process information query using RAG from Qdrant with company isolation and language translation
        Xử lý truy vấn thông tin sử dụng RAG từ Qdrant với cách ly công ty và dịch ngôn ngữ
        """
        try:
            print(
                f"🔍 [INFO_AGENT] Processing query for company {company_id}, industry {industry.value}"
            )
            print(f"   Query: {query[:100]}...")
            print(f"   User language: {language.value}")

            # Step 1: Get user chat history / Bước 1: Lấy lịch sử chat của user
            chat_history = await self._get_user_chat_history(user_id, session_id)

            # Continue with existing logic...
            # ...existing code...

            # Step 2: Detect document languages in company collection / Bước 2: Phát hiện ngôn ngữ tài liệu trong collection công ty
            document_languages = await self._detect_company_document_languages(
                company_id, industry
            )
            print(f"   Document languages in collection: {document_languages}")

            # Step 3: Translate query if needed / Bước 3: Dịch câu hỏi nếu cần
            translated_queries = await self._translate_query_for_documents(
                query, language, document_languages
            )

            # Step 4: Search in Qdrant with all language variants / Bước 4: Tìm kiếm trong Qdrant với tất cả biến thể ngôn ngữ
            all_rag_results = []
            for lang, translated_query in translated_queries.items():
                print(f"   Searching with {lang} query: {translated_query[:50]}...")

                rag_results = await self.qdrant_service.search_company_data(
                    company_id=company_id,
                    query=translated_query,
                    industry=industry,
                    language=(
                        Language(lang) if lang in ["vi", "en"] else Language.AUTO_DETECT
                    ),
                    limit=3,
                    score_threshold=0.6,
                )

                if rag_results:
                    # Add source language info / Thêm thông tin ngôn ngữ nguồn
                    for result in rag_results:
                        result["search_language"] = lang
                    all_rag_results.extend(rag_results)

            # Step 5: Remove duplicates and sort by score / Bước 5: Loại bỏ trùng lặp và sắp xếp theo điểm
            unique_results = self._deduplicate_results(all_rag_results)
            unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Take top results / Lấy kết quả top
            final_results = unique_results[:5]

            if final_results:
                # Use RAG results from Qdrant / Sử dụng kết quả RAG từ Qdrant
                print(
                    f"✅ [INFO_AGENT] Found {len(final_results)} relevant documents from Qdrant"
                )
                context = self._build_comprehensive_context(
                    final_results, chat_history, language
                )
                sources = [
                    {
                        "type": "qdrant_rag",
                        "source": f"company_{company_id}",
                        "chunks": len(final_results),
                    }
                ]
                confidence = 0.9
            else:
                # No company-specific data found - let DeepSeek handle with industry knowledge
                # Không tìm thấy dữ liệu riêng công ty - để DeepSeek xử lý với kiến thức ngành
                print(
                    f"⚠️ [INFO_AGENT] No company-specific data found, will rely on AI industry knowledge"
                )
                context = self._build_industry_context_only(
                    chat_history, language, industry, company_id
                )
                sources = [
                    {
                        "type": "ai_industry_knowledge",
                        "source": f"industry_{industry.value}",
                    }
                ]
                confidence = 0.6

            # Step 6: Create multilingual prompt with company isolation / Bước 6: Tạo prompt đa ngôn ngữ với cách ly công ty
            prompt = self._create_multilingual_company_prompt(
                original_query=query,
                context=context,
                user_language=language,
                industry=industry,
                company_id=company_id,
                chat_history=chat_history,
            )

            # Step 7: Get AI response / Bước 7: Lấy phản hồi AI
            response = await self.ai_manager.get_response(
                question=prompt,
                session_id=session_id,
                user_id=user_id or "information_agent",
            )

            return {
                "response": response,
                "sources": sources,
                "confidence": confidence,
                "language": language.value,
                "company_id": company_id,
                "industry": industry.value,
                "translated_queries": translated_queries,
                "document_languages": document_languages,
            }

        except Exception as e:
            print(f"❌ [INFO_AGENT] Error processing query: {e}")
            return {
                "response": self._get_fallback_response(language),
                "sources": [],
                "confidence": 0.3,
                "language": language.value,
                "error": str(e),
            }

    async def stream_response(
        self,
        query: str,
        company_id: str,
        session_id: str,
        language: Language = Language.VIETNAMESE,
        industry: Industry = Industry.BANKING,
    ) -> AsyncGenerator[str, None]:
        """
        Stream information response for real-time experience
        Stream phản hồi thông tin cho trải nghiệm thời gian thực
        """
        try:
            # Process same as non-streaming but yield chunks / Xử lý giống như không streaming nhưng yield từng chunk
            result = await self.process_query(
                query, company_id, session_id, language, industry
            )
            response = result.get("response", self._get_fallback_response(language))

            # Yield response in chunks / Yield phản hồi theo từng chunk
            chunk_size = 50
            for i in range(0, len(response), chunk_size):
                yield response[i : i + chunk_size]
                await asyncio.sleep(0.1)  # Small delay for streaming effect

        except Exception as e:
            error_message = self._get_fallback_response(language)
            yield error_message

    def _get_system_message(self, language: Language) -> str:
        """
        Get system message for AI
        Lấy system message cho AI
        """
        if language == Language.VIETNAMESE:
            return """
Bạn là trợ lý AI chuyên nghiệp của công ty. Nhiệm vụ của bạn là:
1. Trả lời các câu hỏi về thông tin công ty, sản phẩm, dịch vụ
2. Luôn trả lời bằng tiếng Việt
3. Cung cấp thông tin chính xác dựa trên dữ liệu có sẵn
4. Thân thiện, lịch sự và chuyên nghiệp
5. Nếu không biết thông tin, hãy thành thật nói không biết và gợi ý cách tìm hiểu thêm
"""
        else:
            return """
You are a professional AI assistant for the company. Your role is to:
1. Answer questions about company information, products, and services
2. Always respond in English
3. Provide accurate information based on available data
4. Be friendly, polite, and professional
5. If you don't know something, honestly say so and suggest how to find more information
"""

    def _get_fallback_response(self, language: Language) -> str:
        """
        Get fallback response when error occurs
        Lấy phản hồi dự phòng khi có lỗi
        """
        if language == Language.VIETNAMESE:
            return """
Xin lỗi, tôi đang gặp sự cố kỹ thuật trong việc tìm kiếm thông tin.
Bạn có thể:
- Thử hỏi lại với câu hỏi cụ thể hơn
- Liên hệ trực tiếp với bộ phận hỗ trợ
- Ghé thăm website chính thức của chúng tôi

Tôi sẵn sàng hỗ trợ bạn với những thông tin khác!
"""
        else:
            return """
Sorry, I'm experiencing technical difficulties finding that information.
You can:
- Try asking again with a more specific question
- Contact our support team directly
- Visit our official website

I'm ready to help you with other information!
"""

    async def search_company_documents(
        self, company_id: str, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search company documents in Qdrant (to be implemented in Phase 4)
        Tìm kiếm tài liệu công ty trong Qdrant (sẽ triển khai trong Phase 4)
        """
        # Placeholder for Phase 4 implementation / Placeholder cho triển khai Phase 4
        return [
            {
                "content": f"Sample document content related to: {query}",
                "metadata": {
                    "source": "company_document.pdf",
                    "company_id": company_id,
                    "type": "info",
                },
                "score": 0.85,
            }
        ]

    async def _get_user_chat_history(
        self, user_id: str, session_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get user chat history for context from the UnifiedChatService
        Lấy lịch sử chat của user để làm ngữ cảnh từ UnifiedChatService
        """
        try:
            if not user_id and not session_id:
                return []

            # Import unified_chat_service here to avoid circular dependency
            from src.services.unified_chat_service import unified_chat_service

            # Use session_id as primary identifier for chat history
            identifier = session_id or user_id

            # Get conversation history from unified chat service
            history_objects = unified_chat_service._get_conversation_history(identifier)

            # Convert to simple dict list for context
            history_list = []
            for msg in history_objects:
                history_list.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": (
                            msg.timestamp.isoformat()
                            if hasattr(msg, "timestamp")
                            else None
                        ),
                        "intent": (
                            msg.intent.value
                            if hasattr(msg, "intent") and msg.intent
                            else None
                        ),
                        "language": (
                            msg.language.value
                            if hasattr(msg, "language") and msg.language
                            else None
                        ),
                    }
                )

            # Return latest messages for context (limit by parameter)
            result = history_list[-limit:] if history_list else []

            if result:
                print(
                    f"📜 [INFO_AGENT] Retrieved {len(result)} chat history entries for context"
                )
            else:
                print(f"📜 [INFO_AGENT] No chat history found for user {user_id}")

            return result

        except Exception as e:
            print(f"❌ Error getting chat history for user {user_id}: {e}")
            return []

    async def _detect_company_document_languages(
        self, company_id: str, industry: Industry
    ) -> List[str]:
        """
        Detect what languages are available in company documents
        Phát hiện ngôn ngữ có sẵn trong tài liệu công ty
        """
        try:
            # Query Qdrant to get unique languages in company collection
            # Truy vấn Qdrant để lấy ngôn ngữ duy nhất trong collection công ty

            # For now, return common languages - in production would query Qdrant metadata
            # Hiện tại trả về ngôn ngữ phổ biến - trong production sẽ truy vấn metadata Qdrant
            return ["vi", "en"]  # Vietnamese and English by default

        except Exception as e:
            print(f"❌ Error detecting document languages: {e}")
            return ["vi", "en"]

    async def _translate_query_for_documents(
        self, query: str, user_language: Language, document_languages: List[str]
    ) -> Dict[str, str]:
        """
        Translate user query to match document languages
        Dịch câu hỏi của user để phù hợp với ngôn ngữ tài liệu
        """
        try:
            translated_queries = {}
            user_lang_code = user_language.value

            # Always include original query / Luôn bao gồm câu hỏi gốc
            translated_queries[user_lang_code] = query

            # Translate to other document languages if needed / Dịch sang ngôn ngữ tài liệu khác nếu cần
            for doc_lang in document_languages:
                if doc_lang != user_lang_code:
                    print(
                        f"   Translating query from {user_lang_code} to {doc_lang}..."
                    )
                    translated_query = await self._translate_text(
                        query, user_lang_code, doc_lang
                    )
                    if translated_query and translated_query != query:
                        translated_queries[doc_lang] = translated_query

            return translated_queries

        except Exception as e:
            print(f"❌ Error translating query: {e}")
            return {user_language.value: query}

    async def _translate_text(self, text: str, from_lang: str, to_lang: str) -> str:
        """
        Translate text using DeepSeek
        Dịch văn bản sử dụng DeepSeek
        """
        try:
            if from_lang == to_lang:
                return text

            # Language mapping / Ánh xạ ngôn ngữ
            lang_names = {
                "vi": "Vietnamese",
                "en": "English",
                "zh": "Chinese",
                "ja": "Japanese",
                "ko": "Korean",
                "th": "Thai",
                "id": "Indonesian",
            }

            from_name = lang_names.get(from_lang, from_lang)
            to_name = lang_names.get(to_lang, to_lang)

            prompt = f"""
Translate the following text from {from_name} to {to_name}.
Only return the translation, no explanations.

Text to translate: {text}

Translation:
"""

            translation = await self.ai_manager.get_response(
                question=prompt, session_id="translation", user_id="translator"
            )

            return translation.strip() if translation else text

        except Exception as e:
            print(f"❌ Translation error: {e}")
            return text

    def _deduplicate_results(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results based on content similarity
        Loại bỏ kết quả trùng lặp dựa trên độ tương đồng nội dung
        """
        if not results:
            return []

        unique_results = []
        seen_content = set()

        for result in results:
            content = result.get("content", "").strip()
            content_hash = hash(content[:200])  # Use first 200 chars for deduplication

            if content_hash not in seen_content:
                seen_content.add(content_hash)
                unique_results.append(result)

        return unique_results

    def _build_industry_context_only(
        self,
        chat_history: List[Dict[str, Any]],
        language: Language,
        industry: Industry,
        company_id: str,
    ) -> str:
        """
        Build context for AI industry knowledge when no company data is available
        Xây dựng ngữ cảnh cho kiến thức ngành của AI khi không có dữ liệu công ty
        """
        context_parts = []

        # Add chat history context / Thêm ngữ cảnh lịch sử chat
        if chat_history:
            if language == Language.VIETNAMESE:
                context_parts.append("LỊCH SỬ CHAT GẦN ĐÂY:")
            else:
                context_parts.append("RECENT CHAT HISTORY:")

            for i, msg in enumerate(chat_history[-3:], 1):  # Last 3 messages
                role = msg.get("role", "user")
                content = msg.get(
                    "content", ""
                )  # Show full content instead of truncating
                context_parts.append(f"{i}. {role}: {content}")
            context_parts.append("")

        # Add instruction for AI to use industry knowledge / Thêm hướng dẫn cho AI sử dụng kiến thức ngành
        if language == Language.VIETNAMESE:
            context_parts.append(
                f"THÔNG TIN CÔNG TY: Không có thông tin cụ thể về công ty ID: {company_id}"
            )
            context_parts.append(f"NGÀNH: {industry.value}")
            context_parts.append("Hãy sử dụng kiến thức chung về ngành này để trả lời.")
        else:
            context_parts.append(
                f"COMPANY INFORMATION: No specific information available for company ID: {company_id}"
            )
            context_parts.append(f"INDUSTRY: {industry.value}")
            context_parts.append("Please use general industry knowledge to respond.")

        return "\n".join(context_parts)

    def _build_comprehensive_context(
        self,
        rag_results: List[Dict[str, Any]],
        chat_history: List[Dict[str, Any]],
        language: Language,
    ) -> str:
        """
        Build comprehensive context from RAG results and chat history
        Xây dựng ngữ cảnh toàn diện từ kết quả RAG và lịch sử chat
        """
        context_parts = []

        # Add chat history context / Thêm ngữ cảnh lịch sử chat
        if chat_history:
            if language == Language.VIETNAMESE:
                context_parts.append("LỊCH SỬ CHAT GẦN ĐÂY:")
            else:
                context_parts.append("RECENT CHAT HISTORY:")

            for i, msg in enumerate(chat_history[-3:], 1):  # Last 3 messages
                role = msg.get("role", "user")
                content = msg.get(
                    "content", ""
                )  # Show full content instead of truncating
                context_parts.append(f"{i}. {role}: {content}")
            context_parts.append("")

        # Add document results / Thêm kết quả tài liệu
        if rag_results:
            if language == Language.VIETNAMESE:
                context_parts.append("THÔNG TIN TỪ TÀI LIỆU CÔNG TY:")
            else:
                context_parts.append("COMPANY DOCUMENT INFORMATION:")

            for i, result in enumerate(rag_results, 1):
                content = result.get("content", "")
                content_type = result.get("content_type", "")
                score = result.get("score", 0)
                doc_lang = result.get("language", "unknown")
                search_lang = result.get("search_language", "original")

                context_parts.append(
                    f"Document {i} ({content_type}, score: {score:.2f}, language: {doc_lang}, searched in: {search_lang}):"
                )
                context_parts.append(content)
                context_parts.append("")

        return "\n".join(context_parts)

    def _create_multilingual_company_prompt(
        self,
        original_query: str,
        context: str,
        user_language: Language,
        industry: Industry,
        company_id: str,
        chat_history: List[Dict[str, Any]],
    ) -> str:
        """
        Create comprehensive multilingual prompt with company isolation
        Tạo prompt đa ngôn ngữ toàn diện với cách ly công ty
        """
        # Format chat history for context
        chat_context = ""
        if chat_history:
            chat_context = "\n\nLỊCH SỬ CUỘC HỘI THOẠI GẦN ĐÂY:\n"
            for i, msg in enumerate(
                chat_history[-5:], 1
            ):  # Last 5 messages (tăng từ 3 lên 5)
                role = "Khách hàng" if msg.get("role") == "user" else "AI Assistant"
                content = msg.get("content", "")
                # Hiển thị đầy đủ nội dung (không truncate)
                chat_context += f"{i}. {role}: {content}\n"

        if user_language == Language.VIETNAMESE:
            return f"""
Bạn là trợ lý AI chuyên nghiệp của công ty (ID: {company_id}) trong ngành {industry.value}.

QUY TẮC QUAN TRỌNG - COMPANY & INDUSTRY ISOLATION:
1. ƯU TIÊN: Trả lời thông tin về công ty này (ID: {company_id}) nếu có trong context
2. NẾU KHÔNG CÓ thông tin công ty: Chỉ trả lời thông tin CHUNG về ngành {industry.value}
3. TUYỆT ĐỐI KHÔNG: Cung cấp thông tin về công ty khác hoặc ngành khác
4. TUYỆT ĐỐI KHÔNG: Cung cấp thông tin ngoài ngành {industry.value}
5. Nếu khách hỏi về công ty/ngành khác: Lịch sự từ chối và hướng dẫn tìm nguồn chính xác
6. Sử dụng lịch sử chat để hiểu ngữ cảnh cuộc hội thoại{chat_context}

NGỮ CẢNH VÀ THÔNG TIN:
{context}

CÂU HỎI KHÁCH HÀNG: {original_query}

Hướng dẫn trả lời:
- LUÔN trả lời bằng tiếng Việt
- NẾU CÓ thông tin công ty trong context: Dựa vào đó để trả lời
- NẾU KHÔNG CÓ thông tin công ty: Sử dụng kiến thức chung về ngành {industry.value}
- Thân thiện, chuyên nghiệp và chính xác
- Nếu không có thông tin cụ thể về công ty: "Tôi không có thông tin cụ thể về công ty này, nhưng về ngành {industry.value} thì..."
- CHỈ trả lời trong phạm vi ngành {industry.value}

PHẢN HỒI:
"""
        else:
            # Format chat history for English
            chat_context_en = ""
            if chat_history:
                chat_context_en = "\n\nRECENT CONVERSATION HISTORY:\n"
                for i, msg in enumerate(chat_history[-3:], 1):  # Last 3 messages
                    role = "Customer" if msg.get("role") == "user" else "AI Assistant"
                    content = msg.get("content", "")
                    chat_context_en += f"{i}. {role}: {content}\n"

            return f"""
You are a professional AI assistant for company (ID: {company_id}) in the {industry.value} industry.

IMPORTANT RULES - COMPANY & INDUSTRY ISOLATION:
1. PRIORITY: Provide information about this company (ID: {company_id}) if available in context
2. IF NO COMPANY INFO: Only provide GENERAL information about {industry.value} industry
3. ABSOLUTELY DO NOT: Provide information about other companies or other industries
4. ABSOLUTELY DO NOT: Provide information outside {industry.value} industry
5. If asked about other companies/industries: Politely decline and guide to accurate sources
6. Use chat history to understand conversation context{chat_context_en}

CONTEXT AND INFORMATION:
{context}

CUSTOMER QUESTION: {original_query}

Response guidelines:
- ALWAYS respond in English
- IF company info available in context: Base answer on that
- IF NO company info: Use general knowledge about {industry.value} industry
- Be friendly, professional, and accurate
- If no specific company information: "I don't have specific information about this company, but regarding the {industry.value} industry..."
- ONLY respond within {industry.value} industry scope

RESPONSE:
"""
