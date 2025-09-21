import tiktoken
from typing import Dict, List, Optional, Tuple
from src.utils.logger import setup_logger
from .db_manager import DBManager

logger = setup_logger()


class ConversationManager:
    def __init__(
        self,
        db_manager: DBManager,
        max_token_limit: int = 64000,
        system_reserved_tokens: int = 1000,
    ):
        """
        Quản lý cuộc hội thoại và giới hạn token

        Args:
            db_manager: Instance của DBManager để thao tác với database
            max_token_limit: Giới hạn token tối đa cho một cuộc hội thoại (64K)
            system_reserved_tokens: Token dành riêng cho system message
        """
        self.db_manager = db_manager
        self.max_token_limit = max_token_limit
        self.system_reserved_tokens = system_reserved_tokens
        self.encoding = tiktoken.get_encoding(
            "cl100k_base"
        )  # encoding phổ biến cho LLM
        self.logger = logger

    def count_tokens(self, text: str) -> int:
        """Đếm số token trong một đoạn văn bản"""
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def add_message_enhanced(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        role: str = None,
        content: str = None,
    ) -> bool:
        """
        Enhanced message adding with comprehensive user identification
        Thêm tin nhắn nâng cao với nhận dạng user toàn diện

        Args:
            user_id: Authenticated user ID (highest priority)
            device_id: Device identifier for anonymous users
            session_id: Session identifier
            role: 'user' hoặc 'assistant'
            content: Nội dung tin nhắn

        Returns:
            bool: True nếu thêm thành công
        """
        return self.db_manager.add_message_enhanced(
            user_id=user_id,
            device_id=device_id,
            session_id=session_id,
            role=role,
            content=content,
        )

    def add_message(self, user_id: str, role: str, content: str) -> bool:
        """
        Legacy method for backward compatibility
        Phương thức legacy cho tương thích ngược
        """
        return self.db_manager.add_message(user_id, role, content)

    def get_optimized_messages_enhanced(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        rag_context: str = "",
        current_query: str = "",
    ) -> List[Dict]:
        """
        Enhanced method to get optimized messages with priority-based user identification
        Phương thức nâng cao lấy tin nhắn tối ưu với nhận dạng user theo độ ưu tiên

        Args:
            user_id: Authenticated user ID (highest priority)
            device_id: Device identifier
            session_id: Session identifier
            rag_context: Context từ RAG
            current_query: Câu hỏi hiện tại

        Returns:
            List[Dict]: Danh sách tin nhắn tối ưu để gửi đến API
        """
        # Tính token cho system message, RAG context và câu hỏi hiện tại
        system_message = (
            "Bạn là chuyên gia tài chính. Hãy trả lời câu hỏi dựa trên dữ liệu sau:"
        )
        system_tokens = self.count_tokens(system_message)
        rag_tokens = self.count_tokens(f"DỮ LIỆU:\n{rag_context}")
        query_tokens = self.count_tokens(f"CÂU HỎI: {current_query}")

        # Tính token cố định
        fixed_tokens = (
            system_tokens + rag_tokens + query_tokens + self.system_reserved_tokens
        )

        # Tính token có sẵn cho lịch sử hội thoại
        available_tokens = self.max_token_limit - fixed_tokens

        if available_tokens <= 0:
            self.logger.warning(
                f"No tokens available for history. Fixed tokens: {fixed_tokens}"
            )
            return []

        # Use enhanced method to get recent messages with priority-based identification
        # Sử dụng phương thức nâng cao để lấy tin nhắn gần đây với nhận dạng theo độ ưu tiên
        recent_messages = self.db_manager.get_recent_messages_enhanced(
            user_id=user_id, device_id=device_id, session_id=session_id, hours=72
        )

        # Nếu không có tin nhắn gần đây, trả về rỗng
        if not recent_messages:
            return []

        # Tính tổng token của tất cả tin nhắn gần đây
        all_tokens = sum(self.count_tokens(msg["content"]) for msg in recent_messages)

        # Nếu tổng token nhỏ hơn available_tokens, trả về tất cả tin nhắn
        if all_tokens <= available_tokens:
            return recent_messages

        # Nếu tổng token vượt quá, cần lọc bớt tin nhắn
        optimized_messages = []
        current_tokens = 0

        # Ưu tiên tin nhắn mới nhất, nhưng vẫn giữ cặp (user, assistant)
        for i in range(len(recent_messages) - 1, -1, -2):
            if i > 0:  # Đảm bảo còn ít nhất 2 tin nhắn
                assistant_msg = recent_messages[i]
                user_msg = recent_messages[i - 1]

                assistant_tokens = self.count_tokens(assistant_msg["content"])
                user_tokens = self.count_tokens(user_msg["content"])

                # Nếu thêm cặp tin nhắn này vượt quá giới hạn, dừng lại
                if current_tokens + assistant_tokens + user_tokens > available_tokens:
                    break

                # Thêm cặp tin nhắn vào đầu danh sách (để giữ thứ tự đúng)
                optimized_messages.insert(0, user_msg)
                optimized_messages.insert(1, assistant_msg)

                current_tokens += assistant_tokens + user_tokens

        return optimized_messages

    def get_optimized_messages(
        self, user_id: str, rag_context: str, current_query: str
    ) -> List[Dict]:
        """
        Legacy method for backward compatibility - delegates to enhanced method
        Phương thức legacy cho tương thích ngược - ủy quyền cho phương thức nâng cao
        """
        return self.get_optimized_messages_enhanced(
            user_id=user_id, rag_context=rag_context, current_query=current_query
        )

    def _format_prompt(self, query: str, context: str) -> str:
        """
        ✅ DI CHUYỂN _format_prompt TỪ CHATBOT VÀO CONVERSATION_MANAGER
        """
        return (
            "Bạn là chuyên viên tín dụng cấp cao của Ngân hàng VRB, chuyên thẩm định hồ sơ vay vốn cá nhân và doanh nghiệp, đồng thời là chuyên gia thẩm định tài sản đảm bảo như bất động sản, ô tô, sổ tiết kiệm, thiết bị máy móc, hàng hóa, v.v.Bạn cần đánh giá nhanh khả năng vay vốn của khách hàng dựa trên thông tin được cung cấp, bao gồm:Thông tin khách hàng (thu nhập, lịch sử tín dụng, mục đích vay, phương án trả nợ)Tài sản đảm bảo (loại tài sản, vị trí, tính pháp lý, giá trị định giá, hiện trạng sở hữu)Các tiêu chí tín dụng nội bộ của ngân hàng VRB.Sử dụng dữ liệu được cung cấp bên dưới để đưa ra nhận định và tư vấn cho khách hàng:, lưu ý - Lãi suất cho vay của ngân hàng VRB hiện tại chỉ từ 4.5%/năm với Quy mô chương trình: 500 tỷ đồng. Bạn cần hỏi rõ như cầu vay của khách hàng là bao nhiêu tiền, thời hạn bao lâu, tài sản đảm bảo là gì và cụ thể thông tin của tài sản đảm bảo..\n"
            f"DỮ LIỆU:\n{context}\n\n"
            f"CÂU HỎI: {query}\n\n"
            "Trả lời rất ngắn gọn, dễ hiểu, dùng ngôn ngữ chuyên nghiệp nhưng thân thiện. và hỏi thêm cụ thể nhu cầu của khách hàng như nào để tư vấn tiếp. Đồng thời xin số điện thoại của khách hàng và gợi ý đưa số điện thoại chuyên viên của ngân hàng VRB là 0979209921(Mr.Duy) để tư vấn tiếp). Đánh giá sơ bộ xem khách hàng có đủ điều kiện vay vốn không. Gợi ý ba trường hợp:Đủ điều kiện vay.Cần nhân viên ngân hàng xem xét thêm thông tin.Chưa đủ điều kiện vay.Giải thích lý do cho đánh giá trên (về thu nhập, nợ xấu, tỷ lệ tài trợ, giá trị TSĐB, v.v.)Tư vấn cụ thể cho khách hàng nếu cần bổ sung hồ sơ hoặc điều chỉnh phương án vay (VD: giảm số tiền vay, tăng TSĐB, bổ sung chứng minh thu nhập, v.v.)"
        )

    def format_messages_for_api(
        self,
        user_id: str,
        rag_context: str,
        current_query: str,
        use_legacy_format: bool = False,
    ) -> List[Dict]:
        """
        Format tin nhắn cho API DeepSeek với tối ưu token

        Args:
            user_id: ID của người dùng
            rag_context: Context từ RAG
            current_query: Câu hỏi hiện tại
            use_legacy_format: True = dùng _format_prompt, False = dùng system message riêng

        Returns:
            List[Dict]: Danh sách tin nhắn định dạng cho API
        """
        # Lấy lịch sử tối ưu
        history_messages = self.get_optimized_messages(
            user_id, rag_context, current_query
        )

        if use_legacy_format:
            # ✅ SỬ DỤNG _format_prompt CHO LEGACY COMPATIBILITY
            formatted_prompt = self._format_prompt(current_query, rag_context)

            # Tạo danh sách tin nhắn với formatted prompt
            messages = []

            # Thêm lịch sử nếu có
            if history_messages:
                messages.extend(history_messages)

            # Thêm câu hỏi hiện tại đã được format
            messages.append({"role": "user", "content": formatted_prompt})

        else:
            # ✅ SỬ DỤNG SYSTEM MESSAGE RIÊNG (MODERN FORMAT)
            # Tạo system message với RAG context
            system_message = {
                "role": "system",
                "content": f"Bạn là chuyên gia tài chính. Hãy trả lời câu hỏi dựa trên dữ liệu sau:\nDỮ LIỆU:\n{rag_context}",
            }

            # Tạo danh sách tin nhắn cho API
            messages = [system_message]

            # Thêm lịch sử nếu có
            if history_messages:
                messages.extend(history_messages)

            # Thêm câu hỏi hiện tại
            messages.append({"role": "user", "content": current_query})

        # Log thông tin về token
        if use_legacy_format:
            formatted_tokens = self.count_tokens(formatted_prompt)
            history_tokens = sum(
                self.count_tokens(msg["content"]) for msg in history_messages
            )
            total_tokens = formatted_tokens + history_tokens

            self.logger.info(
                f"Token breakdown (Legacy) - Formatted Prompt: {formatted_tokens}, History: {history_tokens}, Total: {total_tokens}"
            )
        else:
            system_tokens = self.count_tokens(system_message["content"])
            query_tokens = self.count_tokens(current_query)
            history_tokens = sum(
                self.count_tokens(msg["content"]) for msg in history_messages
            )
            total_tokens = system_tokens + history_tokens + query_tokens

            self.logger.info(
                f"Token breakdown (Modern) - System: {system_tokens}, History: {history_tokens}, Query: {query_tokens}, Total: {total_tokens}"
            )

        return messages

    def get_optimized_messages_for_frontend(
        self,
        user_id: str = None,
        device_id: str = None,
        session_id: str = None,
        rag_context: str = "",
        current_query: str = "",
    ) -> List[Dict]:
        """
        OPTIMIZED method for frontend requirements with user name support
        Phương thức tối ưu cho yêu cầu frontend với hỗ trợ tên người dùng

        Frontend optimization: user_id first, then device_id, get latest session
        Tối ưu frontend: user_id trước, sau đó device_id, lấy session mới nhất

        Args:
            user_id: Always provided by frontend (authenticated or anon_web_xxx)
            device_id: Device identifier fallback
            session_id: Session identifier (lowest priority)
            rag_context: Context từ RAG
            current_query: Câu hỏi hiện tại

        Returns:
            List[Dict]: Danh sách tin nhắn tối ưu để gửi đến API
        """
        # Tính token cho system message, RAG context và câu hỏi hiện tại
        system_message = (
            "Bạn là chuyên gia tài chính. Hãy trả lời câu hỏi dựa trên dữ liệu sau:"
        )
        system_tokens = self.count_tokens(system_message)
        rag_tokens = self.count_tokens(f"DỮ LIỆU:\n{rag_context}")
        query_tokens = self.count_tokens(f"CÂU HỎI: {current_query}")

        # Tính token cố định
        fixed_tokens = (
            system_tokens + rag_tokens + query_tokens + self.system_reserved_tokens
        )

        # Tính token có sẵn cho lịch sử hội thoại
        available_tokens = self.max_token_limit - fixed_tokens

        if available_tokens <= 0:
            self.logger.warning(
                f"No tokens available for history. Fixed tokens: {fixed_tokens}"
            )
            return []

        # Use OPTIMIZED method for frontend requirements
        # Sử dụng phương thức tối ưu cho yêu cầu frontend
        recent_messages = self.db_manager.get_recent_messages_optimized(
            user_id=user_id, device_id=device_id, session_id=session_id, hours=72
        )

        # Nếu không có tin nhắn gần đây, trả về rỗng
        if not recent_messages:
            return []

        # Tính tổng token của tất cả tin nhắn gần đây
        all_tokens = sum(self.count_tokens(msg["content"]) for msg in recent_messages)

        # Nếu tổng token nhỏ hơn available_tokens, trả về tất cả tin nhắn
        if all_tokens <= available_tokens:
            return recent_messages

        # Nếu tổng token vượt quá, cần lọc bớt tin nhắn
        optimized_messages = []
        current_tokens = 0

        # Ưu tiên tin nhắn mới nhất, nhưng vẫn giữ cặp (user, assistant)
        for i in range(len(recent_messages) - 1, -1, -2):
            if i > 0:  # Đảm bảo còn ít nhất 2 tin nhắn
                assistant_msg = recent_messages[i]
                user_msg = recent_messages[i - 1]

                assistant_tokens = self.count_tokens(assistant_msg["content"])
                user_tokens = self.count_tokens(user_msg["content"])

                # Nếu thêm cặp tin nhắn này vượt quá giới hạn, dừng lại
                if current_tokens + assistant_tokens + user_tokens > available_tokens:
                    break

                # Thêm cặp tin nhắn vào đầu danh sách (để giữ thứ tự đúng)
                optimized_messages.insert(0, user_msg)
                optimized_messages.insert(1, assistant_msg)

                current_tokens += assistant_tokens + user_tokens

        return optimized_messages
