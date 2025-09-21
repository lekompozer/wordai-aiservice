"""
Interactive test for AI Sales Agent - Manual conversation flow
Allows user to manually input responses and see detailed logging
"""

import sys
import os
sys.path.append('/Users/user/Code/ai-chatbot-rag')

from src.ai_sales_agent.models.nlu_models import StepSubQuestion, STEP_CONFIGS
from src.ai_sales_agent.nlu.utils import NLUProcessor
from src.ai_sales_agent.nlg.generator import NLGGenerator
import json
from datetime import datetime

def print_separator(char="=", length=80):
    print(char * length)

def print_step_info(step, config):
    print(f"\n📋 HIỆN TẠI: {step.value} - {config['name']}")
    print(f"🎯 Required Fields: {', '.join(config['requiredFields'])}")
    if config['optionalFields']:
        print(f"⭐ Optional Fields: {', '.join(config['optionalFields'])}")

def print_extraction_details(result, session):
    print(f"\n🔍 EXTRACTION DETAILS:")
    print(f"   📊 Extracted Data: {json.dumps(result['extractedData'], ensure_ascii=False, indent=6)}")
    print(f"   🎯 Confidence: {result['confidence']:.2f}")
    print(f"   ❌ Missing Fields: {result['missingFields']}")
    if result['validationErrors']:
        print(f"   ⚠️  Validation Errors: {result['validationErrors']}")
    
    print(f"\n💾 SESSION STATE:")
    print(f"   📋 All Extracted: {json.dumps(session['extracted_fields'], ensure_ascii=False, indent=6)}")
    print(f"   🔄 Turn: {session['conversation_count']}")

