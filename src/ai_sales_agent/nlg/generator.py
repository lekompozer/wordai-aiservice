"""
Enhanced NLG Generator using AI for natural question generation
"""

import random
import asyncio
from typing import Dict, Any, List, Optional
from ..models.nlu_models import StepSubQuestion, STEP_CONFIGS
from .question_templates import (
    STEP_1_1_TEMPLATES, STEP_1_2_TEMPLATES, 
    STEP_2_1_TEMPLATES, STEP_2_2_TEMPLATES,
    STEP_3_1_TEMPLATES, STEP_3_2_TEMPLATES,
    STEP_4_1_TEMPLATES, STEP_4_2_TEMPLATES, STEP_4_3_TEMPLATES,
    STEP_5_1_TEMPLATES, STEP_5_2_TEMPLATES,
    STEP_6_TEMPLATES, STEP_7_TEMPLATES,
    FIELD_DISPLAY_NAMES, FIELD_SUGGESTIONS, FIELD_EXAMPLES
)
from ..services.ai_provider import AISalesAgentProvider
from src.providers.ai_provider_manager import AIProviderManager
from src.core.config import APP_CONFIG


class NLGGenerator:
    """
    Enhanced NLG generator with AI integration and template fallback
    """
    
    def __init__(self):
        self.templates = {
            StepSubQuestion.STEP_1_1: STEP_1_1_TEMPLATES,
            StepSubQuestion.STEP_1_2: STEP_1_2_TEMPLATES,
            StepSubQuestion.STEP_2_1: STEP_2_1_TEMPLATES,
            StepSubQuestion.STEP_2_2: STEP_2_2_TEMPLATES,
            StepSubQuestion.STEP_3_1: STEP_3_1_TEMPLATES,
            StepSubQuestion.STEP_3_2: STEP_3_2_TEMPLATES,
            StepSubQuestion.STEP_4_1: STEP_4_1_TEMPLATES,
            StepSubQuestion.STEP_4_2: STEP_4_2_TEMPLATES,
            StepSubQuestion.STEP_4_3: STEP_4_3_TEMPLATES,
            StepSubQuestion.STEP_5_1: STEP_5_1_TEMPLATES,
            StepSubQuestion.STEP_5_2: STEP_5_2_TEMPLATES,
            StepSubQuestion.STEP_6: STEP_6_TEMPLATES,
            StepSubQuestion.STEP_7: STEP_7_TEMPLATES
        }
        
        # AI Provider for enhanced question generation
        try:
            ai_manager = AIProviderManager(
                deepseek_api_key=APP_CONFIG.get('deepseek_api_key', ''),
                chatgpt_api_key=APP_CONFIG.get('chatgpt_api_key', '')
            )
            self.ai_provider = AISalesAgentProvider(ai_manager)
            self.use_ai = True
            print("✅ NLG initialized with AI provider")
        except Exception as e:
            print(f"⚠️ AI provider failed to initialize: {e}")
            self.ai_provider = None
            self.use_ai = False
    
    def generate_question(
        self,
        current_step: StepSubQuestion,
        extracted_fields: Dict[str, Any],
        missing_fields: List[str],
        validation_errors: Optional[Dict[str, str]] = None,
        is_first_interaction: bool = False
    ) -> str:
        """
        Enhanced question generation using AI with template fallback
        
        Args:
            current_step: Current step in conversation flow
            extracted_fields: Already extracted field values
            missing_fields: List of required fields that are still missing
            validation_errors: Any validation errors to address
            is_first_interaction: Whether this is the first question for this step
            
        Returns:
            Generated question string
        """
        
        print(f"🔄 NLG Generation: Step {current_step.value} with AI={self.use_ai}")
        print(f"📋 Missing fields: {missing_fields}")
        
        # Try AI generation first if available
        if self.use_ai and self.ai_provider:
            try:
                print("🤖 Using AI question generation...")
                # Run async AI generation in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.ai_provider.generate_question_stream(
                        current_step.value, extracted_fields, missing_fields, 
                        is_first_interaction, validation_errors
                    )
                )
                loop.close()
                
                print(f"✅ AI generation successful: {result[:100]}...")
                return result
                
            except Exception as e:
                print(f"❌ AI generation failed: {e}, falling back to templates")
                # Continue to template fallback
        
        # Template-based fallback generation
        print("📝 Using template generation...")
        return self._template_generation(
            current_step, extracted_fields, missing_fields, validation_errors, is_first_interaction
        )
    
    def _template_generation(
        self,
        current_step: StepSubQuestion,
        extracted_fields: Dict[str, Any],
        missing_fields: List[str],
        validation_errors: Optional[Dict[str, str]] = None,
        is_first_interaction: bool = False
    ) -> str:
        """Template-based question generation (original logic)"""
        
        # Handle validation errors first
        if validation_errors:
            return self._generate_validation_error_message(
                current_step, validation_errors, extracted_fields
            )
        
        # Get template collection for current step
        step_templates = self.templates.get(current_step)
        if not step_templates:
            return "Xin lỗi, có lỗi hệ thống. Vui lòng thử lại."
        
        # First interaction for this step
        if is_first_interaction and missing_fields:
            return self._get_random_template(step_templates["first_question"])
        
        # Generate question based on missing fields
        return self._generate_missing_fields_question(
            current_step, step_templates, missing_fields, extracted_fields
        )
    
    def _generate_missing_fields_question(
        self,
        current_step: StepSubQuestion,
        templates: Dict[str, List[str]],
        missing_fields: List[str],
        extracted_fields: Dict[str, Any]
    ) -> str:
        """Generate question for missing fields"""
        
        if not missing_fields:
            # All fields complete for this step
            return self._generate_completion_message(current_step, extracted_fields)
        
        if len(missing_fields) == 1:
            # Single missing field
            field = missing_fields[0]
            template_key = f"missing_{field}"
            
            if template_key in templates:
                question = self._get_random_template(templates[template_key])
                return self._add_field_suggestions(field, question)
            else:
                # Fallback
                display_name = FIELD_DISPLAY_NAMES.get(field, field)
                return f"Vui lòng cho biết {display_name}."
        
        else:
            # Multiple missing fields
            if "missing_multiple" in templates:
                template = self._get_random_template(templates["missing_multiple"])
                missing_display = self._format_missing_fields(missing_fields)
                return template.format(
                    missing_fields=missing_display,
                    name=extracted_fields.get("fullName", "bạn")
                )
            else:
                # Fallback for multiple fields
                missing_display = self._format_missing_fields(missing_fields)
                return f"Vui lòng cung cấp thêm thông tin: {missing_display}"
    
    def _generate_completion_message(
        self,
        current_step: StepSubQuestion,
        extracted_fields: Dict[str, Any]
    ) -> str:
        """Generate completion message when step is done"""
        
        step_templates = self.templates.get(current_step, {})
        
        if "completion" in step_templates:
            template = self._get_random_template(step_templates["completion"])
            
            # Format with available field values
            try:
                return template.format(**extracted_fields)
            except (KeyError, ValueError):
                # Fallback if formatting fails
                return self._get_random_template(step_templates["completion"])
        
        # Default completion message
        step_name = self._get_step_display_name(current_step)
        return f"Cảm ơn bạn! Đã hoàn thành {step_name}."
    
    def _generate_validation_error_message(
        self,
        current_step: StepSubQuestion,
        validation_errors: Dict[str, str],
        extracted_fields: Dict[str, Any]
    ) -> str:
        """Generate error message for validation failures"""
        
        step_templates = self.templates.get(current_step, {})
        
        # Handle specific validation errors
        for field, error_type in validation_errors.items():
            template_key = f"{error_type}"
            
            if template_key in step_templates:
                return self._get_random_template(step_templates[template_key])
        
        # Generic validation error
        return "Vui lòng kiểm tra và nhập lại thông tin cho đúng định dạng."
    
    def _format_missing_fields(self, missing_fields: List[str]) -> str:
        """Format list of missing fields for display"""
        
        display_names = [
            FIELD_DISPLAY_NAMES.get(field, field) 
            for field in missing_fields
        ]
        
        if len(display_names) == 1:
            return display_names[0]
        elif len(display_names) == 2:
            return f"{display_names[0]} và {display_names[1]}"
        else:
            return f"{', '.join(display_names[:-1])} và {display_names[-1]}"
    
    def _add_field_suggestions(self, field: str, base_question: str) -> str:
        """Add helpful suggestions/examples to question"""
        
        suggestions = FIELD_SUGGESTIONS.get(field)
        examples = FIELD_EXAMPLES.get(field)
        
        if suggestions:
            suggestion_text = " hoặc ".join(suggestions)
            return f"{base_question}\nGợi ý: {suggestion_text}"
        
        elif examples:
            example_text = ", ".join(examples[:2])  # Show max 2 examples
            return f"{base_question}\nVí dụ: {example_text}"
        
        return base_question
    
    def _get_random_template(self, templates: List[str]) -> str:
        """Get random template for variation"""
        if not templates:
            return "Vui lòng cung cấp thông tin."
        return random.choice(templates)
    
    def _get_step_display_name(self, step: StepSubQuestion) -> str:
        """Get display name for step"""
        step_names = {
            StepSubQuestion.STEP_1_1: "thông tin khoản vay cơ bản",
            StepSubQuestion.STEP_1_2: "thông tin khoản vay bổ sung", 
            StepSubQuestion.STEP_2_1: "thông tin cá nhân cơ bản",
            StepSubQuestion.STEP_2_2: "thông tin cá nhân chi tiết"
        }
        return step_names.get(step, "bước hiện tại")
    
    def generate_welcome_message(self) -> str:
        """Generate initial welcome message"""
        welcome_messages = [
            "Xin chào! Tôi là trợ lý AI của ngân hàng, sẽ hỗ trợ bạn hoàn thành hồ sơ thẩm định vay một cách nhanh chóng và chính xác.",
            "Chào mừng bạn đến với dịch vụ thẩm định vay trực tuyến! Tôi sẽ hướng dẫn bạn từng bước để hoàn thiện hồ sơ.",
            "Xin chào! Để giúp bạn có trải nghiệm tốt nhất, tôi sẽ thu thập thông tin theo từng bước một cách có hệ thống."
        ]
        return self._get_random_template(welcome_messages)
    
    def generate_step_transition_message(
        self, 
        from_step: StepSubQuestion, 
        to_step: StepSubQuestion,
        extracted_fields: Dict[str, Any]
    ) -> str:
        """Generate transition message between steps"""
        
        if from_step == StepSubQuestion.STEP_1_1 and to_step == StepSubQuestion.STEP_1_2:
            return "Tuyệt vời! Bây giờ chúng ta sẽ hoàn thành thông tin khoản vay."
        
        elif from_step == StepSubQuestion.STEP_1_2 and to_step == StepSubQuestion.STEP_2_1:
            return "Cảm ơn bạn! Tiếp theo, chúng ta sẽ thu thập thông tin cá nhân để hoàn thiện hồ sơ."
        
        elif from_step == StepSubQuestion.STEP_2_1 and to_step == StepSubQuestion.STEP_2_2:
            name = extracted_fields.get("fullName", "bạn")
            return f"Cảm ơn {name}! Cuối cùng, chúng ta cần một số thông tin bổ sung để hoàn tất hồ sơ."
        
        return "Chúng ta tiếp tục với bước tiếp theo."
    
    def generate_final_summary(self, all_extracted_fields: Dict[str, Any]) -> str:
        """Generate final summary of all collected information"""
        
        name = all_extracted_fields.get("fullName", "Quý khách")
        loan_amount = all_extracted_fields.get("loanAmount", "N/A")
        loan_term = all_extracted_fields.get("loanTerm", "N/A")
        loan_purpose = all_extracted_fields.get("loanPurpose", "N/A")
        loan_type = all_extracted_fields.get("loanType", "N/A")
        
        summary = f"""
🎉 HOÀN THÀNH HỒ SƠ THẨM ĐỊNH VAY 🎉

Cảm ơn {name} đã hoàn thành quy trình!

📋 THÔNG TIN KHOẢN VAY:
• Số tiền: {loan_amount:,} VND
• Thời hạn: {loan_term}
• Mục đích: {loan_purpose}
• Hình thức: {loan_type}

👤 THÔNG TIN CÁ NHÂN:
• Họ tên: {name}
• Số điện thoại: {all_extracted_fields.get("phoneNumber", "N/A")}
• Năm sinh: {all_extracted_fields.get("birthYear", "N/A")}

⏰ BƯỚC TIẾP THEO:
Hồ sơ của bạn sẽ được chuyển đến bộ phận thẩm định. Chúng tôi sẽ liên hệ trong vòng 24-48 giờ với kết quả sơ bộ.

Cảm ơn bạn đã tin tưởng sử dụng dịch vụ của chúng tôi! 🏦
        """.strip()
        
        return summary
    
    def generate_question_simple(
        self,
        current_step: str,
        extracted_fields: Dict[str, Any],
        missing_fields: List[str],
        is_first_interaction: bool = False
    ) -> Dict[str, Any]:
        """
        Generate question using AI - Simplified signature for test
        """
        print(f"🔄 NLG Generation: Step {current_step} with AI={self.use_ai}")
        print(f"📋 Missing fields: {missing_fields}")
        
        try:
            # Try AI generation first if available
            if self.use_ai and self.ai_provider:
                print("🤖 Using AI question generation...")
                # Run async AI generation
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.ai_provider.generate_question_async(
                        current_step, extracted_fields, missing_fields, is_first_interaction
                    )
                )
                loop.close()
                
                return {
                    "question": result,
                    "method": "AI (DeepSeek)",
                    "summary": self._generate_summary(extracted_fields) if extracted_fields else ""
                }
            else:
                print("📝 Using template fallback...")
                return self._template_fallback_generation(current_step, missing_fields, is_first_interaction)
                
        except Exception as e:
            print(f"❌ AI generation failed, using fallback: {e}")
            return self._template_fallback_generation(current_step, missing_fields, is_first_interaction)
    
    def _generate_summary(self, extracted_fields: Dict[str, Any]) -> str:
        """Generate summary of collected data"""
        if not extracted_fields:
            return ""
        
        summary_parts = []
        for key, value in extracted_fields.items():
            if key == "loanAmount" and isinstance(value, (int, float)):
                summary_parts.append(f"Số tiền vay: {value:,} VND")
            elif key == "fullName":
                summary_parts.append(f"Họ tên: {value}")
            elif key == "phoneNumber":
                summary_parts.append(f"SĐT: {value}")
            else:
                summary_parts.append(f"{key}: {value}")
        
        return "Thông tin đã thu thập: " + ", ".join(summary_parts)
    
    def _template_fallback_generation(self, current_step: str, missing_fields: List[str], 
                                    is_first_interaction: bool) -> Dict[str, Any]:
        """Fallback template-based generation"""
        templates = {
            "1.1": [
                "Chào anh/chị! Để bắt đầu hồ sơ vay, vui lòng cho biết số tiền cần vay, thời hạn vay và mục đích sử dụng vốn?",
                "Xin chào! Anh/chị muốn vay bao nhiêu tiền, trong thời gian bao lâu và để làm gì?"
            ],
            "1.2": [
                "Cảm ơn anh/chị! Vui lòng cho biết hình thức vay (thế chấp hay tín chấp) và mã nhân viên tư vấn (nếu có)?",
                "Anh/chị muốn vay theo hình thức nào và có mã nhân viên giới thiệu không?"
            ],
            "2.1": [
                "Tiếp theo, vui lòng cung cấp họ tên đầy đủ, số điện thoại và năm sinh của anh/chị?",
                "Để hoàn thiện hồ sơ, tôi cần họ tên, số điện thoại và năm sinh của anh/chị?"
            ],
            "2.2": [
                "Cuối cùng, vui lòng cho biết giới tính, tình trạng hôn nhân, số người phụ thuộc và email (nếu có)?",
                "Cần thêm một số thông tin: Giới tính? Đã kết hôn chưa? Có bao nhiêu người phụ thuộc? Email liên hệ?"
            ]
        }
        
        import random
        question = random.choice(templates.get(current_step, ["Vui lòng cung cấp thông tin còn thiếu."]))
        
        return {
            "question": question,
            "method": "Template fallback",
            "summary": ""
        }
    
    def generate_step_6_summary(self, extracted_fields: Dict[str, Any]) -> str:
        """
        Generate Step 6 confirmation summary
        """
        try:
            template = STEP_6_TEMPLATES["summary"][0]
            
            # Format fields for display
            formatted_fields = {}
            for key, value in extracted_fields.items():
                if value is None or value == "":
                    formatted_fields[key] = "Chưa cung cấp"
                elif isinstance(value, bool):
                    formatted_fields[key] = "Có" if value else "Không"
                elif isinstance(value, (int, float)) and key in ["loanAmount", "collateralValue", "monthlyIncome", "otherIncomeAmount", "totalDebtAmount", "monthlyDebtPayment"]:
                    formatted_fields[key] = int(value)
                else:
                    formatted_fields[key] = str(value)
            
            # Set defaults for missing fields
            required_fields = [
                "loanAmount", "loanTerm", "loanPurpose", "loanType",
                "fullName", "gender", "birthYear", "phoneNumber", "email", "maritalStatus", "dependents",
                "collateralType", "collateralInfo", "collateralValue",
                "monthlyIncome", "primaryIncomeSource", "companyName", "jobTitle", "workExperience", "otherIncomeAmount",
                "hasExistingDebt", "totalDebtAmount", "monthlyDebtPayment"
            ]
            
            for field in required_fields:
                if field not in formatted_fields:
                    if field in ["loanAmount", "collateralValue", "monthlyIncome", "otherIncomeAmount", "totalDebtAmount", "monthlyDebtPayment"]:
                        formatted_fields[field] = 0
                    else:
                        formatted_fields[field] = "Chưa cung cấp"
            
            return template.format(**formatted_fields)
            
        except Exception as e:
            print(f"❌ Error generating Step 6 summary: {e}")
            return "📋 **XÁC NHẬN THÔNG TIN HỒ SƠ VAY**\n\nCó lỗi hiển thị thông tin. Vui lòng thử lại."
    def generate_step_6_confirmation(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Step 6 confirmation with all collected data
        
        Returns:
            Dict with question (confirmation message), method, and summary
        """
        try:
            # Generate comprehensive summary
            summary = self.generate_step_6_summary(extracted_fields)
            
            # Add edit instructions
            edit_instructions = random.choice(STEP_6_TEMPLATES["edit_instructions"])
            
            full_message = f"{summary}\n\n{edit_instructions}"
            
            return {
                "question": full_message,
                "method": "Step 6 Confirmation",
                "summary": "Xác nhận thông tin hồ sơ vay",
                "requires_confirmation": True
            }
            
        except Exception as e:
            print(f"❌ Error generating Step 6 confirmation: {e}")
            return {
                "question": "Có lỗi khi hiển thị thông tin. Vui lòng thử lại.",
                "method": "Error",
                "summary": ""
            }
    
    def process_step_6_response(self, user_response: str, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user response in Step 6 (confirmation or edit)
        
        Returns:
            Dict with:
            - action: 'confirm', 'edit', or 'invalid'
            - field: field to edit (if action is 'edit')
            - value: new value (if action is 'edit')
            - message: response message
        """
        response_lower = user_response.lower().strip()
        
        # Check for confirmation
        if response_lower in ["xác nhận", "xac nhan", "confirm", "ok", "đồng ý", "dong y"]:
            return {
                "action": "confirm",
                "message": random.choice(STEP_6_TEMPLATES["confirmation_success"]),
                "next_step": "7"
            }
        
        # Check for edit command
        edit_result = self.parse_step_6_edit_command(user_response)
        if edit_result.get("is_edit"):
            return {
                "action": "edit",
                "field": edit_result["field"],
                "value": edit_result["value"],
                "message": random.choice(STEP_6_TEMPLATES["edit_success"])
            }
        
        # Invalid response
        return {
            "action": "invalid",
            "message": "Vui lòng trả lời 'Xác nhận' hoặc 'Sửa [field]: [giá trị]' để chỉnh sửa thông tin."
        }
    
    def generate_step_7_processing_message(self) -> Dict[str, Any]:
        """
        Generate processing message while waiting for assessment
        """
        return {
            "question": random.choice(STEP_7_TEMPLATES["processing"]),
            "method": "Step 7 Processing",
            "summary": "Đang thẩm định hồ sơ",
            "is_processing": True
        }
    
    def format_assessment_result(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format loan assessment result from /api/loan/assessment API response
        Matches the LoanAssessmentResponse structure exactly
        """
        try:
            # Check if assessment was successful
            if not assessment_data.get("success", False):
                error_msg = assessment_data.get("error", "Không thể thẩm định hồ sơ")
                return {
                    "question": f"❌ **THẨM ĐỊNH THẤT BẠI**\n\n{error_msg}\n\nVui lòng kiểm tra lại thông tin hoặc liên hệ hỗ trợ.",
                    "method": "Assessment Error",
                    "summary": "Thẩm định thất bại",
                    "is_error": True
                }
            
            # Extract key information from API response
            status = assessment_data.get('status', 'unknown')
            confidence = assessment_data.get('confidence', 0)
            credit_score = assessment_data.get('creditScore', 0)
            reasoning = assessment_data.get('reasoning', '')
            assessment_id = assessment_data.get('assessmentId', 'N/A')
            
            # Map status to Vietnamese display
            status_mapping = {
                'approved': '✅ PHÊ DUYỆT',
                'rejected': '❌ TỪ CHỐI', 
                'needs_review': '⚠️ CẦN XEM XÉT THÊM',
                'conditional_approval': '🟡 PHÊ DUYỆT CÓ ĐIỀU KIỆN'
            }
            
            status_display = status_mapping.get(status, f'❓ {status.upper()}')
            confidence_percent = round(confidence * 100, 1) if confidence else 0
            
            # Build main assessment message
            message_parts = [
                f"🏦 **KẾT QUẢ THẨM ĐỊNH HỒ SƠ VAY**",
                f"",
                f"📋 **Mã thẩm định**: {assessment_id}",
                f"🎯 **Quyết định**: {status_display}",
                f"📊 **Độ tin cậy**: {confidence_percent}%",
                f"💳 **Điểm tín dụng**: {credit_score}/850",
                f"",
                f"📝 **Phân tích chi tiết**:",
                f"{reasoning}",
                f""
            ]
            
            # Add loan details if approved
            if status in ['approved', 'conditional_approval']:
                approved_amount = assessment_data.get('approvedAmount')
                interest_rate = assessment_data.get('interestRate', 8.5)
                loan_term = assessment_data.get('loanTerm', 15)
                monthly_payment = assessment_data.get('monthlyPayment')
                
                if approved_amount:
                    message_parts.extend([
                        f"💰 **THÔNG TIN KHOẢN VAY ĐƯỢC DUYỆT**:",
                        f"• Số tiền: {approved_amount:,} VNĐ",
                        f"• Lãi suất: {interest_rate}%/năm",
                        f"• Thời hạn: {loan_term} năm",
                        f"• Trả góp hàng tháng: {monthly_payment:,} VNĐ" if monthly_payment else "• Trả góp: Đang tính toán",
                        f""
                    ])
            
            # Add financial ratios
            debt_to_income = assessment_data.get('debtToIncome')
            loan_to_value = assessment_data.get('loanToValue')
            
            if debt_to_income is not None or loan_to_value is not None:
                message_parts.extend([
                    f"📊 **CHỈ SỐ TÀI CHÍNH**:",
                ])
                
                if debt_to_income is not None:
                    dti_percent = round(debt_to_income * 100, 1)
                    dti_status = "✅ Tốt" if dti_percent <= 40 else "⚠️ Cao" if dti_percent <= 50 else "❌ Quá cao"
                    message_parts.append(f"• Tỷ lệ nợ/thu nhập: {dti_percent}% ({dti_status})")
                
                if loan_to_value is not None:
                    ltv_percent = round(loan_to_value * 100, 1)
                    ltv_status = "✅ An toàn" if ltv_percent <= 70 else "⚠️ Chấp nhận được" if ltv_percent <= 80 else "❌ Rủi ro cao"
                    message_parts.append(f"• Tỷ lệ vay/tài sản: {ltv_percent}% ({ltv_status})")
                
                message_parts.append("")
            
            # Add risk factors
            risk_factors = assessment_data.get('riskFactors', [])
            if risk_factors:
                message_parts.extend([
                    f"⚠️ **YẾU TỐ RỦI RO**:",
                    *[f"• {risk}" for risk in risk_factors[:5]],  # Show max 5 risks
                    f""
                ])
            
            # Add recommendations
            recommendations = assessment_data.get('recommendations', [])
            if recommendations:
                message_parts.extend([
                    f"💡 **KHUYẾN NGHỊ**:",
                    *[f"• {rec}" for rec in recommendations[:5]],  # Show max 5 recommendations
                    f""
                ])
            
            # Add conditions if any
            conditions = assessment_data.get('conditions', [])
            if conditions:
                message_parts.extend([
                    f"📋 **ĐIỀU KIỆN VAY** (nếu được phê duyệt):",
                    *[f"• {cond}" for cond in conditions[:5]],
                    f""
                ])
            
            # Add next steps based on status
            if status == 'approved':
                message_parts.extend([
                    f"🎉 **BƯỚC TIẾP THEO**:",
                    f"• Chuẩn bị hồ sơ pháp lý theo yêu cầu",
                    f"• Thẩm định tài sản đảm bảo (nếu cần)",
                    f"• Ký kết hợp đồng tín dụng", 
                    f"• Giải ngân theo thỏa thuận"
                ])
            elif status == 'conditional_approval':
                message_parts.extend([
                    f"📋 **BƯỚC TIẾP THEO**:",
                    f"• Hoàn thành các điều kiện được nêu trên",
                    f"• Bổ sung tài liệu (nếu được yêu cầu)",
                    f"• Thẩm định lại sau khi đáp ứng điều kiện"
                ])
            elif status == 'needs_review':
                message_parts.extend([
                    f"🔍 **BƯỚC TIẾP THEO**:",
                    f"• Hồ sơ sẽ được chuyển lên cấp cao hơn",
                    f"• Có thể cần bổ sung thêm thông tin",
                    f"• Kết quả sẽ có trong 3-5 ngày làm việc"
                ])
            else:  # rejected
                message_parts.extend([
                    f"📞 **BƯỚC TIẾP THEO**:",
                    f"• Tham khảo các khuyến nghị để cải thiện hồ sơ",
                    f"• Có thể nộp lại hồ sơ sau 6 tháng",
                    f"• Liên hệ tư vấn viên để được hỗ trợ"
                ])
            
            formatted_message = "\n".join(message_parts)
            
            return {
                "question": formatted_message,
                "method": "Loan Assessment Complete",
                "summary": f"{status_display} - Tin cậy: {confidence_percent}%",
                "is_complete": True,
                "assessment_data": assessment_data,
                "status": status,
                "approved": status in ['approved', 'conditional_approval']
            }
            
        except Exception as e:
            print(f"❌ Error formatting assessment result: {e}")
            return {
                "question": "Có lỗi khi hiển thị kết quả thẩm định. Vui lòng liên hệ hỗ trợ.",
                "method": "Error",
                "summary": "",
                "is_error": True
            }
    
    def prepare_assessment_payload(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare payload for loan assessment API matching LoanApplicationRequest exactly
        """
        from datetime import datetime
        import time
        
        # Generate application ID if not exists
        application_id = conversation_data.get('applicationId', f"APP_{int(time.time() * 1000)}")
        
        # Parse loan term to ensure correct format for API
        loan_term = conversation_data.get('loanTerm', 15)
        if isinstance(loan_term, (int, float)):
            loan_term_str = f"{int(loan_term)} năm"
        else:
            loan_term_str = str(loan_term)
            if 'năm' not in loan_term_str.lower():
                # If just a number, assume it's years
                try:
                    years = int(float(str(loan_term).replace('tháng', '').replace('năm', '').strip()))
                    if 'tháng' in str(loan_term).lower():
                        years = max(1, years // 12)  # Convert months to years
                    loan_term_str = f"{years} năm"
                except:
                    loan_term_str = "15 năm"  # Default
        
        # Calculate birth year from age if needed
        birth_year = conversation_data.get('birthYear')
        if not birth_year and conversation_data.get('age'):
            current_year = datetime.now().year
            birth_year = current_year - int(conversation_data['age'])
        elif not birth_year:
            birth_year = 1990  # Default
        
        # Build complete payload matching API structure exactly
        payload = {
            # Core loan info (required)
            "applicationId": application_id,
            "loanAmount": int(conversation_data.get('loanAmount', 0)),
            "loanType": conversation_data.get('loanType', 'Thế chấp'),
            "loanTerm": loan_term_str,
            "loanPurpose": conversation_data.get('loanPurpose', 'Mua nhà'),
            
            # Personal info (required for API)
            "fullName": conversation_data.get('fullName', ''),
            "phoneNumber": conversation_data.get('phoneNumber', ''),
            "phoneCountryCode": conversation_data.get('phoneCountryCode', '+84'),
            "birthYear": int(birth_year),
            "gender": conversation_data.get('gender', 'Nam'),
            "maritalStatus": conversation_data.get('maritalStatus', 'Độc thân'),
            "dependents": int(conversation_data.get('dependents', 0)),
            "email": conversation_data.get('email', ''),
        }
        
        # Financial info (critical for assessment) - Handle currency properly without auto-conversion
        monthly_income_raw = conversation_data.get('monthlyIncome', 0)
        income_currency = conversation_data.get('currency') or conversation_data.get('incomeCurrency', 'VND')
        
        # DON'T auto-convert foreign currency - let DeepSeek handle confirmation
        if monthly_income_raw > 0:
            if income_currency.upper() in ['USD', 'EUR', 'JPY', 'GBP']:
                # Store foreign currency income with currency info for DeepSeek to handle
                print(f"💰 Foreign currency detected: {monthly_income_raw:,} {income_currency} - Needs confirmation")
                # Add currency info to payload for AI agent to ask confirmation
                payload['monthlyIncomeCurrency'] = income_currency.upper()
                payload['monthlyIncomeNeedsConfirmation'] = True
                # Store raw amount - assessment API will need to handle this
                monthly_income_vnd = int(monthly_income_raw)  # Store raw for now
            else:
                # VND or unknown currency, treat as VND
                monthly_income_vnd = int(monthly_income_raw)
        else:
            monthly_income_vnd = 0
        
        # Handle collateral data - Extract from complex object if needed
        collateral_info = ""
        collateral_value = 0
        collateral_type = conversation_data.get('collateralType', 'Bất động sản')
        
        # Check if collateral is a complex object (from AI extraction)
        collateral_obj = conversation_data.get('collateral')
        if collateral_obj and isinstance(collateral_obj, dict):
            # Extract details from collateral object to build description
            house_type = collateral_obj.get('type', 'house')
            address = collateral_obj.get('address', '')
            area = collateral_obj.get('area', 0)
            floors = collateral_obj.get('floors', 0)
            width = collateral_obj.get('width', 0)
            
            # Build collateral info string - NO automatic valuation
            if house_type == 'house' and address:
                collateral_info = f"Nhà {floors} tầng tại {address}, diện tích {area}m², mặt tiền {width}m"
                print(f"🏠 Collateral info extracted: {collateral_info}")
            else:
                collateral_info = str(collateral_obj)
            
            # collateralValue MUST be provided by user, not auto-calculated
            collateral_value = int(conversation_data.get('collateralValue', 0))
            if collateral_value == 0:
                print(f"⚠️ Collateral value missing - DeepSeek should ask user for valuation")
        else:
            # Use simple fields as provided by user
            collateral_info = conversation_data.get('collateralInfo', '')
            collateral_value = int(conversation_data.get('collateralValue', 0))
        
        # Add financial and collateral data to payload
        payload.update({
            # Financial info (critical for assessment)
            "monthlyIncome": monthly_income_vnd,
            "primaryIncomeSource": conversation_data.get('primaryIncomeSource', 'Lương'),
            "companyName": conversation_data.get('companyName', ''),
            "jobTitle": conversation_data.get('jobTitle', ''),
            "workExperience": int(conversation_data.get('workExperience', 0)),
            "otherIncomeAmount": int(conversation_data.get('otherIncomeAmount', 0)),
            "bankName": conversation_data.get('bankName', ''),
            "totalAssets": int(conversation_data.get('totalAssets', 0)),
            "liquidAssets": int(conversation_data.get('liquidAssets', 0)),
            
            # Debt info (critical for DTI calculation)
            "hasExistingDebt": bool(conversation_data.get('hasExistingDebt', False)),
            "totalDebtAmount": int(conversation_data.get('totalDebtAmount', 0)),
            "monthlyDebtPayment": int(conversation_data.get('monthlyDebtPayment', 0)),
            "cicCreditScoreGroup": conversation_data.get('cicCreditScoreGroup', '1'),
            
            # Collateral info (for LTV calculation)
            "collateralType": collateral_type,
            "collateralInfo": collateral_info,
            "collateralValue": collateral_value,
            "hasCollateralImage": bool(conversation_data.get('collateralImage', False)),
            
            # Backend config (matches API default)
            "interestRate": float(conversation_data.get('interestRate', 8.5))
        })
        
        # Add existing loans if available (for detailed debt analysis)
        existing_loans = conversation_data.get('existingLoans', [])
        if existing_loans and isinstance(existing_loans, list):
            payload['existingLoans'] = existing_loans
        
        # Add other income details if available
        if conversation_data.get('otherIncome'):
            payload['otherIncome'] = conversation_data['otherIncome']
            
        # Add credit history if available
        if conversation_data.get('creditHistory'):
            payload['creditHistory'] = conversation_data['creditHistory']
        
        return payload
    
    def _parse_loan_term_to_months(self, loan_term_str) -> int:
        """
        Parse loan term string to months
        Examples: "5 năm" -> 60, "12 tháng" -> 12
        """
        import re
        
        # Handle if already a number (months)
        if isinstance(loan_term_str, (int, float)):
            return int(loan_term_str)
        
        if not loan_term_str:
            return 12  # Default 1 year
        
        # Convert to string and process
        loan_term_str = str(loan_term_str).lower()
        
        # Parse years
        year_match = re.search(r"(\d+)\s*năm", loan_term_str)
        if year_match:
            years = int(year_match.group(1))
            return years * 12
        
        # Parse months
        month_match = re.search(r"(\d+)\s*tháng", loan_term_str)
        if month_match:
            return int(month_match.group(1))
        
        # Try to parse just number (assume months)
        number_match = re.search(r"(\d+)", loan_term_str)
        if number_match:
            number = int(number_match.group(1))
            # If number > 30, assume it's months, otherwise years
            return number if number > 30 else number * 12
        
        return 12  # Default
    
    def generate_step_transition(self, from_step: str, to_step: str, extracted_fields: Dict[str, Any]) -> str:
        """
        Generate transition message between steps
        """
        transitions = {
            ("5.1", "5.2"): "Vui lòng cung cấp thêm chi tiết về các khoản nợ hiện tại.",
            ("5.1", "6"): "Cảm ơn! Không có nợ hiện tại sẽ giúp hồ sơ vay của bạn được đánh giá tốt hơn. Hãy xác nhận lại toàn bộ thông tin.",
            ("5.2", "6"): "Cảm ơn thông tin về tình hình nợ. Bây giờ hãy xem lại toàn bộ thông tin hồ sơ.",
            ("4.3", "5.1"): "Thông tin tài chính đã đầy đủ. Câu hỏi cuối cùng về tình trạng nợ hiện tại.",
            ("3.2", "4.1"): "Cảm ơn thông tin về tài sản đảm bảo. Tiếp theo là thông tin về thu nhập của bạn.",
            ("2.2", "3.1"): "Thông tin cá nhân đã hoàn tất. Bây giờ về tài sản đảm bảo cho khoản vay."
        }
        
        key = (from_step, to_step)
        if key in transitions:
            return transitions[key]
        
        # Default transition
        return f"Chuyển sang bước {to_step}..."
    
    def validate_step_6_data(self, extracted_fields: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Validate all collected data before assessment
        
        Returns:
            Dict with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        # Required fields check
        required_fields = [
            "loanAmount", "loanTerm", "loanPurpose", "loanType",
            "fullName", "phoneNumber", "birthYear",
            "monthlyIncome", "primaryIncomeSource",
            "hasExistingDebt"
        ]
        
        for field in required_fields:
            if field not in extracted_fields or not extracted_fields[field]:
                errors.append(f"Thiếu thông tin bắt buộc: {FIELD_DISPLAY_NAMES.get(field, field)}")
        
        # Validate loan amount vs income
        if "loanAmount" in extracted_fields and "monthlyIncome" in extracted_fields:
            loan_amount = float(extracted_fields["loanAmount"])
            monthly_income = float(extracted_fields["monthlyIncome"])
            
            if monthly_income > 0:
                debt_ratio = loan_amount / (monthly_income * 12)
                if debt_ratio > 10:
                    warnings.append("Tỷ lệ vay/thu nhập rất cao, có thể ảnh hưởng đến khả năng duyệt")
        
        # Validate collateral for secured loans
        if extracted_fields.get("loanType") == "Thế chấp":
            if not extracted_fields.get("collateralType") or not extracted_fields.get("collateralValue"):
                errors.append("Vay thế chấp cần có thông tin tài sản đảm bảo")
        
        return {"errors": errors, "warnings": warnings}
    
    def generate_validation_error_message(self, validation_result: Dict[str, List[str]]) -> str:
        """
        Generate error message for validation failures
        """
        message = "⚠️ **CẦN BỔ SUNG THÔNG TIN**\n\n"
        
        if validation_result["errors"]:
            message += "**Lỗi cần sửa:**\n"
            for error in validation_result["errors"]:
                message += f"• {error}\n"
        
        if validation_result["warnings"]:
            message += "\n**Cảnh báo:**\n"
            for warning in validation_result["warnings"]:
                message += f"• {warning}\n"
        
        message += "\nVui lòng bổ sung thông tin còn thiếu hoặc liên hệ hỗ trợ."
        
        return message
    def generate_step_7_assessment_result(self, assessment_result: Dict[str, Any]) -> str:
        """
        Generate Step 7 assessment result display
        """
        try:
            if not assessment_result.get("success", False):
                # Error case
                error_template = STEP_7_TEMPLATES["assessment_error"][0]
                return error_template.format(
                    error_code=assessment_result.get("error", "UNKNOWN_ERROR")
                )
            
            # Success case
            template = STEP_7_TEMPLATES["assessment_success"][0]
            
            # Status mapping
            status_emoji = {
                "APPROVED": "✅",
                "CONDITIONAL": "⚠️", 
                "REJECTED": "❌"
            }
            
            status_text = {
                "APPROVED": "CHẤP THUẬN",
                "CONDITIONAL": "CHẤP THUẬN CÓ ĐIỀU KIỆN",
                "REJECTED": "TỪ CHỐI"
            }
            
            # Credit rating mapping
            credit_rating_map = {
                (750, 850): "Xuất sắc",
                (700, 749): "Tốt",
                (650, 699): "Khá",
                (600, 649): "Trung bình",
                (300, 599): "Yếu"
            }
            
            credit_score = assessment_result.get("creditScore", 0)
            credit_rating = "N/A"
            for (min_score, max_score), rating in credit_rating_map.items():
                if min_score <= credit_score <= max_score:
                    credit_rating = rating
                    break
            
            # DTI assessment
            dti_ratio = assessment_result.get("debtToIncome", 0) * 100
            if dti_ratio <= 40:
                dti_assessment = "Tốt"
            elif dti_ratio <= 50:
                dti_assessment = "Chấp nhận được"
            else:
                dti_assessment = "Cao"
            
            # LTV assessment  
            ltv_ratio = assessment_result.get("loanToValue", 0) * 100
            if ltv_ratio <= 70:
                ltv_assessment = "An toàn"
            elif ltv_ratio <= 80:
                ltv_assessment = "Chấp nhận được"
            else:
                ltv_assessment = "Rủi ro cao"
            
            # Build conditions section
            conditions_section = ""
            if assessment_result.get("conditions"):
                conditions_section = "\n⚠️ **YÊU CẦU BỔ SUNG:**"
                for condition in assessment_result["conditions"]:
                    conditions_section += f"\n• {condition}"
            
            # Build reasoning section
            reasoning_section = ""
            if assessment_result.get("reasoning"):
                reasoning_section = f"\n💡 **NHẬN XÉT:**\n{assessment_result['reasoning']}"
            
            # Format template
            return template.format(
                status_emoji=status_emoji.get(assessment_result.get("status"), "📋"),
                status=status_text.get(assessment_result.get("status"), assessment_result.get("status", "UNKNOWN")),
                creditScore=credit_score,
                creditRating=credit_rating,
                dtiRatio=f"{dti_ratio:.0f}",
                dtiAssessment=dti_assessment,
                ltvRatio=f"{ltv_ratio:.0f}",
                ltvAssessment=ltv_assessment,
                confidence=f"{assessment_result.get('confidence', 0)*100:.0f}",
                approvedAmount=int(assessment_result.get("approvedAmount", 0)),
                interestRate=assessment_result.get("interestRate", 0),
                loanTerm=assessment_result.get("loanTerm", "N/A"),
                monthlyPayment=int(assessment_result.get("monthlyPayment", 0)),
                conditions_section=conditions_section,
                reasoning_section=reasoning_section,
                applicationId=assessment_result.get("applicationId", "N/A")
            )
            
        except Exception as e:
            print(f"❌ Error generating Step 7 result: {e}")
            error_template = STEP_7_TEMPLATES["assessment_error"][1]
            return error_template.format(error_message=str(e))
    
    def parse_step_6_edit_command(self, user_message: str) -> Dict[str, Any]:
        """
        Parse Step 6 edit commands like "Sửa thu nhập: 35 triệu"
        """
        import re
        
        # Pattern for edit commands
        edit_pattern = r"sửa\s+([^:]+):\s*(.+)"
        match = re.search(edit_pattern, user_message.lower().strip())
        
        if not match:
            return {"is_edit": False}
        
        field_name = match.group(1).strip()
        new_value = match.group(2).strip()
        
        # Map Vietnamese field names to actual field names
        field_mapping = {
            "thu nhập": "monthlyIncome",
            "lương": "monthlyIncome", 
            "tên": "fullName",
            "họ tên": "fullName",
            "tài sản": "collateralValue",
            "giá trị tài sản": "collateralValue",
            "nợ": "totalDebtAmount",
            "dư nợ": "totalDebtAmount",
            "trả nợ": "monthlyDebtPayment",
            "số tiền vay": "loanAmount",
            "công ty": "companyName",
            "chức vụ": "jobTitle",
            "email": "email",
            "điện thoại": "phoneNumber",
            "sdt": "phoneNumber",
            "năm sinh": "birthYear",
            "tuổi": "birthYear"
        }
        
        actual_field = field_mapping.get(field_name)
        if not actual_field:
            return {"is_edit": False, "error": f"Không nhận diện được trường '{field_name}'"}
        
        # Parse value based on field type
        try:
            if actual_field in ["loanAmount", "monthlyIncome", "collateralValue", "totalDebtAmount", "monthlyDebtPayment", "otherIncomeAmount"]:
                # Parse money values
                parsed_value = self._parse_money_value(new_value)
            elif actual_field == "birthYear":
                # Parse birth year
                parsed_value = self._parse_birth_year(new_value)
            else:
                # String fields
                parsed_value = new_value
            
            return {
                "is_edit": True,
                "field": actual_field,
                "value": parsed_value,
                "original_input": user_message
            }
            
        except Exception as e:
            return {"is_edit": False, "error": f"Không thể chuyển đổi giá trị '{new_value}': {str(e)}"}
    
    def _parse_money_value(self, value_str: str) -> int:
        """Parse money value from Vietnamese text"""
        import re
        
        value_str = value_str.lower().replace(",", "").replace(".", "")
        
        # Handle "triệu", "tỷ", etc.
        if "tỷ" in value_str:
            number = re.search(r"(\d+(?:\.\d+)?)", value_str)
            if number:
                return int(float(number.group(1)) * 1_000_000_000)
        elif "triệu" in value_str:
            number = re.search(r"(\d+(?:\.\d+)?)", value_str)
            if number:
                return int(float(number.group(1)) * 1_000_000)
        else:
            # Direct number
            number = re.search(r"(\d+)", value_str)
            if number:
                return int(number.group(1))
        
        raise ValueError(f"Cannot parse money value: {value_str}")
    
    def _parse_birth_year(self, value_str: str) -> int:
        """Parse birth year from Vietnamese text"""
        import re
        from datetime import datetime
        
        current_year = datetime.now().year
        
        if "tuổi" in value_str.lower():
            # Parse age
            age_match = re.search(r"(\d+)", value_str)
            if age_match:
                age = int(age_match.group(1))
                return current_year - age
        else:
            # Parse year directly
            year_match = re.search(r"(\d{4})", value_str)
            if year_match:
                return int(year_match.group(1))
        
        raise ValueError(f"Cannot parse birth year: {value_str}")
