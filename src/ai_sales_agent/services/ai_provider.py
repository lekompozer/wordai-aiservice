"""
AI Provider service for AI Sales Agent using DeepSeek
Flexible approach - Extract any information from natural conversation
"""

import json
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.providers.ai_provider_manager import AIProviderManager
from src.core.config import APP_CONFIG
from src.ai_sales_agent.utils.flexible_assessment import FlexibleAssessmentChecker

class AISalesAgentProvider:
    """
    AI Provider for flexible information extraction and natural conversation
    """
    
    def __init__(self, ai_manager: AIProviderManager):
        self.ai_manager = ai_manager
        self.provider = "deepseek"
        
        # Field priorities matching /api/loan/assessment API requirements exactly
        self.field_priorities = {
            # CRITICAL - Required for assessment API (90-100 points)
            "fullName": 100,
            "loanAmount": 95,
            "monthlyIncome": 95,
            "loanPurpose": 90,
            "loanTerm": 90,
            "loanType": 85,
            
            # ESSENTIAL - Core personal info for API (70-85 points)
            "birthYear": 80,
            "age": 80,  # Alternative to birthYear
            "phoneNumber": 75,
            "primaryIncomeSource": 85,
            "collateralType": 85,
            "collateralValue": 90,
            "hasExistingDebt": 80,
            
            # IMPORTANT - Financial analysis (60-75 points)
            "monthlyDebtPayment": 75,
            "totalDebtAmount": 70,
            "otherIncomeAmount": 65,
            "companyName": 60,
            "jobTitle": 60,
            "workExperience": 65,
            
            # DEMOGRAPHIC - API expects these (50-65 points)
            "gender": 55,
            "maritalStatus": 60,
            "dependents": 55,
            "email": 50,
            
            # FINANCIAL DETAILS - Improve assessment accuracy (40-55 points)
            "totalAssets": 50,
            "liquidAssets": 45,
            "bankName": 40,
            "cicCreditScoreGroup": 55,
            "collateralInfo": 50,
            
            # OPTIONAL - Nice to have (15-40 points)
            "phoneCountryCode": 15,
            "creditHistory": 35,
            "existingLoans": 40,
            "interestRate": 20,
            "salesAgentCode": 15,
            "collateralImage": 25,
            "currency": 70,  # Important for international customers
            "loanCurrency": 70  # Alternative field name
        }
    
    async def process_message_combined(
        self,
        user_message: str,
        current_data: Dict[str, Any],
        message_count: int,
        context: str = None,
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process user message with combined NLU extraction and NLG response generation
        Returns both extracted data and natural response in one AI call
        """
        
        # Get configuration or use defaults
        config = config or {}
        bank_name = config.get('bankName', 'VRB')
        unsecured_rate = config.get('unsecuredInterestRate', 18.0)
        mortgage_rate_first = config.get('mortgageRateFirstYear', 5.0)
        mortgage_rate_after = config.get('mortgageRateAfterYear', 8.5)
        
        # Get loan type for conditional logic
        loan_type = current_data.get('loanType', '').lower()
        is_mortgage = 'thế chấp' in loan_type or 'the chap' in loan_type or 'secured' in loan_type or 'mortgage' in loan_type
        
        # Get smart question suggestion
        checker = FlexibleAssessmentChecker()
        next_question_info = checker.get_next_smart_question(current_data, message_count)
        
        # Build combined prompt with bilingual instructions
        prompt = f"""
YOU ARE A BILINGUAL LOAN CONSULTANT AT {bank_name} BANK.
BẠN LÀ NHÂN VIÊN TƯ VẤN VAY VỐN ĐA NGÔN NGỮ TẠI NGÂN HÀNG {bank_name}.

🌐 CRITICAL LANGUAGE RULE / QUY TẮC NGÔN NGỮ QUAN TRỌNG:
- ALWAYS respond in the SAME LANGUAGE as the customer's message
- LUÔN trả lời bằng CÙNG NGÔN NGỮ với tin nhắn của khách hàng
- If customer writes in English → Response must be in English
- Nếu khách hàng viết tiếng Việt → Phản hồi phải bằng tiếng Việt
- Auto-detect the language from the customer's input and maintain consistency
- Tự động nhận diện ngôn ngữ từ input của khách hàng và giữ nhất quán

TASKS / NHIỆM VỤ:
    1. EXTRACTION (NLU): Analyze and extract ALL information from customer's response
   TRÍCH XUẤT (NLU): Phân tích và trích xuất TẤT CẢ thông tin từ câu trả lời khách hàng

2. VALIDATION: Check age (18-70), phone format, logical consistency  
   KIỂM TRA: Kiểm tra tuổi (18-70), định dạng SĐT, tính logic hợp lý

3. RESPONSE (NLG): Create natural, polite response in CUSTOMER'S LANGUAGE
   PHẢN HỒI (NLG): Tạo câu trả lời tự nhiên, lịch sự bằng NGÔN NGỮ KHÁCH HÀNG

CUSTOMER SAID / KHÁCH HÀNG NÓI: "{user_message}"

EXISTING INFORMATION (DO NOT ASK AGAIN) / THÔNG TIN ĐÃ CÓ (KHÔNG HỎI LẠI):
{self._format_current_data(current_data)}

QUESTIONS ASKED / SỐ CÂU ĐÃ HỎI: {message_count}/10 (max 10, should stop at 5-7 / tối đa 10 câu, nên dừng ở 5-7)

LOAN TYPE / LOẠI VAY: {f"Secured (Thế chấp) - NEED to ask about collateral / Thế chấp - CẦN hỏi tài sản đảm bảo" if is_mortgage else f"Unsecured (Tín chấp) - NO collateral questions / Tín chấp - KHÔNG hỏi tài sản đảm bảo" if loan_type else "UNKNOWN - ASK IMMEDIATELY / CHƯA BIẾT - CẦN HỎI NGAY"}

🚨 CRITICAL LOAN TYPE RULE / QUY TẮC QUAN TRỌNG VỀ LOẠI VAY:
- If customer says "unsecured" → This means "Tín chấp" (NO collateral needed, DO NOT ask about property/assets)
- If customer says "secured" → This means "Thế chấp" (collateral required, ask about property/assets)
- Nếu khách nói "unsecured" → Có nghĩa là "Tín chấp" (KHÔNG cần tài sản đảm bảo, KHÔNG hỏi về nhà/tài sản)
- Nếu khách nói "secured" → Có nghĩa là "Thế chấp" (cần tài sản đảm bảo, hỏi về nhà/tài sản)

SUGGESTED NEXT QUESTION / CÂU HỎI TIẾP THEO GỢI Ý: {next_question_info.get('question', 'Ask for missing priority information / Hỏi thông tin ưu tiên còn thiếu')}

RECENT HISTORY / LỊCH SỬ GẦN ĐÂY:
{context if context else "None / Chưa có"}

REQUIRED OUTPUT JSON / YÊU CẦU OUTPUT JSON:
{{
    "nlu": {{
        "extractedData": {{
            // Extract ALL information found / Trích xuất TẤT CẢ thông tin tìm thấy
            // "loanAmount": amount (number) / số tiền (number),
            // "loanTerm": term (number - years) / thời hạn (number - năm),
            // "fullName": "Full name / Họ và tên",
            // "birthYear": birth year (from age if given) / năm sinh (từ tuổi nếu có)
            // ... other fields / các field khác
        }},
        "validationErrors": {{
            // Polite validation checks / Kiểm tra validation một cách lịch sự
            // "birthYear": "Please confirm your birth year / Anh/chị xem giúp em năm sinh này đã đúng chưa ạ?",
            // "phoneNumber": "Could you please check the phone number format? / Anh/chị kiểm tra giúp em số điện thoại có đúng định dạng không ạ?"
        }},
        "confidence": 0.85
    }},
    "nlg": {{
        "response": "Natural, polite response in customer's language - Thank for info + Gently ask to fix errors FIRST + Then ask for 2-3 more fields / Câu phản hồi tự nhiên, lịch sự bằng ngôn ngữ khách hàng - Cảm ơn thông tin + Nhẹ nhàng yêu cầu sửa lỗi TRƯỚC + Sau đó hỏi tiếp 2-3 field",
        "isComplete": false, // true if asked 5-7 questions or have critical data / nếu đã hỏi 5-7 câu hoặc đủ data critical
        "suggestAssessment": false, // true if should suggest assessment / nếu nên gợi ý thẩm định
        "language": "auto-detect from customer input (en/vi) / tự nhận diện từ input khách hàng"
    }}
}}

IMPORTANT RULES / QUY TẮC QUAN TRỌNG:
    1. NLU: Extract ALL information, even not directly asked
   NLU: Trích xuất MỌI thông tin, kể cả không được hỏi trực tiếp

2. VALIDATION: Check birth year (age 18-70), phone format (Vietnamese: 0xxxxxxxxx), logical data
   VALIDATION: Kiểm tra năm sinh (tuổi 18-70), định dạng SĐT (VN: 0xxxxxxxxx), dữ liệu logic

3. NLG: If validation errors, ask to CONFIRM POLITELY (not like error message)
   NLG: Nếu có lỗi validation, YÊU CẦU XÁC NHẬN MỘT CÁCH LỊCH SỰ (không như thông báo lỗi)

4. Examples of polite validation requests / Ví dụ yêu cầu validation lịch sự:
   - Birth year issue: 'Could you please confirm your birth year?' / 'Anh/chị xem giúp em năm sinh này đã đúng chưa ạ?'
   - Phone issue: 'Could you please check your phone number?' / 'Anh/chị kiểm tra giúp em số điện thoại có đúng không ạ?'

5. NLG: NEVER re-ask information already in 'EXISTING INFORMATION'
   NLG: TUYỆT ĐỐI KHÔNG HỎI LẠI thông tin đã có trong 'THÔNG TIN ĐÃ CÓ'

6. Priority order / Ưu tiên hỏi theo thứ tự:
   - Q1: Loan amount, term (if missing) / Câu 1: Số tiền, thời hạn vay (nếu chưa có)
   - Q2: LOAN TYPE (unsecured/secured) - CRITICAL / Câu 2: LOẠI HÌNH VAY (tín chấp/thế chấp) - QUAN TRỌNG
   - Q3-4: Personal info (name, phone, birth year) / Câu 3-4: Thông tin cá nhân (họ tên, SĐT, năm sinh)
   - Q5-6: Income, work / Câu 5-6: Thu nhập, công việc
   - Q7: Existing debt (if needed) / Câu 7: Nợ hiện tại (nếu cần)
   - Q8-10: COLLATERAL DETAILS (ONLY if secured/thế chấp loan) / Câu 8-10: CHI TIẾT TÀI SẢN ĐẢM BẢO (CHỈ hỏi nếu vay thế chấp)
     * Q8: collateralType - Loại tài sản (nhà đất/căn hộ/xe hơi/...)
     * Q9: collateralInfo - Thông tin chi tiết (địa chỉ, diện tích, tình trạng pháp lý, hình ảnh)  
     * Q10: collateralValue - Giá trị ước tính từ khách hàng (BẮT BUỘC có số tiền cụ thể)
   
🚨 NEVER ask about collateral/property if loan type is "Tín chấp" or customer said "unsecured"
🚨 TUYỆT ĐỐI KHÔNG hỏi về tài sản đảm bảo nếu loại vay là "Tín chấp" hoặc khách nói "unsecured"

🏠 CRITICAL COLLATERAL RULES for SECURED LOANS / QUY TẮC QUAN TRỌNG VỀ TÀI SẢN ĐẢM BẢO CHO VAY THẾ CHẤP:
- MUST ask for ALL 3 pieces of collateral information / PHẢI hỏi ĐỦ 3 thông tin tài sản:
  1. TYPE: What kind of asset (house, apartment, car, etc.) / LOẠI: Loại tài sản gì (nhà, căn hộ, xe hơi...)
  2. DETAILS: Specific information (address, size, legal status, photos) / CHI TIẾT: Thông tin cụ thể (địa chỉ, diện tích, tình trạng pháp lý, hình ảnh)
  3. VALUE: Customer's estimated value (specific amount required) / GIÁ TRỊ: Khách hàng ước tính giá trị (phải có số tiền cụ thể)
- Do NOT accept vague answers like "có nhà" or "valuable property" / KHÔNG chấp nhận câu trả lời mơ hồ
- MUST get specific monetary value from customer / PHẢI có giá trị tiền tệ cụ thể từ khách hàng
- Ask follow-up questions until all 3 pieces are clear / Hỏi tiếp đến khi có đủ cả 3 thông tin rõ ràng

7. Ask 2-3 info per question to optimize, but PRIORITIZE validation fixes
   Hỏi 2-3 thông tin trong 1 câu để tối ưu, nhưng ƯU TIÊN sửa validation trước

8. 🌐 RESPOND IN CUSTOMER'S LANGUAGE (English/Vietnamese) - CRITICAL!
   🌐 TRẢ LỜI BẰNG NGÔN NGỮ KHÁCH HÀNG (Tiếng Anh/Tiếng Việt) - QUAN TRỌNG!

INTEREST RATES (for reference) / LÃI SUẤT (tham khảo):
- Unsecured / Tín chấp: {unsecured_rate}%/year/năm
- Secured / Thế chấp: {mortgage_rate_first}% first year/năm đầu, {mortgage_rate_after}% after/các năm sau

RETURN JSON ONLY, NO EXPLANATION. / CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH.
    """
        
        try:
            messages = [{"role": "user", "content": prompt}]
            full_response = ""
            
            async for chunk in self.ai_manager.chat_completion_stream(messages, self.provider):
                full_response += chunk
            
            # Parse JSON response
            json_text = self._extract_json_from_response(full_response)
            result = json.loads(json_text)
            
            # Post-process extracted data with validation
            if "nlu" in result and "extractedData" in result["nlu"]:
                processed_data, validation_errors = self._post_process_extracted_data_with_validation(
                    result["nlu"]["extractedData"]
                )
                result["nlu"]["extractedData"] = processed_data
                if validation_errors:
                    result["nlu"]["validationErrors"] = validation_errors
            
            # Add metadata
            result["metadata"] = {
                "messageCount": message_count,
                "loanType": current_data.get('loanType', 'Unknown'),
                "method": "Combined NLU+NLG",
                "bankName": bank_name,
                "language": result.get("nlg", {}).get("language", "auto-detect"),
                "config": config
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Combined processing failed: {e}")
            # Fallback to separate processing
            return await self._fallback_separate_processing(user_message, current_data, message_count, context)

    async def _fallback_separate_processing(
        self, 
        user_message: str, 
        current_data: Dict[str, Any],
        message_count: int,
        context: str
    ) -> Dict[str, Any]:
        """Fallback to separate NLU and NLG if combined fails"""
        
        # Extract data first
        nlu_result = await self.extract_information_flexible(user_message, current_data, context)
        
        # Generate response
        missing_fields = self.get_missing_priority_fields(current_data)
        nlg_response = await self.generate_flexible_response(
            user_message,
            nlu_result.get("extractedData", {}),
            current_data,
            missing_fields[:3]
        )
        
        # Check if should suggest assessment
        checker = FlexibleAssessmentChecker()
        readiness = checker.assess_readiness(current_data)
        
        return {
            "nlu": {
                "extractedData": nlu_result.get("extractedData", {}),
                "confidence": nlu_result.get("confidence", 0.7)
            },
            "nlg": {
                "response": nlg_response,
                "isComplete": readiness["auto_ready"],
                "suggestAssessment": readiness["auto_ready"] and message_count >= 5
            },
            "metadata": {
                "messageCount": message_count,
                "method": "Separate NLU+NLG Fallback"
            }
        }
    def _build_flexible_extraction_prompt(
        self, 
        user_message: str, 
        current_data: Dict[str, Any],
        context: str = None,
        bank_name: str = "VRB"
    ) -> str:
        """Build prompt for flexible extraction"""
        
        # Get all possible fields
        all_fields = list(self.field_priorities.keys())
        
        # Handle context section to avoid f-string backslash issue
        context_section = f"LỊCH SỬ HỘI THOẠI GẦN ĐÂY:\n{context}" if context else ""
        
        prompt = f"""
BẠN LÀ CHUYÊN GIA TRÍCH XUẤT THÔNG TIN VAY VỐN NGÂN HÀNG {bank_name}.

NHIỆM VỤ: Trích xuất TẤT CẢ thông tin có thể từ câu trả lời của khách hàng.

THÔNG TIN ĐÃ CÓ:
{self._format_current_data(current_data)}

CÁC FIELD CÓ THỂ TRÍCH XUẤT: {', '.join(all_fields)}

NGƯỜI DÙNG NÓI: "{user_message}"

{context_section}

Hãy phân tích và trích xuất theo format JSON:
{{
    "extractedData": {{
        // Chỉ include các field TÌM THẤY trong câu trả lời
        // Giữ nguyên ý định người dùng, đặc biệt cho loanPurpose
    }},
    "confidence": 0.85,
    "fieldsFound": ["field1", "field2"]
}}

QUY TẮC QUAN TRỌNG:
1. Trích xuất MỌI thông tin có thể, không chỉ field được hỏi
2. Tự động suy luận:
   - "30 tuổi" → birthYear: {datetime.now().year - 30}
   - "làm IT" → jobTitle: "IT", primaryIncomeSource: "Lương"
   - "có nhà ở Q7" → collateralType: "Bất động sản", collateralInfo: "Nhà ở Quận 7"
3. Số tiền và tiền tệ - ĐẶC BIỆT QUAN TRỌNG:
   - Tiếng Việt: "2 tỷ" → 2000000000, "500 triệu" → 500000000
   - Nước ngoài: "3000 USD", "5000 EUR" → monthlyIncome: 3000, currency: "USD" (GIỮ NGUYÊN SỐ + ĐƠN VỊ)
   - "income is 3000 usd" → monthlyIncome: 3000, currency: "USD"
   - "I said 3000 USD not VND" → monthlyIncome: 3000, currency: "USD" (xác nhận lại currency)
   - KHÔNG tự động convert sang VNĐ, để DeepSeek hỏi xác nhận và xử lý tỷ giá
   - Khi user xác nhận currency, lưu thông tin để không hỏi lại
4. Công ty và nghề nghiệp - QUAN TRỌNG:
   - "credit sales of VRB bank" → jobTitle: "credit sales", companyName: "VRB bank"
   - "work at ABC Company" → companyName: "ABC Company"
   - "occupation is manager" → jobTitle: "manager"
   - TÁCH RỜI job title và company name
5. loanPurpose: GIỮ NGUYÊN ý định (vd: "mua nhà" → "mua nhà", không convert)
6. loanType - QUY TẮC ĐẶC BIỆT - QUAN TRỌNG:
   - "unsecured" (tiếng Anh) → PHẢI TRẢ VỀ: "Tín chấp"
   - "secured", "mortgage", "thế chấp" → PHẢI TRẢ VỀ: "Thế chấp"
   - "tín chấp", "tin chap" → PHẢI TRẢ VỀ: "Tín chấp"
   - TUYỆT ĐỐI KHÔNG NHẦM LẪN: unsecured = Tín chấp (NO collateral needed)
7. Chú ý context hội thoại để hiểu đúng

CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH.
"""
        
        return prompt
    
    def _post_process_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy post-processing - use _post_process_extracted_data_with_validation instead"""
        processed_data, _ = self._post_process_extracted_data_with_validation(data)
        return processed_data
    
    def _fallback_flexible_extraction(self, user_message: str) -> Dict[str, Any]:
        """Fallback extraction using patterns"""
        extracted_data = {}
        user_lower = user_message.lower()
        
        # Loan amount patterns
        amount_patterns = [
            (r'(\d+(?:[.,]\d+)?)\s*tỷ', 1000000000),
            (r'(\d+(?:[.,]\d+)?)\s*triệu', 1000000),
        ]
        
        for pattern, multiplier in amount_patterns:
            match = re.search(pattern, user_lower)
            if match:
                amount = float(match.group(1).replace(',', '.'))
                extracted_data["loanAmount"] = int(amount * multiplier)
                break
        
        # Phone patterns
        phone_pattern = r'(?:0|\+84|84)?([0-9]{9,10})'
        phone_match = re.search(phone_pattern, user_message)
        if phone_match:
            phone = phone_match.group(0)
            if not phone.startswith('0'):
                phone = '0' + phone[-9:]
            extracted_data["phoneNumber"] = phone
        
        # Name detection (proper nouns)
        if re.search(r'\b(?:tên|là|tôi là)\s+(.+?)(?:\.|,|$)', user_lower):
            name_match = re.search(r'\b(?:tên|là|tôi là)\s+(.+?)(?:\.|,|$)', user_message, re.IGNORECASE)
            if name_match:
                extracted_data["fullName"] = name_match.group(1).strip()
        
        # Add more patterns as needed...
        
        return {
            "extractedData": extracted_data,
            "confidence": 0.6,
            "fieldsFound": list(extracted_data.keys()),
            "method": "Pattern Matching Fallback"
        }
    
    def _format_current_data(self, data: Dict[str, Any]) -> str:
        """Format current data for display"""
        if not data:
            return "Chưa có thông tin"
            
        lines = []
        for field, value in data.items():
            vn_name = self._get_vietnamese_field_name(field)
            
            # Format value
            if field in ['loanAmount', 'collateralValue', 'monthlyIncome'] and isinstance(value, (int, float)):
                formatted_value = f"{value:,.0f} VNĐ"
            else:
                formatted_value = str(value)
                
            lines.append(f"- {vn_name}: {formatted_value}")
            
        return "\n".join(lines)
    
    def _get_vietnamese_field_name(self, field: str) -> str:
        """Get Vietnamese name for field"""
        mapping = {
            "loanAmount": "Số tiền vay",
            "loanTerm": "Thời hạn vay",
            "loanPurpose": "Mục đích vay",
            "loanType": "Hình thức vay",
            "fullName": "Họ và tên",
            "phoneNumber": "Số điện thoại",
            "birthYear": "Năm sinh",
            "gender": "Giới tính",
            "maritalStatus": "Tình trạng hôn nhân",
            "dependents": "Số người phụ thuộc",
            "email": "Email",
            "monthlyIncome": "Thu nhập hàng tháng",
            "primaryIncomeSource": "Nguồn thu nhập chính",
            "collateralType": "Loại tài sản thế chấp",
            "collateralValue": "Giá trị tài sản",
            "collateralInfo": "Thông tin tài sản",
            "hasExistingDebt": "Nợ hiện tại",
            "totalDebtAmount": "Tổng dư nợ",
            "monthlyDebtPayment": "Trả nợ hàng tháng",
            "companyName": "Công ty",
            "jobTitle": "Chức vụ",
            "workExperience": "Kinh nghiệm",
            "salesAgentCode": "Mã nhân viên",
            "otherIncomeAmount": "Thu nhập khác",
            "totalAssets": "Tổng tài sản",
            "bankName": "Ngân hàng",
            "cicCreditScoreGroup": "Nhóm nợ CIC",
            "collateralImage": "Hình ảnh tài sản",
            "currency": "Đơn vị tiền tệ",
            "loanCurrency": "Đơn vị tiền tệ vay"
        }
        
        return mapping.get(field, field)
    
    def _extract_json_from_response(self, response: str) -> str:
        """Extract JSON from response"""
        # Remove markdown blocks
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*$', '', response)
        
        # Find JSON object
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return response
    
    def get_missing_priority_fields(self, current_data: Dict[str, Any]) -> List[str]:
        """Get missing fields sorted by priority"""
        missing = []
        
        for field, priority in sorted(self.field_priorities.items(), key=lambda x: x[1], reverse=True):
            if field not in current_data or current_data[field] in [None, "", 0]:
                # Special handling for 0 values in certain fields
                if field == "dependents" and current_data.get(field) == 0:
                    continue  # 0 is valid for dependents
                missing.append(field)
                
        return missing
    
    def calculate_readiness_score(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate assessment readiness score"""
        total_score = 0
        max_score = sum(self.field_priorities.values())
        
        for field, priority in self.field_priorities.items():
            if field in current_data and current_data[field] not in [None, ""]:
                # Special handling for 0 values
                if field == "dependents" and current_data[field] == 0:
                    total_score += priority
                elif current_data[field] != 0:
                    total_score += priority
        
        completion_percentage = (total_score / max_score) * 100
        
        return {
            "score": total_score,
            "maxScore": max_score,
            "percentage": completion_percentage,
            "canProceed": total_score >= 450  # ~60% minimum
        }
    
    def prepare_loan_assessment_payload(
        self,
        conversation_data: Dict[str, Any],
        conversation_history: List[Dict[str, str]] = None,
        additional_context: str = None
    ) -> Dict[str, Any]:
        """
        Prepare enhanced payload for loan assessment API with conversation history
        and validation scores
        """
        # Get completeness and readiness scores
        checker = FlexibleAssessmentChecker()
        readiness = checker.assess_readiness(conversation_data)
        
        # Build base payload from conversation data
        payload = {
            # Core loan information
            "loanAmount": conversation_data.get("loanAmount"),
            "loanTerm": conversation_data.get("loanTerm"),
            "loanType": conversation_data.get("loanType"),
            "loanPurpose": conversation_data.get("loanPurpose"),
            
            # Personal information
            "fullName": conversation_data.get("fullName"),
            "phoneNumber": conversation_data.get("phoneNumber"),
            "birthYear": conversation_data.get("birthYear"),
            "age": conversation_data.get("age"),
            "gender": conversation_data.get("gender"),
            "maritalStatus": conversation_data.get("maritalStatus"),
            "dependents": conversation_data.get("dependents"),
            
            # Income and employment
            "monthlyIncome": conversation_data.get("monthlyIncome"),
            "primaryIncomeSource": conversation_data.get("primaryIncomeSource"),
            "companyName": conversation_data.get("companyName"),
            "jobTitle": conversation_data.get("jobTitle"),
            "workExperience": conversation_data.get("workExperience"),
            
            # Debt and obligations
            "hasExistingDebt": conversation_data.get("hasExistingDebt"),
            "currentDebt": conversation_data.get("currentDebt"),
            "totalDebtAmount": conversation_data.get("totalDebtAmount"),
            "monthlyDebtPayment": conversation_data.get("monthlyDebtPayment"),
            
            # Credit and banking (enhanced)
            "cicCreditScoreGroup": conversation_data.get("cicCreditScoreGroup"),
            "hasCreditCard": conversation_data.get("hasCreditCard", False),
            "creditCardLimit": int(conversation_data.get("creditCardLimit", 0)),
            "hasSavingsAccount": conversation_data.get("hasSavingsAccount", False),
            "savingsAmount": int(conversation_data.get("savingsAmount", 0)),
            "bankName": conversation_data.get("bankName"),
            
            # Assets and collateral (enhanced)
            "hasProperty": conversation_data.get("hasProperty", False),
            "propertyValue": int(conversation_data.get("propertyValue", 0)),
            "hasCar": conversation_data.get("hasCar", False),
            "carValue": int(conversation_data.get("carValue", 0)),
            "collateralType": conversation_data.get("collateralType"),
            "collateralValue": conversation_data.get("collateralValue"),
            "collateralInfo": conversation_data.get("collateralInfo"),
            
            # Assessment metadata
            "dataCompleteness": readiness.get("completion_percentage", 0),
            "readinessScore": readiness.get("score", 0),
            "canProceedAssessment": readiness.get("can_proceed", False),
            "messageCount": conversation_data.get("_message_count", 0),
            
            # Enhanced context
            "conversationHistory": self._format_conversation_history(conversation_history) if conversation_history else [],
            "isFromChat": True,  # Always true when this method is called
            "salesAgentCode": "AI_SALES_AGENT",
            "additionalContext": additional_context,
            "extractionMethod": "AI_Enhanced_NLU",
            "timestamp": int(time.time()),
        }
        
        # Remove None values
        return {k: v for k, v in payload.items() if v is not None}
    
    def _format_conversation_history(self, history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Format conversation history for API payload"""
        formatted = []
        for i, exchange in enumerate(history[-10:]):  # Last 10 exchanges
            formatted.append({
                "turn": i + 1,
                "user_message": exchange.get("user", ""),
                "agent_response": exchange.get("agent", ""),
                "timestamp": exchange.get("timestamp", int(time.time()))
            })
        return formatted
    
    async def submit_loan_assessment(
        self,
        conversation_data: Dict[str, Any],
        conversation_history: List[Dict[str, str]] = None,
        api_endpoint: str = "/api/loan/assessment"
    ) -> Dict[str, Any]:
        """
        Submit loan assessment with conversation context to the API
        """
        try:
            # Prepare comprehensive payload
            payload = self.prepare_loan_assessment_payload(
                conversation_data, 
                conversation_history,
                additional_context="Data collected via AI Sales Agent conversation"
            )
            
            # Ensure required fields
            if not payload.get("applicationId"):
                payload["applicationId"] = f"ai_chat_{int(time.time())}"
                
            print(f"🏦 Submitting loan assessment for {payload.get('fullName', 'Unknown')}")
            print(f"💰 Loan amount: {payload.get('loanAmount', 0):,} VNĐ")
            print(f"💬 Conversation exchanges: {len(conversation_history) if conversation_history else 0}")
            print(f"📊 Data completeness: {payload.get('dataCompleteness', 0):.1f}%")
            
            # Here you would make the actual API call to your loan assessment endpoint
            # For now, return the prepared payload for inspection
            return {
                "success": True,
                "message": "Loan assessment payload prepared successfully",
                "payload": payload,
                "endpoint": api_endpoint
            }
            
        except Exception as e:
            print(f"❌ Error preparing loan assessment: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _detect_english(self, text: str) -> bool:
        """Enhanced English detection with better patterns and debugging"""
        english_indicators = [
            r'\b(i|my|me|you|we|they|he|she|it|am|is|are|was|were|have|has|had|will|would|could|should|can|may|might)\b',
            r'\b(want|need|like|loan|mortgage|income|work|job|years?|months?|name|phone|address|money|bank|credit|borrow|borrowing)\b',
            r'\b(hello|hi|please|thank|sorry|yes|no|okay|ok|sure|maybe|help|information|billion|million|thousand)\b',
            r'\b(for|from|with|without|about|after|before|during|until|since|because|although|while|when|where|what|why|how)\b'
        ]
        
        text_lower = text.lower()
        english_matches = []
        for pattern in english_indicators:
            matches = re.findall(pattern, text_lower)
            english_matches.extend(matches)
        english_count = len(english_matches)
        
        # Check for Vietnamese indicators
        vietnamese_indicators = [
            r'\b(tôi|tao|mình|anh|chị|em|được|là|có|không|của|và|với|cho|để|từ|này|đó|khi|như|về|sau|trước)\b',
            r'\b(tiền|vay|vốn|ngân hàng|lãi suất|thu nhập|công việc|năm|tháng|tuổi|sinh|ạ|ợ|muốn|cần|tỷ|triệu)\b'
        ]
        
        vietnamese_matches = []
        for pattern in vietnamese_indicators:
            matches = re.findall(pattern, text_lower)
            vietnamese_matches.extend(matches)
        vietnamese_count = len(vietnamese_matches)
        
        # Debug logging
        is_english = english_count > vietnamese_count and english_count >= 2
        print(f"🌐 Language Detection: '{text[:50]}...'")
        print(f"   English matches ({english_count}): {english_matches}")
        print(f"   Vietnamese matches ({vietnamese_count}): {vietnamese_matches}")
        print(f"   Detected: {'English' if is_english else 'Vietnamese'}")
        
        return is_english
    
    def _post_process_extracted_data_with_validation(self, data: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, str]]:
        """Enhanced post-processing with validation errors returned separately"""
        processed = {}
        validation_errors = {}
        
        # Field mapping for compatibility with loan assessment API
        field_mapping = {
            'income': 'monthlyIncome',
            'salary': 'monthlyIncome',
            'job': 'jobTitle',
            'position': 'jobTitle',
            'company': 'companyName',
            'workplace': 'companyName',
            'debt': 'currentDebt',
            'phone': 'phoneNumber',
            'name': 'fullName',
            'age': 'age',
            'born': 'birthYear',
            'birth_year': 'birthYear',
            'occupation': 'jobTitle'  # Map occupation to jobTitle for better processing
        }
        
        # Apply field mapping first
        mapped_data = {}
        for key, value in data.items():
            if value is None or value == "":
                continue
            
            # Check if field needs mapping
            mapped_key = field_mapping.get(key.lower(), key)
            mapped_data[mapped_key] = value
            
        # Check for currency information BEFORE processing numbers
        detected_currency = None
        for key, value in data.items():
            if key.lower() in ['currency', 'loanCurrency']:
                detected_currency = str(value).upper()
                break
        
        # If no explicit currency field, check for currency in string values
        if not detected_currency:
            for key, value in mapped_data.items():
                if isinstance(value, str) and key in ["monthlyIncome", "loanAmount", "collateralValue"]:
                    # Look for currency indicators in the value
                    value_upper = value.upper()
                    if 'USD' in value_upper:
                        detected_currency = 'USD'
                        break
                    elif 'EUR' in value_upper:
                        detected_currency = 'EUR'
                        break
        
        # Store detected currency
        if detected_currency and detected_currency != 'VND':
            mapped_data['currency'] = detected_currency
            
        # Process mapped data with validation
        for key, value in mapped_data.items():
            if value is None or value == "":
                continue
                
            # Birth year validation and age calculation
            if key == "birthYear":
                try:
                    birth_year = int(value) if isinstance(value, str) else value
                    current_year = 2025
                    age = current_year - birth_year
                    
                    # Validate age range (18-70 for loan eligibility)
                    if 18 <= age <= 70:
                        processed[key] = birth_year
                        processed["age"] = age
                    else:
                        # Add polite validation error
                        if age < 18:
                            validation_errors[key] = f"Anh/chị xem giúp em năm sinh {birth_year} này đã đúng chưa ạ? Vì theo tính toán thì anh/chị mới {age} tuổi."
                        elif age > 100:
                            validation_errors[key] = f"Anh/chị xem giúp em năm sinh {birth_year} này đã đúng chưa ạ? Cho em hỏi anh/chị năm nay bao nhiêu tuổi?"
                        else:
                            validation_errors[key] = f"Anh/chị xem giúp em năm sinh {birth_year} này đã đúng chưa ạ? Vì theo quy định ngân hàng chỉ cho vay với độ tuổi từ 18-70."
                        print(f"⚠️ Birth year {birth_year} results in age {age} (outside 18-70 range)")
                except (ValueError, TypeError):
                    validation_errors[key] = "Anh/chị có thể cho em biết chính xác năm sinh không ạ? Em cần ghi đúng thông tin."
                    print(f"⚠️ Invalid birth year format: {value}")
                continue
            
            # Phone number cleaning and validation
            if key == "phoneNumber" and isinstance(value, str):
                phone = re.sub(r'[^\d+]', '', value)
                if phone.startswith('+84'):
                    phone = '0' + phone[3:]
                elif phone.startswith('84'):
                    phone = '0' + phone[2:]
                
                # Validate Vietnamese phone format  
                if re.match(r'^0[3-9]\d{8}$', phone):
                    processed[key] = phone
                else:
                    validation_errors[key] = f"Anh/chị kiểm tra giúp em số điện thoại {value} có đúng định dạng không ạ? Em muốn ghi chính xác thông tin liên hệ."
                    print(f"⚠️ Invalid phone format: {phone}")
                continue
                
            # Number fields - Enhanced currency handling with currency detection
            if key in ["loanAmount", "collateralValue", "monthlyIncome", "totalDebtAmount", 
                      "monthlyDebtPayment", "otherIncomeAmount", "totalAssets", "dependents",
                      "creditCardLimit", "savingsAmount", "propertyValue", "carValue"]:
                if isinstance(value, (int, float)):
                    num_value = int(value)
                    
                    # Get detected currency from mapped data
                    currency_unit = mapped_data.get('currency', 'VND')
                    
                    # Special handling for currency amounts with foreign currency detection
                    if key in ["loanAmount", "monthlyIncome", "collateralValue"] and num_value > 0:
                        
                        # If we have a foreign currency detected
                        if currency_unit and currency_unit != 'VND':
                            processed[key] = num_value  # Store original amount
                            processed['currency'] = currency_unit  # Store currency separately
                            print(f"💰 Foreign currency detected: {key} = {num_value:,} {currency_unit}")
                        
                        # Check if this might be foreign currency (small numbers without explicit currency) - ONLY if no currency detected
                        elif num_value <= 100000 and key in ["loanAmount", "monthlyIncome"] and currency_unit == 'VND' and not mapped_data.get('currency'):
                            # This might be USD, EUR, etc. - ask for confirmation ONLY if no currency info available
                            validation_errors[key] = f"Could you please confirm the currency for {num_value:,}? Is this in VND, USD, or another currency? / Anh/chị xác nhận giúp em đơn vị tiền tệ cho số {num_value:,} này? VNĐ, USD hay đơn vị khác ạ?"
                            print(f"⚠️ Ambiguous currency for {key}: {num_value} (might be foreign currency)")
                            processed[key] = num_value  # Store the number but flag for confirmation
                        else:
                            processed[key] = num_value
                            
                    elif key == "loanAmount" and num_value > 0:
                        if num_value < 50_000_000 and currency_unit == 'VND':  # Less than 50M VND
                            validation_errors[key] = f"Anh/chị xác nhận lại số tiền vay {num_value:,} có đúng không ạ? Đơn vị tiền tệ là gì? / Could you confirm the loan amount {num_value:,} and the currency unit?"
                        elif num_value > 50_000_000_000:  # More than 50B VND
                            validation_errors[key] = f"Anh/chị xác nhận lại số tiền vay {num_value:,} VNĐ có đúng không ạ? Số tiền này khá lớn, em cần xác nhận chính xác."
                        processed[key] = num_value
                    elif key == "monthlyIncome" and num_value > 0:
                        processed[key] = num_value
                    elif key == "dependents" and 0 <= num_value <= 20:
                        processed[key] = num_value
                    elif key in ["totalDebtAmount", "monthlyDebtPayment"] and num_value >= 0:
                        processed[key] = num_value
                    else:
                        processed[key] = num_value
                continue
                    
            # Name normalization
            if key == "fullName" and isinstance(value, str):
                processed[key] = ' '.join(word.capitalize() for word in value.split())
                continue
                
            # Loan type normalization - CRITICAL LOGIC
            if key == "loanType":
                value_lower = str(value).lower()
                print(f"🔍 Processing loanType: '{value}' -> '{value_lower}'")
                
                # Check for unsecured loan indicators FIRST - EXACT MATCH
                if 'unsecured' in value_lower or any(word in value_lower for word in ['tín chấp', 'tin chap', 'không tài sản']):
                    processed[key] = "Tín chấp"
                    print(f"✅ Detected unsecured loan: '{value}' -> 'Tín chấp'")
                # Check for secured loan indicators AFTER
                elif any(word in value_lower for word in ['thế chấp', 'the chap', 'secured', 'mortgage', 'có tài sản']):
                    processed[key] = "Thế chấp"
                    print(f"✅ Detected secured loan: '{value}' -> 'Thế chấp'")
                else:
                    processed[key] = value
                    print(f"⚠️ Unknown loan type, keeping original: '{value}'")
                continue
                    
            # Job title processing to extract company names
            if key == "jobTitle" and isinstance(value, str):
                # Look for patterns like "credit sales of VRB bank", "manager at ABC Corp"
                job_patterns = [
                    (r'(.+?)\s+(?:of|at)\s+(.+)', lambda m: (m.group(1).strip(), m.group(2).strip())),
                    (r'(.+?)\s+(?:tại|ở)\s+(.+)', lambda m: (m.group(1).strip(), m.group(2).strip())),
                ]
                
                for pattern, extractor in job_patterns:
                    match = re.search(pattern, value, re.IGNORECASE)
                    if match:
                        job_title, company_name = extractor(match)
                        processed[key] = job_title
                        processed["companyName"] = company_name
                        print(f"🏢 Extracted from jobTitle '{value}': job='{job_title}', company='{company_name}'")
                        break
                else:
                    # No pattern matched, keep original job title
                    processed[key] = value
                continue
                
            # Collateral information validation for mortgage loans
            if key == "collateralType" and isinstance(value, str):
                # Normalize collateral type
                collateral_lower = value.lower()
                if any(word in collateral_lower for word in ['nhà', 'house', 'bất động sản', 'property']):
                    processed[key] = "Bất động sản - Nhà ở"
                elif any(word in collateral_lower for word in ['căn hộ', 'apartment', 'chung cư']):
                    processed[key] = "Bất động sản - Căn hộ"
                elif any(word in collateral_lower for word in ['đất', 'land', 'thổ cư']):
                    processed[key] = "Bất động sản - Đất"
                elif any(word in collateral_lower for word in ['xe', 'car', 'ô tô', 'vehicle']):
                    processed[key] = "Phương tiện - Xe hơi"
                elif any(word in collateral_lower for word in ['xe máy', 'motorbike', 'motor']):
                    processed[key] = "Phương tiện - Xe máy"
                else:
                    processed[key] = value
                print(f"🏠 Collateral type normalized: '{value}' -> '{processed[key]}'")
                continue
                
            if key == "collateralInfo" and isinstance(value, str):
                # Validate collateral info completeness
                info_lower = value.lower()
                has_address = any(word in info_lower for word in ['địa chỉ', 'address', 'đường', 'quận', 'phường'])
                has_size = any(word in info_lower for word in ['m2', 'diện tích', 'size', 'mét'])
                has_legal = any(word in info_lower for word in ['sổ', 'giấy tờ', 'pháp lý', 'legal', 'ownership'])
                
                if len(value.strip()) < 20:
                    validation_errors[key] = "Anh/chị có thể mô tả chi tiết hơn về tài sản không? Em cần thông tin về địa chỉ, diện tích, tình trạng pháp lý để đánh giá chính xác."
                elif not (has_address or has_size or has_legal):
                    validation_errors[key] = "Em cần thêm thông tin chi tiết như: địa chỉ, diện tích, tình trạng sổ đỏ/giấy tờ pháp lý. Anh/chị bổ sung giúp em?"
                else:
                    processed[key] = value
                continue
                
            if key == "collateralValue" and isinstance(value, (int, float)):
                collateral_value = int(value)
                if collateral_value <= 0:
                    validation_errors[key] = "Giá trị tài sản thế chấp phải lớn hơn 0. Anh/chị ước tính lại giúp em?"
                elif collateral_value < 50000000:  # Less than 50M VND
                    validation_errors[key] = f"Anh/chị xác nhận tài sản có giá trị {collateral_value:,} VNĐ? Giá trị này có vẻ thấp so với yêu cầu vay thế chấp."
                elif collateral_value > 100000000000:  # More than 100B VND
                    validation_errors[key] = f"Anh/chị xác nhận tài sản có giá trị {collateral_value:,} VNĐ? Em cần xác nhận lại giá trị này."
                else:
                    processed[key] = collateral_value
                    print(f"🏠 Collateral value processed: {collateral_value:,} VNĐ")
                continue
                
            # Boolean fields with enhanced mapping
            if key in ["hasExistingDebt", "collateralImage", "hasCreditCard", "hasSavingsAccount", 
                      "hasProperty", "hasCar", "hasBankStatement"]:
                if isinstance(value, bool):
                    processed[key] = value
                elif isinstance(value, str):
                    processed[key] = value.lower() in ['true', 'có', 'yes', '1', 'đang có']
                continue
                
            # Default - keep as is
            processed[key] = value
        
        return processed, validation_errors