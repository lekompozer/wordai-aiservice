"""
Flexible Assessment Readiness Checker
Đánh giá khả năng thẩm định dựa trên dữ liệu hiện có thay vì bắt buộc step cứng nhắc
"""

from typing import Dict, Any, List, Tuple
from enum import Enum

class AssessmentReadiness(Enum):
    """Mức độ sẵn sàng thẩm định"""
    READY = "ready"                    # Đủ dữ liệu core, có thể thẩm định ngay
    NEARLY_READY = "nearly_ready"      # Thiếu 1-2 field quan trọng
    NEED_MORE_INFO = "need_more_info"  # Thiếu nhiều thông tin cơ bản
    INSUFFICIENT = "insufficient"       # Quá ít thông tin

class FlexibleAssessmentChecker:
    """
    Kiểm tra tính sẵn sàng thẩm định một cách linh hoạt
    Thu thập data theo priority và conditional logic
    """
    
    def __init__(self):
        # Định nghĩa độ ưu tiên của các field theo API requirements
        self.field_priorities = {
            # CRITICAL - Bắt buộc cho thẩm định cơ bản
            "loanAmount": 100,          # Required
            "loanType": 95,             # Required - determines collateral flow
            "loanTerm": 90,             # Required
            "fullName": 85,             # Required
            "phoneNumber": 80,          # Required
            "monthlyIncome": 95,        # Required for DTI calculation
            "birthYear": 85,            # Required for age verification
            
            # CRITICAL FOR MORTGAGE ONLY (conditional) - Enhanced priorities
            "collateralType": 95,       # CRITICAL if loanType = "Thế chấp" - MUST know what asset type
            "collateralValue": 95,      # CRITICAL if loanType = "Thế chấp" - MUST have monetary value 
            "collateralInfo": 90,       # CRITICAL if loanType = "Thế chấp" - MUST have detailed info
            
            # IMPORTANT - Ảnh hưởng nhiều đến kết quả thẩm định
            "primaryIncomeSource": 80,
            "hasExistingDebt": 75,     # Important for DTI
            "totalDebtAmount": 70,      # If hasExistingDebt = true
            "monthlyDebtPayment": 70,   # If hasExistingDebt = true
            "cicCreditScoreGroup": 75,
            "gender": 65,
            "maritalStatus": 60,
            "dependents": 55,
            
            # HELPFUL - Cải thiện độ chính xác
            "companyName": 50,
            "jobTitle": 45,
            "workExperience": 40,
            "loanPurpose": 45,
            "otherIncomeAmount": 35,
            "totalAssets": 30,
            "bankName": 25,
            
            # OPTIONAL - Bonus information
            "email": 20,
            "salesAgentCode": 15,
            "collateralImage": 10,
            "liquidAssets": 15,
            "existingLoans": 10
        }
        
        # Ngưỡng điểm để đánh giá readiness (adjusted for new scoring)
        self.readiness_thresholds = {
            AssessmentReadiness.READY: 650,         # >= 650 điểm
            AssessmentReadiness.NEARLY_READY: 500,  # 500-649 điểm  
            AssessmentReadiness.NEED_MORE_INFO: 350, # 350-499 điểm
            AssessmentReadiness.INSUFFICIENT: 0      # < 350 điểm
        }
        
        # Question templates for natural conversation
        self.question_templates = {
            # Step 1: Loan basic info (2-3 fields per question)
            "loan_basic": [
                "Anh/chị cần vay bao nhiêu tiền, trong thời gian bao lâu và để làm gì ạ?",
                "Anh/chị muốn vay theo hình thức nào - có tài sản thế chấp hay vay tín chấp?"
            ],
            
            # Step 2: Personal info (2-3 fields per question)
            "personal_info": [
                "Cho em xin họ tên đầy đủ, số điện thoại và năm sinh của anh/chị?",
                "Anh/chị cho biết giới tính, tình trạng hôn nhân và số người phụ thuộc?"
            ],
            
            # Step 3: Income info (2-3 fields per question)
            "income_info": [
                "Thu nhập hàng tháng của anh/chị là bao nhiêu và từ nguồn nào (lương/kinh doanh)?",
                "Anh/chị làm việc ở đâu, chức vụ gì và đã làm được bao lâu?"
            ],
            
            # Step 4: Debt info (conditional)
            "debt_info": [
                "Anh/chị có đang vay nợ ở ngân hàng hoặc tổ chức tín dụng nào không?",
                "Tổng dư nợ hiện tại và số tiền phải trả hàng tháng là bao nhiêu?"
            ],
            
            # Step 5: Collateral info (conditional - only for mortgage)
            "collateral_info": [
                "Tài sản thế chấp là gì và giá trị ước tính bao nhiêu?",
                "Anh/chị mô tả chi tiết về tài sản (địa chỉ, diện tích, tình trạng pháp lý)?"
            ]
        }
    
    def calculate_data_score(self, conversation_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        Tính điểm dữ liệu hiện có với conditional logic
        """
        total_score = 0
        analysis = {
            "present_fields": {},
            "missing_critical": [],
            "missing_important": [],
            "bonus_fields": []
        }
        
        # Get loan type to apply conditional logic
        loan_type = conversation_data.get('loanType', '').lower()
        is_mortgage = 'thế chấp' in loan_type or 'the chap' in loan_type
        
        # Check if has existing debt
        has_debt = conversation_data.get('hasExistingDebt', False)
        
        for field, priority in self.field_priorities.items():
            # Skip collateral fields if not mortgage loan
            if not is_mortgage and field in ['collateralType', 'collateralValue', 'collateralInfo']:
                continue
                
            # Skip debt detail fields if no existing debt
            if not has_debt and field in ['totalDebtAmount', 'monthlyDebtPayment']:
                continue
            
            # Check if field has value
            if field in conversation_data and conversation_data[field] not in [None, "", 0]:
                # Special handling for 0 values
                if field == "dependents" and conversation_data[field] == 0:
                    total_score += priority
                    analysis["present_fields"][field] = priority
                elif field != "dependents":
                    total_score += priority
                    analysis["present_fields"][field] = priority
                
                # Categorize bonus fields
                if priority < 30:
                    analysis["bonus_fields"].append(field)
            else:
                # Categorize missing fields
                if priority >= 75:  # Critical
                    analysis["missing_critical"].append(field)
                elif priority >= 50:  # Important
                    analysis["missing_important"].append(field)
        
        return total_score, analysis
    
    def get_next_smart_question(self, conversation_data: Dict[str, Any], message_count: int) -> Dict[str, Any]:
        """
        Get next question based on what's missing and message count
        Max 10 questions, focus on 5-7 for critical data
        """
        _, analysis = self.calculate_data_score(conversation_data)
        
        # Check loan type for conditional flow
        loan_type = conversation_data.get('loanType', '').lower()
        is_mortgage = 'thế chấp' in loan_type or 'the chap' in loan_type
        
        # PRIORITY 1: Basic loan info (if missing)
        if not conversation_data.get('loanAmount') or not conversation_data.get('loanTerm'):
            return {
                "step": "loan_basic",
                "question": "Anh/chị cần vay bao nhiêu tiền và trong thời gian bao lâu ạ?",
                "expecting": ["loanAmount", "loanTerm", "loanPurpose"]
            }
        
        # PRIORITY 2: Loan type (CRITICAL - ask early)
        if not conversation_data.get('loanType'):
            return {
                "step": "loan_type", 
                "question": "Anh/chị muốn vay theo hình thức nào - vay tín chấp (không cần tài sản) hay vay thế chấp (có tài sản đảm bảo)?",
                "expecting": ["loanType"]
            }
            
        # PRIORITY 3: Personal info with validation
        if not conversation_data.get('fullName') or not conversation_data.get('phoneNumber') or not conversation_data.get('birthYear'):
            missing_personal = []
            if not conversation_data.get('fullName'):
                missing_personal.append("họ tên")
            if not conversation_data.get('phoneNumber'):
                missing_personal.append("số điện thoại")
            if not conversation_data.get('birthYear'):
                missing_personal.append("năm sinh")
                
            return {
                "step": "personal_info",
                "question": f"Cho em xin {' và '.join(missing_personal)} của anh/chị?",
                "expecting": ["fullName", "phoneNumber", "birthYear"]
            }
            
        # Validate birth year and phone number
        birth_year = conversation_data.get('birthYear')
        if birth_year:
            current_year = 2025
            age = current_year - birth_year
            if age < 18 or age > 70:
                return {
                    "step": "birth_year_validation",
                    "question": f"Em thấy năm sinh {birth_year} (tương đương {age} tuổi). Anh/chị vui lòng xác nhận lại năm sinh chính xác để em kiểm tra điều kiện vay?",
                    "expecting": ["birthYear"]
                }
        
        phone_number = conversation_data.get('phoneNumber')
        if phone_number and len(str(phone_number).replace(' ', '').replace('-', '')) not in [10, 11]:
            return {
                "step": "phone_validation", 
                "question": f"Số điện thoại {phone_number} có vẻ chưa đúng. Anh/chị vui lòng cung cấp lại số điện thoại 10-11 số?",
                "expecting": ["phoneNumber"]
            }
            
        # PRIORITY 4: Income and work info combined  
        if not conversation_data.get('monthlyIncome') or not conversation_data.get('companyName'):
            missing_work = []
            if not conversation_data.get('monthlyIncome'):
                missing_work.append("thu nhập hàng tháng")
            if not conversation_data.get('companyName'):
                missing_work.append("công ty làm việc")
            if not conversation_data.get('jobTitle'):
                missing_work.append("chức vụ")
                
            return {
                "step": "income_work_info",
                "question": f"Anh/chị cho biết {' và '.join(missing_work)} hiện tại?",
                "expecting": ["monthlyIncome", "companyName", "jobTitle"]
            }
        
        # PRIORITY 5: CIC and credit info (important for unsecured loans)
        if not is_mortgage and not conversation_data.get('cicCreditScoreGroup') and message_count < 7:
            return {
                "step": "credit_check",
                "question": "Anh/chị có biết điểm tín dụng CIC của mình thuộc nhóm nào không (A, B, C)? Và hiện có đang vay nợ ở ngân hàng nào không?",
                "expecting": ["cicCreditScoreGroup", "hasExistingDebt", "bankName"]
            }
            
        # PRIORITY 6: Credit card and savings for unsecured loans
        if not is_mortgage and not conversation_data.get('hasCreditCard') and message_count < 8:
            return {
                "step": "banking_services",
                "question": "Anh/chị có đang sử dụng thẻ tín dụng hay có tài khoản tiết kiệm ở ngân hàng nào không?",
                "expecting": ["hasCreditCard", "hasSavingsAccount", "bankName"]
            }
        
        # Get loan amount for asset assessment
        loan_amount = conversation_data.get('loanAmount', 0)
        if isinstance(loan_amount, str):
            try:
                loan_amount = float(loan_amount.replace(',', '').replace('.', ''))
            except (ValueError, AttributeError):
                loan_amount = 0
        
        # PRIORITY 7: Asset information for mortgage loans or high amounts
        if (is_mortgage or loan_amount > 1000000000) and not conversation_data.get('hasProperty'):
            return {
                "step": "asset_info", 
                "question": "Để đánh giá khoản vay, anh/chị có thể chia sẻ thông tin về tài sản đang có như nhà đất, xe hơi, tiết kiệm không?",
                "expecting": ["hasProperty", "propertyValue", "hasCar", "savingsAmount"]
            }
            
        # PRIORITY 8: Debt and obligations (enhanced for all loan types)
        if not conversation_data.get('hasExistingDebt') and message_count < 8:
            debt_inquiry = "cho vay không tài sản" if not is_mortgage else "thế chấp"
            return {
                "step": "debt_check",
                "question": f"Hiện tại anh/chị có khoản nợ nào khác đang phải trả hàng tháng không? Điều này quan trọng để đánh giá khả năng thanh toán cho khoản {debt_inquiry}.",
                "expecting": ["hasExistingDebt", "monthlyDebtPayment", "currentDebt"]
            }
            
        if conversation_data.get('hasExistingDebt') and not conversation_data.get('totalDebtAmount'):
            return {
                "step": "debt_details",
                "question": "Anh/chị có thể cho biết tổng số nợ hiện tại và số tiền phải trả hàng tháng không?",
                "expecting": ["totalDebtAmount", "monthlyDebtPayment"]
            }

        # PRIORITY 9: Collateral info - MUST get all 3 pieces for mortgage loans  
        if is_mortgage and message_count < 10:
            # Check what collateral information is missing
            collateral_type = conversation_data.get('collateralType')
            collateral_info = conversation_data.get('collateralInfo') 
            collateral_value = conversation_data.get('collateralValue')
            
            # STEP 1: Ask for collateral type first
            if not collateral_type:
                return {
                    "step": "collateral_type",
                    "question": "Tài sản thế chấp của anh/chị là gì? (nhà đất, căn hộ, xe hơi, hay loại tài sản khác?)",
                    "expecting": ["collateralType"],
                    "required_for_mortgage": True
                }
            
            # STEP 2: Ask for detailed information about the collateral  
            if collateral_type and not collateral_info:
                if 'nhà' in collateral_type.lower() or 'căn hộ' in collateral_type.lower() or 'đất' in collateral_type.lower():
                    return {
                        "step": "collateral_property_details",
                        "question": f"Anh/chị cho biết thông tin chi tiết về {collateral_type}: địa chỉ, diện tích, tình trạng sổ đỏ/pháp lý? Có ảnh của tài sản không?",
                        "expecting": ["collateralInfo", "collateralImage"],
                        "required_for_mortgage": True
                    }
                elif 'xe' in collateral_type.lower():
                    return {
                        "step": "collateral_vehicle_details", 
                        "question": f"Anh/chị cho biết thông tin chi tiết về {collateral_type}: hãng xe, đời xe, biển số, tình trạng đăng ký? Có ảnh của xe không?",
                        "expecting": ["collateralInfo", "collateralImage"],
                        "required_for_mortgage": True
                    }
                else:
                    return {
                        "step": "collateral_general_details",
                        "question": f"Anh/chị mô tả chi tiết về {collateral_type}: tình trạng, vị trí, giấy tờ pháp lý? Có ảnh của tài sản không?",
                        "expecting": ["collateralInfo", "collateralImage"], 
                        "required_for_mortgage": True
                    }
                    
            # STEP 3: Ask for specific monetary value (CRITICAL)
            if collateral_type and collateral_info and not collateral_value:
                return {
                    "step": "collateral_value_required",
                    "question": f"Quan trọng nhất, anh/chị ước tính {collateral_type} này có giá trị bao nhiêu tiền? Em cần số tiền cụ thể để đánh giá khả năng cho vay thế chấp.",
                    "expecting": ["collateralValue"],
                    "required_for_mortgage": True,
                    "critical": True
                }
                
            # VALIDATION: Ensure collateral value is reasonable
            if collateral_value and isinstance(collateral_value, (int, float)) and collateral_value < 100000000:  # Less than 100M VND
                return {
                    "step": "collateral_value_validation",
                    "question": f"Anh/chị xác nhận tài sản {collateral_type} có giá trị {collateral_value:,} VNĐ? Giá trị này có hợp lý so với thực tế thị trường không?",
                    "expecting": ["collateralValue"],
                    "validation": True
                }
        
        # PRIORITY 10: Final completion check
        completeness = self.calculate_completeness(conversation_data, is_mortgage)
        if completeness >= 75 or message_count >= 8:  # Sufficient data for assessment
            return {
                "step": "assessment_ready",
                "question": "Cảm ơn anh/chị! Tôi đã có đủ thông tin để đánh giá. Anh/chị có muốn bổ sung thêm thông tin gì không?",
                "expecting": ["additional_info", "ready_for_assessment"]
            }
        else:
            # Ask for the most critical missing information
            missing = self.get_missing_critical_fields(conversation_data, is_mortgage)
            if missing:
                return {
                    "step": "critical_missing",
                    "question": f"Để hoàn tất đánh giá, tôi cần thêm thông tin về: {', '.join(missing)}. Anh/chị có thể chia sẻ không?",
                    "expecting": missing
                }
                
        # Default fallback
        return {
            "step": "general_followup",
            "question": "Anh/chị có thêm thông tin gì muốn chia sẻ để hỗ trợ đánh giá khoản vay không?",
            "expecting": ["additional_info"]
        }
    
    def assess_readiness(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced readiness assessment with message count consideration
        """
        score, analysis = self.calculate_data_score(conversation_data)
        max_possible_score = sum(self.field_priorities.values())
        completion_percentage = (score / max_possible_score) * 100
        
        # Count messages
        message_count = conversation_data.get('_message_count', 0)
        
        # Determine readiness level
        readiness = AssessmentReadiness.INSUFFICIENT
        for level, threshold in sorted(self.readiness_thresholds.items(), 
                                     key=lambda x: x[1], reverse=True):
            if score >= threshold:
                readiness = level
                break
        
        # Can proceed if READY or NEARLY_READY (or if asked 7+ questions)
        can_proceed = (
            readiness in [AssessmentReadiness.READY, AssessmentReadiness.NEARLY_READY] or
            (message_count >= 7 and score >= 450)
        )
        
        # Auto-ready if asked 5-7 questions and have critical fields
        auto_ready = (
            message_count >= 5 and 
            len(analysis["missing_critical"]) <= 2 and
            score >= 500
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(readiness, analysis, message_count)
        
        return {
            "readiness": readiness,
            "score": score,
            "max_possible_score": max_possible_score,
            "completion_percentage": completion_percentage,
            "can_proceed": can_proceed,
            "auto_ready": auto_ready,
            "recommendations": recommendations,
            "missing_critical": analysis["missing_critical"],
            "missing_important": analysis["missing_important"],
            "present_fields": list(analysis["present_fields"].keys()),
            "bonus_fields": analysis["bonus_fields"],
            "message_count": message_count
        }
    
    def _generate_recommendations(self, readiness: AssessmentReadiness, analysis: Dict[str, Any], message_count: int) -> List[str]:
        """Generate smart recommendations based on current state and message count"""
        recommendations = []
        
        if message_count >= 7:
            recommendations.append(f"✅ Đã hỏi {message_count} câu - Đủ để thẩm định!")
        
        if readiness == AssessmentReadiness.READY:
            recommendations.append("✅ Đủ dữ liệu để thẩm định với độ tin cậy cao!")
        elif readiness == AssessmentReadiness.NEARLY_READY:
            recommendations.append("⚡ Có thể thẩm định với độ tin cậy tốt.")
        elif message_count >= 5:
            recommendations.append("📊 Đã thu thập đủ thông tin cơ bản để thẩm định.")
        
        return recommendations
    
    def get_missing_critical_fields(self, conversation_data: Dict[str, Any], is_mortgage: bool = False) -> List[str]:
        """Get list of missing critical fields in Vietnamese for user feedback"""
        missing = []
        
        # Core critical fields for all loans
        critical_fields = {
            'fullName': 'họ tên',
            'phoneNumber': 'số điện thoại', 
            'birthYear': 'năm sinh',
            'monthlyIncome': 'thu nhập hàng tháng',
            'loanAmount': 'số tiền vay',
            'loanType': 'hình thức vay'
        }
        
        # Additional critical fields for mortgage - MUST have all 3 pieces
        if is_mortgage:
            critical_fields.update({
                'collateralType': 'loại tài sản thế chấp',
                'collateralInfo': 'thông tin chi tiết tài sản',
                'collateralValue': 'giá trị ước tính tài sản'
            })
        else:
            # Additional for unsecured loans
            critical_fields.update({
                'companyName': 'tên công ty',
                'cicCreditScoreGroup': 'nhóm tín dụng CIC'
            })
        
        for field, description in critical_fields.items():
            if not conversation_data.get(field):
                missing.append(description)
                
        return missing[:3]  # Return max 3 most important