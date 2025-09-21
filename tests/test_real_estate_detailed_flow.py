import os
import sys
import json
import asyncio
import aiohttp
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re

# ✅ Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()
# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from utils.real_estate_analyzer import analyze_real_estate_query
from utils.logger import setup_logger

logger = setup_logger()

class RealEstateTestSuite:
    """
    🏠 Complete Real Estate Test Suite - Python version
    Chuyển đổi chính xác từ NodeJS test suite
    """
    
    def __init__(self):
        # ✅ FIXED: Load environment variable after dotenv is loaded
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        print(f"🔍 Checking SERPAPI_KEY...")
        print(f"   Environment SERPAPI_KEY: {'Found' if self.serpapi_key else 'NOT FOUND'}")
        if self.serpapi_key:
            print(f"   Key preview: {self.serpapi_key[:20]}...")
        
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)
        
        # ✅ Website configurations
        self.target_websites = [
            'nhadat.cafeland.vn',
            'alonhadat.com.vn'
        ]
        
        # ✅ Headers for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    async def test_single_question_detailed_flow(self) -> Dict[str, Any]:
        """
        🔍 TESTING SINGLE QUESTION DETAILED FLOW
        Main test function - exact replica of NodeJS version
        """
        print('=' * 100)
        print('🔍 TESTING SINGLE QUESTION DETAILED FLOW')
        print('=' * 100)
        
        question = "Định giá căn hộ 2PN tại Vinhomes Grand Park quận 9 TPHCM?"
        
        print(f'📝 Question: "{question}"')
        print(f'🌐 Target websites: {", ".join(self.target_websites)}')
        print('=' * 80)
        
        # ✅ STEP 1: Analyze Question
        print('\n📊 STEP 1: Analyzing Question...')
        analysis = analyze_real_estate_query(question)
        
        print(f'   🔍 Generated search query: "{analysis.search_query}"')
        print(f'   🎯 Confidence: {round(analysis.confidence * 100)}%')
        print(f'   🏠 Property Type: {analysis.property_type}')
        print(f'   🏗️ Project Name: {analysis.project_name}')
        print(f'   🛏️ Bedrooms: {analysis.bedrooms}')
        
        results = []
        
        # ✅ STEP 2-4: Process Each Website
        async with aiohttp.ClientSession(headers=self.headers) as session:
            for i, website in enumerate(self.target_websites):
                
                print(f'\n{"=" * 80}')
                print(f'🌐 PROCESSING WEBSITE {i + 1}/{len(self.target_websites)}: {website}')
                print(f'{"=" * 80}')
                
                website_result = {
                    'website': website,
                    'search_query': '',
                    'serp_api_results': [],
                    'target_listing_url': '',
                    'properties': [],
                    'success': False,
                    'error': None
                }
                
                try:
                    # ✅ STEP 2: Create Site-Specific Search Query
                    site_specific_query = f"{analysis.search_query} site:{website}"
                    website_result['search_query'] = site_specific_query
                    
                    print(f'\n🔍 STEP 2: Creating Site-Specific Search Query')
                    print(f'   📋 Query: "{site_specific_query}"')
                    
                    # ✅ STEP 3: Search via SerpApi
                    print(f'\n🌐 STEP 3: Searching via SerpApi...')
                    
                    if not self.serpapi_key:
                        raise Exception('SERPAPI_KEY not configured')
                    
                    search_results = await self._search_via_serpapi(site_specific_query)
                    website_result['serp_api_results'] = search_results
                    
                    print(f'   ✅ Found {len(search_results)} search results')
                    
                    if len(search_results) == 0:
                        raise Exception('No search results found')
                    
                    # ✅ Log all search results
                    print(f'   📋 SEARCH RESULTS:')
                    for index, result in enumerate(search_results):
                        print(f'      {index + 1}. "{result["title"]}"')
                        print(f'         🔗 URL: {result["link"]}')
                        snippet = result.get("snippet", "")
                        if snippet:
                            print(f'         📄 Snippet: {snippet[:100]}...')
                    
                    # ✅ Get first result (listing page)
                    first_result = search_results[0]
                    website_result['target_listing_url'] = first_result['link']
                    
                    print(f'\n🎯 SELECTED TARGET URL: {first_result["link"]}')
                    print(f'📄 Expected: Property listing page')
                    
                    # ✅ STEP 4: Extract Properties from Listing Page
                    print(f'\n📋 STEP 4: Extracting Properties from Listing Page...')
                    
                    properties = await self._extract_properties_from_listing_page(
                        session, first_result['link'], website
                    )
                    website_result['properties'] = properties
                    
                    print(f'   ✅ Extracted {len(properties)} properties')
                    
                    # ✅ Log detailed properties
                    if len(properties) > 0:
                        print(f'\n🏘️ EXTRACTED PROPERTIES (showing first 5):')
                        for index, prop in enumerate(properties[:5]):
                            print(f'\n   {index + 1}. Title: "{prop["title"]}"')
                            print(f'      🔗 URL: {prop["url"]}')
                            print(f'      💰 Price: {prop["price"] or "N/A"}')
                            print(f'      📐 Area: {prop["area"] or "N/A"}')
                            detail = prop["detail"]
                            if detail:
                                print(f'      📝 Detail: {detail[:150]}...')
                        
                        if len(properties) > 5:
                            print(f'\n   ... and {len(properties) - 5} more properties')
                    else:
                        print(f'   ⚠️ No properties extracted')
                    
                    website_result['success'] = True
                    
                except Exception as error:
                    print(f'   ❌ Error processing {website}: {str(error)}')
                    website_result['error'] = str(error)
                    website_result['success'] = False
                
                results.append(website_result)
                
                # ✅ Delay between websites
                if i < len(self.target_websites) - 1:
                    delay = 3
                    print(f'\n⏱️ Waiting {delay}s before next website...')
                    await asyncio.sleep(delay)
        
        # ✅ FINAL SUMMARY
        print(f'\n{"=" * 100}')
        print(f'🎉 SINGLE QUESTION TEST COMPLETED')
        print(f'{"=" * 100}')
        
        successful_websites = [r for r in results if r['success']]
        total_properties = sum(len(r['properties']) for r in results)
        
        print(f'📊 SUMMARY:')
        print(f'   ✅ Successful websites: {len(successful_websites)}/{len(results)}')
        print(f'   🏠 Total properties extracted: {total_properties}')
        
        for index, result in enumerate(results):
            print(f'\n   {index + 1}. {result["website"]}:')
            print(f'      ✅ Success: {result["success"]}')
            print(f'      🔗 Target URL: {result["target_listing_url"] or "N/A"}')
            print(f'      🏠 Properties: {len(result["properties"])}')
            if result['error']:
                print(f'      🚨 Error: {result["error"]}')
        
        # ✅ Save results
        timestamp = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        output_file = self.results_dir / f'single-question-detailed-test-{timestamp}.json'
        
        report_data = {
            'question': question,
            'analysis': {
                'search_query': analysis.search_query,
                'property_type': analysis.property_type,
                'project_name': analysis.project_name,
                'bedrooms': analysis.bedrooms,
                'confidence': analysis.confidence,
                'has_price_intent': analysis.has_price_intent,
                'location': {
                    'province': analysis.location.province,
                    'district': analysis.location.district,
                    'street': analysis.location.street,
                    'area': analysis.location.area
                }
            },
            'websites': results,
            'summary': {
                'successful_websites': len(successful_websites),
                'total_websites': len(results),
                'total_properties': total_properties,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f'\n📄 Detailed results saved to: {output_file}')
        
        return report_data

    async def _search_via_serpapi(self, query: str) -> List[Dict[str, Any]]:
        """
        🌐 Search via SerpApi - Helper function
        """
        try:
            params = {
                'q': query,
                'location': 'Vietnam',
                'google_domain': 'google.com.vn',
                'gl': 'vn',
                'hl': 'vi',
                'num': 5,
                'safe': 'active',
                'api_key': self.serpapi_key
            }
            
            response = requests.get('https://serpapi.com/search', params=params, timeout=10)
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"SerpAPI error: {data['error']}")
            
            return data.get('organic_results', [])
            
        except Exception as e:
            logger.error(f"SerpAPI search error: {e}")
            return []

    async def _extract_properties_from_listing_page(self, session: aiohttp.ClientSession, 
                                                  url: str, website: str) -> List[Dict[str, Any]]:
        """
        🏠 Extract Properties from Listing Page - Helper function
        """
        try:
            print(f'      🌐 Fetching content from: {url}')
            
            async with session.get(url, timeout=15) as response:
                if response.status >= 400:
                    raise Exception(f'HTTP {response.status}')
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                page_title = soup.find('title')
                title_text = page_title.text.strip() if page_title else "No title"
                print(f'      ✅ Page loaded successfully')
                print(f'      📄 Page title: {title_text}')
                
                properties = []
                
                # ✅ Website-specific selectors
                property_selector = ''
                selectors = {}
                
                if website == 'nhadat.cafeland.vn':
                    property_selector = '.reales-items-list .reales-items, .product-item, .item-product, .listing-item'
                    selectors = {
                        'title': 'h3 a, .reales-title a, .product-title a, .item-title a',
                        'url': 'h3 a, .reales-title a, .product-title a, .item-title a',
                        'price': '.reales-price, .price, .product-price',
                        'area': '.reales-area, .area, .dien-tich',
                        'detail': '.reales-preview, .preview, .description, .excerpt'
                    }
                elif website == 'alonhadat.com.vn':
                    property_selector = '.content-item, .product-item, .ct_item, .listing-item, .item'
                    selectors = {
                        'title': 'h3 a, .ct_title a, .product-title a, .item-title a',
                        'url': 'h3 a, .ct_title a, .product-title a, .item-title a',
                        'price': '.ct_price, .price, .product-price',
                        'area': '.ct_dt, .area, .dien-tich, [class*="area"]',
                        'detail': '.ct_brief, .brief, .description, .excerpt'
                    }
                
                print(f'      🔍 Using selector: "{property_selector}"')
                
                items = soup.select(property_selector)
                print(f'      📋 Found {len(items)} potential property items')
                
                # ✅ Try multiple selectors if first one doesn't work
                if len(items) == 0:
                    fallback_selectors = [
                        '.product-item, .item-product',
                        '.listing-item, .item-listing',
                        '.content-item, .item-content',
                        '.property-item, .item-property',
                        '.item, .product, .listing',
                        'article, .article',
                        '[class*="item"], [class*="product"], [class*="listing"]'
                    ]
                    
                    for fallback_selector in fallback_selectors:
                        fallback_items = soup.select(fallback_selector)
                        if len(fallback_items) > 0:
                            print(f'      🔄 Using fallback selector: "{fallback_selector}" ({len(fallback_items)} items)')
                            items = fallback_items
                            break
                
                # ✅ Extract properties
                for index, item in enumerate(items[:10]):  # Limit to 10 properties
                    property_data = self._extract_single_property(item, selectors, url)
                    
                    # Only add property if it has meaningful content
                    if (property_data['title'] and 
                        property_data['title'] != 'No title' and 
                        len(property_data['title']) > 10):
                        properties.append(property_data)
                
                print(f'      ✅ Successfully extracted {len(properties)} properties')
                return properties
                
        except Exception as error:
            print(f'      ❌ Error extracting properties: {str(error)}')
            return []

    def _extract_single_property(self, item, selectors: Dict[str, str], base_url: str) -> Dict[str, Any]:
        """
        🏠 Extract data from a single property item
        """
        property_data = {
            'title': '',
            'url': '',
            'price': '',
            'area': '',
            'detail': ''
        }
        
        try:
            # ✅ Extract title and URL
            title_elements = item.select(selectors.get('title', 'h3 a, .title a, a'))
            if title_elements:
                title_element = title_elements[0]
                property_data['title'] = title_element.get_text(strip=True) or title_element.get('title', '') or 'No title'
                href = title_element.get('href', '')
                if href:
                    property_data['url'] = urljoin(base_url, href)
            
            # ✅ Extract price
            price_elements = item.select(selectors.get('price', '.price'))
            if price_elements:
                property_data['price'] = price_elements[0].get_text(strip=True)
            
            # ✅ Extract area
            area_elements = item.select(selectors.get('area', '.area'))
            if area_elements:
                property_data['area'] = area_elements[0].get_text(strip=True)
            
            # ✅ Extract detail
            detail_elements = item.select(selectors.get('detail', '.detail, .description'))
            if detail_elements:
                property_data['detail'] = detail_elements[0].get_text(strip=True)
            
            # ✅ Enhanced extraction from all text if missing
            if not property_data['price'] or not property_data['area']:
                item_text = item.get_text()
                
                if not property_data['price']:
                    price_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:tỷ|triệu|tr|billion|million)', 
                                          item_text, re.IGNORECASE)
                    if price_match:
                        property_data['price'] = price_match.group(0)
                
                if not property_data['area']:
                    area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m2|m²|mét)', 
                                         item_text, re.IGNORECASE)
                    if area_match:
                        property_data['area'] = area_match.group(0)
            
        except Exception as e:
            logger.error(f"Error extracting single property: {e}")
        
        return property_data

    async def run_single_question_test(self):
        """
        🚀 Run single question test - Main entry point
        """
        print('🚀 STARTING SINGLE QUESTION DETAILED TEST...\n')
        
        try:
            # Check SerpApi key
            if not self.serpapi_key:
                print('❌ SERPAPI_KEY not configured. Please set it in .env file or environment variable.')
                print('💡 You can get a free API key from: https://serpapi.com/')
                return
            
            await self.test_single_question_detailed_flow()
            
            print('\n🎉 SINGLE QUESTION TEST COMPLETED SUCCESSFULLY!')
            
        except Exception as error:
            print(f'❌ Single question test failed: {str(error)}')
            import traceback
            traceback.print_exc()