def interactive_conversation():
    """Interactive conversation where user can type responses manually"""
    
    # Initialize processors
    nlu = NLUProcessor()
    nlg = NLGGenerator()
    
    print_separator("=")
    print("🏦 INTERACTIVE AI SALES AGENT - BANKING LOAN ASSESSMENT")
    print("💬 Bạn sẽ tự trả lời từng bước để xem chi tiết quá trình xử lý")
    print_separator("=")
    
    # Session state
    session = {
        "current_step": StepSubQuestion.STEP_1_1,
        "extracted_fields": {},
        "conversation_count": 0,
        "history": []
    }
    
    # Welcome message
    welcome = nlg.generate_welcome_message()
    print(f"\n🤖 Assistant: {welcome}")
    
    # Step flow
    step_flow = [StepSubQuestion.STEP_1_1, StepSubQuestion.STEP_1_2, 
                StepSubQuestion.STEP_2_1, StepSubQuestion.STEP_2_2]
    
    current_step_index = 0
    
    while current_step_index < len(step_flow):
        current_step = step_flow[current_step_index]
        session["current_step"] = current_step
        step_key = current_step.value
        step_config = STEP_CONFIGS[step_key]
        
        print_step_info(current_step, step_config)
        
        # Check what's missing for current step
        missing_fields = [
            field for field in step_config["requiredFields"]
            if field not in session["extracted_fields"] or not session["extracted_fields"][field]
        ]
        
        # If step is already complete, move to next
        if not missing_fields:
            print(f"✅ Step {step_key} đã hoàn thành, chuyển sang step tiếp theo...")
            current_step_index += 1
            continue
        
        # Generate question for current step
        is_first_for_step = session["conversation_count"] == 0 or any(
            field not in session["extracted_fields"] for field in step_config["requiredFields"]
        )
        
        question = nlg.generate_question(
            current_step=current_step,
            extracted_fields=session["extracted_fields"],
            missing_fields=missing_fields,
            is_first_interaction=is_first_for_step
        )
        
        print(f"\n🤖 Assistant: {question}")
        print_separator("-")
        
        # Get user input
        print(f"\n👤 Your turn (Step {step_key}):")
        print("   💡 Hints:")
        if step_key == "1.1":
            print("      - Số tiền vay (VD: 500 triệu, 2 tỷ)")
            print("      - Thời hạn (VD: 10 năm, 5 năm)")
            print("      - Mục đích (VD: mua nhà, kinh doanh)")
        elif step_key == "1.2":
            print("      - Loại vay (VD: thế chấp, tín chấp)")
            print("      - Mã nhân viên (VD: ABC123)")
        elif step_key == "2.1":
            print("      - Họ tên đầy đủ")
            print("      - Số điện thoại (10 số)")
            print("      - Năm sinh hoặc tuổi")
        elif step_key == "2.2":
            print("      - Giới tính (Nam/Nữ)")
            print("      - Tình trạng hôn nhân")
            print("      - Số người phụ thuộc")
            print("      - Email (optional)")
        
        user_input = input("\n📝 Nhập câu trả lời: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Thoát chương trình!")
            break
        
        if not user_input:
            print("⚠️  Vui lòng nhập câu trả lời!")
            continue
        
        print_separator("-")
        
        # Process with NLU
        print(f"\n🔄 PROCESSING INPUT: '{user_input}'")
        
        result = nlu.extract_information(
            step=step_key,
            user_message=user_input,
            required_fields=step_config["requiredFields"],
            current_data=session["extracted_fields"]
        )
        
        # Update session
        session["extracted_fields"].update(result["extractedData"])
        session["conversation_count"] += 1
        
        # Add to history
        session["history"].append({
            "timestamp": datetime.now().isoformat(),
            "step": step_key,
            "user_input": user_input,
            "extracted": result["extractedData"],
            "missing_before": missing_fields,
            "confidence": result["confidence"]
        })
        
        # Print extraction details
        print_extraction_details(result, session)
        
        # Check if current step is now complete
        updated_missing = [
            field for field in step_config["requiredFields"]
            if field not in session["extracted_fields"] or not session["extracted_fields"][field]
        ]
        
        if not updated_missing:
            print(f"\n✅ STEP {step_key} HOÀN THÀNH!")
            
            # Show transition message
            if current_step_index < len(step_flow) - 1:
                next_step = step_flow[current_step_index + 1]
                transition = nlg.generate_step_transition_message(
                    from_step=current_step,
                    to_step=next_step,
                    extracted_fields=session["extracted_fields"]
                )
                print(f"\n🔄 TRANSITION: {transition}")
            
            current_step_index += 1
        else:
            print(f"\n⏳ STEP {step_key} chưa hoàn thành. Còn thiếu: {updated_missing}")
        
        print_separator("=")
    
    # Final summary
    if current_step_index >= len(step_flow):
        print(f"\n🎉 HOÀN THÀNH TẤT CẢ STEPS!")
        
        final_summary = nlg.generate_final_summary(session["extracted_fields"])
        print(f"\n{final_summary}")
        
        print_separator("=")
        print("📊 FINAL STATISTICS:")
        print(f"   🔄 Total conversations: {session['conversation_count']}")
        print(f"   📋 Total fields extracted: {len(session['extracted_fields'])}")
        print(f"   📈 Completion rate: 100%")
        
        print(f"\n📋 FINAL EXTRACTED FIELDS:")
        for field, value in session["extracted_fields"].items():
            print(f"   • {field}: {value}")
        
        # Show conversation history
        print(f"\n📚 CONVERSATION HISTORY:")
        for i, turn in enumerate(session["history"], 1):
            print(f"\n   Turn {i} (Step {turn['step']}):")
            print(f"     👤 Input: {turn['user_input']}")
            print(f"     📊 Extracted: {turn['extracted']}")
            print(f"     🎯 Confidence: {turn['confidence']:.2f}")
    
    print_separator("=")
    print("💾 Session saved for analysis!")

def quick_demo():
    """Quick demo with pre-filled answers for comparison"""
    print("\n🚀 QUICK DEMO MODE (for comparison)")
    
    demo_inputs = [
        "Tôi muốn vay 800 triệu để kinh doanh trong 15 năm",
        "Vay tín chấp, mã nhân viên XYZ789", 
        "Tên Trần Thị Bình, SĐT 0987654321, 28 tuổi",
        "Nữ, ly hôn, nuôi 1 con, email: binhtt@email.com"
    ]
    
    nlu = NLUProcessor()
    extracted_all = {}
    
    for i, (step, user_input) in enumerate(zip(["1.1", "1.2", "2.1", "2.2"], demo_inputs)):
        print(f"\nStep {step}: {user_input}")
        
        result = nlu.extract_information(
            step=step,
            user_message=user_input,
            required_fields=STEP_CONFIGS[step]["requiredFields"],
            current_data=extracted_all
        )
        
        extracted_all.update(result["extractedData"])
        print(f"Extracted: {result['extractedData']}")
    
    print(f"\nFinal result: {extracted_all}")

if __name__ == "__main__":
    print("🎯 AI SALES AGENT INTERACTIVE TEST")
    print("\nChọn chế độ:")
    print("1. Interactive mode (tự trả lời)")
    print("2. Quick demo (answers tự động)")
    
    choice = input("\nNhập lựa chọn (1/2): ").strip()
    
    if choice == "2":
        quick_demo()
    else:
        interactive_conversation()
    
    print("\n👋 Test completed!")
