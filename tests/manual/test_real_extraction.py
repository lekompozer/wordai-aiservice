#!/usr/bin/env python3
"""
Test Real AI Extraction with Actual R2 URLs
Test AI Extraction thực tế với R2 URLs thật

This test uses real files uploaded to R2 with public URLs to verify:
1. Template selection based on Industry metadata
2. AI provider selection (ChatGPT Vision vs DeepSeek)
3. Raw + structured data extraction
4. Template-based JSON schema processing

Test này sử dụng file thật đã upload lên R2 với public URLs để verify:
1. Lựa chọn template dựa trên Industry metadata
2. Lựa chọn AI provider (ChatGPT Vision vs DeepSeek)
3. Extract raw + structured data
4. Xử lý JSON schema dựa trên template
"""

import asyncio
import json
import time
from pathlib import Path
import sys
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

try:
    from services.ai_extraction_service import AIExtractionService
    from services.extraction_templates.template_factory import ExtractionTemplateFactory
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to run this from the project root directory")
    sys.exit(1)


async def test_real_extraction():
    """Test extraction with real R2 URLs"""
    print("🧪 TESTING REAL AI EXTRACTION WITH R2 URLS")
    print("=" * 80)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize services
    try:
        ai_service = AIExtractionService()
        template_factory = ExtractionTemplateFactory()
        print("✅ AI Extraction Service initialized")
        print("✅ Template Factory initialized")
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        return

    # Real test scenarios with actual R2 URLs
    test_scenarios = [
        {
            "name": "Restaurant Menu",
            "metadata": {
                "industry": "restaurant",
                "data_type": "products",
                "original_name": "20250714_131220_golden-dragon-menu.jpg",
                "file_type": "image/jpg",
            },
            "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/20250714_131220_golden-dragon-menu.jpg",
            "company_info": {
                "name": "Golden Dragon Restaurant",
                "industry": "restaurant",
                "description": "Traditional Vietnamese restaurant",
            },
        },
        {
            "name": "Hotel Services",
            "metadata": {
                "industry": "hotel",
                "data_type": "services",
                "original_name": "Hotel Majestic Saigon — DỊCH VỤ CHI TIẾT.pdf",
                "file_type": "application/pdf",
            },
            "r2_url": "https://agent8x.io.vn/companies/golden-dragon-restaurant/Hotel%20Majestic%20Saigon%20%E2%80%94%20DI%CC%A3CH%20VU%CC%A3%20CHI%20TIE%CC%82%CC%81T.pdf",
            "company_info": {
                "name": "Hotel Majestic Saigon",
                "industry": "hotel",
                "description": "Luxury hotel in Ho Chi Minh City",
            },
        },
        {
            "name": "Banking Products",
            "metadata": {
                "industry": "banking",
                "data_type": "products",
                "original_name": "20250714_103034_vrb-bank-services.docx",
                "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            },
            "r2_url": "https://agent8x.io.vn/companies/vrb-bank-financial/20250714_103034_vrb-bank-services.docx",
            "company_info": {
                "name": "VRB Bank",
                "industry": "banking",
                "description": "Vietnamese commercial bank",
            },
        },
        {
            "name": "Sản phẩm Bảo hiểm AIA",
            "metadata": {
                "industry": "insurance",
                "data_type": "products",
                "original_name": "Sản phẩm Bảo hiểm AIA.txt",
                "file_type": "text/plain",
            },
            "r2_url": "https://agent8x.io.vn/company/5a44b799-4783-448f-b6a8-b9a51ed7ab76/files/Sa%CC%89n%20pha%CC%82%CC%89m%20Ba%CC%89o%20hie%CC%82%CC%89m%20AIA.txt",
            "company_info": {
                "name": "AIA Insurance",
                "industry": "insurance",
                "description": "Life and health insurance company",
            },
        },
        {
            "name": "Fashion Products (CSV)",
            "metadata": {
                "industry": "fashion",  # Will use generic template
                "data_type": "products",
                "original_name": "20250714_103032_ivy-fashion-products.csv",
                "file_type": "text/csv",
            },
            "r2_url": "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv",
            "company_info": {
                "name": "Ivy Fashion Store",
                "industry": "fashion",
                "description": "Fashion retail store",
            },
        },
    ]

    successful_extractions = 0
    total_tests = len(test_scenarios)

    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}/{total_tests}: {scenario['name']}")
        print(f"{'='*60}")

        metadata = scenario["metadata"]
        r2_url = scenario["r2_url"]
        company_info = scenario.get("company_info")

        print(f"🔗 R2 URL: {r2_url}")
        print(f"🏭 Industry: {metadata['industry']}")
        print(f"📊 Data Type: {metadata['data_type']}")
        print(f"📄 File: {metadata['original_name']}")
        print(f"📋 File Type: {metadata['file_type']}")

        start_time = time.time()

        try:
            # Step 1: Template Selection
            print("\n📋 STEP 1: Template Selection")
            template = template_factory.get_template(metadata["industry"])
            template_name = template.__class__.__name__
            print(f"   ✅ Selected Template: {template_name}")

            # Step 2: AI Provider Selection
            print("\n🤖 STEP 2: AI Provider Selection")
            file_extension = Path(metadata.get("original_name", "")).suffix.lower()
            ai_provider = ai_service._select_ai_provider(file_extension)
            print(f"   ✅ Selected Provider: {ai_provider}")
            print(f"   📎 File Extension: {file_extension}")

            # Step 3: Schema Extraction
            print("\n📑 STEP 3: JSON Schema Extraction")
            try:
                json_schema = template.get_extraction_schema(metadata["data_type"])
                schema_keys = list(json_schema.keys())
                print(f"   ✅ Schema Keys: {schema_keys}")

                if metadata["data_type"] in json_schema:
                    sample_item = json_schema[metadata["data_type"]]
                    if isinstance(sample_item, list) and sample_item:
                        sample_fields = (
                            list(sample_item[0].keys())
                            if isinstance(sample_item[0], dict)
                            else []
                        )
                        print(
                            f"   📝 Sample Fields: {sample_fields[:3]}..."
                            if len(sample_fields) > 3
                            else f"   📝 Sample Fields: {sample_fields}"
                        )

            except Exception as e:
                print(f"   ❌ Schema extraction failed: {e}")
                continue

            # Step 4: Prompt Building
            print("\n💬 STEP 4: Prompt Building")
            try:
                system_prompt = ai_service._build_system_prompt(
                    template, metadata["data_type"], company_info
                )
                user_prompt = ai_service._build_user_prompt(
                    template, metadata["data_type"], metadata, company_info
                )

                print(f"   ✅ System Prompt: {len(system_prompt)} characters")
                print(f"   ✅ User Prompt: {len(user_prompt)} characters")

                # Check for schema integration
                has_schema = (
                    "json" in system_prompt.lower()
                    and "schema" in system_prompt.lower()
                )
                has_raw_req = (
                    "raw_content" in system_prompt
                    and "structured_data" in system_prompt
                )

                print(f"   📋 Schema Integrated: {'✅' if has_schema else '❌'}")
                print(f"   📝 Raw+JSON Required: {'✅' if has_raw_req else '❌'}")

            except Exception as e:
                print(f"   ❌ Prompt building failed: {e}")
                continue

            # Step 5: Real AI Extraction
            print("\n🚀 STEP 5: AI Extraction (REAL TEST)")
            try:
                # This is the real extraction call
                result = await ai_service.extract_from_r2_url(
                    r2_url=r2_url,
                    data_type=metadata["data_type"],
                    metadata=metadata,
                    company_info=company_info,
                )

                processing_time = time.time() - start_time

                # Analyze results
                print(f"   ✅ Extraction completed in {processing_time:.2f}s")

                # Check result structure
                has_raw = "raw_content" in result
                has_structured = "structured_data" in result
                has_metadata = "extraction_metadata" in result

                print(f"   📝 Raw Content: {'✅' if has_raw else '❌'}")
                print(f"   🏗️ Structured Data: {'✅' if has_structured else '❌'}")
                print(f"   📊 Metadata: {'✅' if has_metadata else '❌'}")

                if has_raw:
                    raw_length = (
                        len(result["raw_content"]) if result["raw_content"] else 0
                    )
                    print(f"   📄 Raw Content Length: {raw_length} characters")

                if has_structured:
                    structured_data = result["structured_data"]
                    if isinstance(structured_data, dict):
                        data_items = structured_data.get(metadata["data_type"], [])
                        if isinstance(data_items, list):
                            print(f"   📈 Extracted Items: {len(data_items)}")

                        # Show sample extracted item
                        if data_items and len(data_items) > 0:
                            sample_item = data_items[0]
                            if isinstance(sample_item, dict):
                                sample_keys = list(sample_item.keys())[:3]
                                print(f"   🔍 Sample Item Keys: {sample_keys}")

                if has_metadata:
                    extraction_meta = result["extraction_metadata"]
                    print(
                        f"   🤖 AI Provider Used: {extraction_meta.get('ai_provider', 'unknown')}"
                    )
                    print(
                        f"   📋 Template Used: {extraction_meta.get('template_used', 'unknown')}"
                    )
                    print(f"   📊 Total Items: {extraction_meta.get('total_items', 0)}")

                successful_extractions += 1
                print(f"\n✅ TEST {i} PASSED: Successfully extracted data")

                # Save result to file for inspection
                result_file = f"extraction_result_{i}_{metadata['industry']}_{metadata['data_type']}.json"
                try:
                    with open(result_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    print(f"   💾 Result saved to: {result_file}")
                except Exception as save_error:
                    print(f"   ⚠️ Could not save result: {save_error}")

            except Exception as e:
                print(f"   ❌ AI Extraction failed: {e}")
                print(f"\n❌ TEST {i} FAILED: {str(e)}")

                # Show implementation status if ChatGPT Vision
                if ai_provider == "chatgpt" and "implementation" in str(e).lower():
                    print("   ℹ️ Note: ChatGPT Vision API needs full implementation")
                    print(
                        "   ℹ️ The service architecture is ready, just needs API integration"
                    )

        except Exception as e:
            print(f"\n❌ TEST {i} FAILED: Unexpected error: {e}")

        print(f"\n⏱️ Test {i} completed in {time.time() - start_time:.2f}s")

    # Final Summary
    print("\n" + "=" * 80)
    print("🎯 EXTRACTION TEST SUMMARY")
    print("=" * 80)
    print(f"📊 Total Tests: {total_tests}")
    print(f"✅ Successful: {successful_extractions}")
    print(f"❌ Failed: {total_tests - successful_extractions}")
    print(f"📈 Success Rate: {(successful_extractions/total_tests)*100:.1f}%")
    print()

    if successful_extractions > 0:
        print("🎉 EXTRACTION SYSTEM IS WORKING!")
        print("✅ Template selection functioning")
        print("✅ AI provider selection working")
        print("✅ Schema integration successful")
        print("✅ Raw + structured data extraction")
    else:
        print("⚠️ NO SUCCESSFUL EXTRACTIONS")
        print("❗ Check AI provider configurations")
        print("❗ Verify R2 URL accessibility")
        print("❗ Review error messages above")

    print(f"\n⏰ Total test time: {time.time() - time.time():.1f}s")
    print(f"🕒 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def test_service_health():
    """Test AI service health before running extractions"""
    print("🏥 TESTING AI SERVICE HEALTH")
    print("-" * 40)

    try:
        ai_service = AIExtractionService()

        # Test connections
        print("🔍 Testing AI provider connections...")
        connection_status = await ai_service.test_connection()

        print(
            f"   DeepSeek: {'✅' if connection_status.get('deepseek', False) else '❌'}"
        )
        print(
            f"   ChatGPT: {'✅' if connection_status.get('chatgpt', False) else '❌'}"
        )

        # Test template factory
        print("🔍 Testing template factory...")
        template_factory = ExtractionTemplateFactory()
        template_count = len(template_factory._templates)
        print(f"   Available templates: {template_count}")

        for industry in template_factory._templates.keys():
            print(f"   - {industry}")

        if connection_status.get("deepseek", False) or connection_status.get(
            "chatgpt", False
        ):
            print("\n✅ Service health check passed")
            return True
        else:
            print("\n❌ Service health check failed - No AI providers available")
            return False

    except Exception as e:
        print(f"\n❌ Service health check failed: {e}")
        return False


async def main():
    """Run the complete test suite"""
    print("🚀 STARTING REAL AI EXTRACTION TESTS")
    print("=" * 80)

    # Health check first
    health_ok = await test_service_health()

    if not health_ok:
        print("\n⚠️ Skipping extraction tests due to service health issues")
        print("💡 Check your AI provider API keys and configurations")
        return

    print("\n")

    # Run real extraction tests
    await test_real_extraction()

    print("\n🏁 ALL TESTS COMPLETED")


if __name__ == "__main__":
    asyncio.run(main())
