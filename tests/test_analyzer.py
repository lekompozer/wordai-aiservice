import sys
import os

# Add src to path để import được
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.real_estate_analyzer import analyze_real_estate_query, get_analysis_dict

def test_analyzer():
    """Test the analyzer with sample questions"""
    test_questions = [
        "Định giá căn hộ 2PN tại Vinhomes Grand Park quận 9 TPHCM?",
        "Giá nhà phố 125m2 đường Thích Thiện Chiếu Bà Rịa Vũng Tàu bao nhiêu?",
        "Căn hộ 3PN Masteri Thảo Điền quận 2 giá thế nào?",
        "Biệt thự 200m2 Thủ Đức có giá khoảng bao nhiêu?",
        "Shophouse 5x20 mặt tiền đường Nguyễn Văn Linh quận 7 bán giá bao nhiêu?",
        "Đất nền 100m2 dự án Eco Green Sài Gòn giá ra sao?"
    ]
    
    print("🏠 TESTING REAL ESTATE ANALYZER")
    print("=" * 80)
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*80}")
        print(f"🔍 TEST {i}: {question}")
        print('='*80)
        
        try:
            analysis = analyze_real_estate_query(question)
            
            print(f"✅ RESULTS:")
            print(f"   📝 Search Query: {analysis.search_query}")
            print(f"   🏠 Property Type: {analysis.property_type}")
            print(f"   🏗️ Project: {analysis.project_name}")
            print(f"   🛏️ Bedrooms: {analysis.bedrooms}")
            print(f"   📐 Area: {analysis.dientich}")
            print(f"   🌍 Province: {analysis.location.province}")
            print(f"   🏘️ District: {analysis.location.district}")
            print(f"   🛣️ Street: {analysis.location.street}")
            print(f"   💰 Price Intent: {analysis.has_price_intent}")
            print(f"   ❓ Question Pattern: {analysis.has_question_pattern}")
            print(f"   📊 Confidence: {analysis.confidence:.2f} ({analysis.confidence*100:.0f}%)")
            
            if analysis.location.full:
                print(f"   📍 All Locations: {', '.join(analysis.location.full)}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

def test_specific_question():
    """Test with a specific question"""
    question = input("\n🔍 Enter your real estate question: ")
    
    print(f"\n{'='*80}")
    print(f"🔍 ANALYZING: {question}")
    print('='*80)
    
    try:
        analysis = analyze_real_estate_query(question)
        
        # Print detailed results
        print(f"\n✅ DETAILED ANALYSIS:")
        print(f"   Original Question: {analysis.original_question}")
        print(f"   Search Query: {analysis.search_query}")
        print(f"   Confidence: {analysis.confidence:.2f}")
        print(f"   Price Intent: {analysis.has_price_intent}")
        print(f"   Question Pattern: {analysis.has_question_pattern}")
        print(f"   Property Type: {analysis.property_type}")
        print(f"   Project Name: {analysis.project_name}")
        print(f"   Bedrooms: {analysis.bedrooms}")
        print(f"   Area Size: {analysis.dientich}")
        print(f"   Province: {analysis.location.province}")
        print(f"   District: {analysis.location.district}")
        print(f"   Street: {analysis.location.street}")
        print(f"   Area: {analysis.location.area}")
        print(f"   All Locations: {analysis.location.full}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def test_as_dict():
    """Test returning as dictionary"""
    question = "Định giá căn hộ 2PN tại Vinhomes Grand Park quận 9 TPHCM?"
    
    print(f"\n{'='*80}")
    print(f"🔍 TESTING DICTIONARY OUTPUT")
    print('='*80)
    
    try:
        result_dict = get_analysis_dict(question)
        
        import json
        print("📋 RESULT AS JSON:")
        print(json.dumps(result_dict, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🏠 REAL ESTATE ANALYZER TEST SUITE")
    print("=" * 50)
    
    while True:
        print("\nChoose test option:")
        print("1. Test with predefined questions")
        print("2. Test with custom question")
        print("3. Test dictionary output")
        print("4. Exit")
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            test_analyzer()
        elif choice == "2":
            test_specific_question()
        elif choice == "3":
            test_as_dict()
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-4.")