# ✅ Additional test functions
async def test_multiple_questions():
    """Test with multiple questions"""
    test_suite = RealEstateTestSuite()
    
    questions = [
        "Định giá căn hộ 2PN tại Vinhomes Grand Park quận 9 TPHCM?",
        "Giá nhà phố 125m2 đường Thích Thiện Chiếu Bà Rịa Vũng Tàu bao nhiêu?",
        "Căn hộ 3PN Masteri Thảo Điền quận 2 giá thế nào?"
    ]
    
    print("🏠 TESTING MULTIPLE QUESTIONS")
    print("=" * 80)
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*60}")
        print(f"TEST {i}/{len(questions)}: {question}")
        print('='*60)
        
        # Temporarily change the question for testing
        original_method = test_suite.test_single_question_detailed_flow
        
        async def test_with_question():
            # Modify the question in the method
            return await original_method()
        
        result = await test_with_question()
        
        print(f"✅ Completed test {i}")
        
        # Delay between tests
        if i < len(questions):
            await asyncio.sleep(2)

# ✅ Main execution functions
async def main():
    """Main execution function"""
    test_suite = RealEstateTestSuite()
    
    print("🏠 REAL ESTATE TEST SUITE")
    print("=" * 50)
    print("1. Single question detailed test")
    print("2. Multiple questions test")
    print("3. Exit")
    
    while True:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            await test_suite.run_single_question_test()
        elif choice == "2":
            await test_multiple_questions()
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-3.")

if __name__ == "__main__":
    # Run the test
    asyncio.run(main())