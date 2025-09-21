import os
import asyncio
import aiohttp
import requests
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .logger import setup_logger

logger = setup_logger()

class WebSearchUtils:
    """
    🌐 Web Search Utilities for Real Estate Data
    """
    
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.target_websites = [
            'nhadat.cafeland.vn',
            'alonhadat.com.vn',
            'guland.vn'
        ]
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }

    async def search_via_serpapi(self, query: str) -> List[Dict[str, Any]]:
        """🌐 Search via SerpApi"""
        try:
            if not self.serpapi_key:
                logger.warning("SERPAPI_KEY not configured")
                return []
            
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
            
            logger.info(f"🔍 SerpAPI Search: {query}")
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get('https://serpapi.com/search', params=params, timeout=5)
            )
            
            data = response.json()
            
            if 'error' in data:
                logger.error(f"SerpAPI error: {data['error']}")
                return []
            
            results = data.get('organic_results', [])
            logger.info(f"✅ SerpAPI found {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"SerpAPI search error: {e}")
            return []

    async def extract_properties_from_listing_page(self, session: aiohttp.ClientSession, 
                                                 url: str, website: str) -> List[Dict[str, Any]]:
        """🏠 Extract Properties from Listing Page"""
        try:
            logger.info(f"🌐 Fetching: {url}")
            
            custom_headers = {
                **self.headers,
                'Referer': f'https://{website}/',
                'Host': website,
            }
            
            async with session.get(
                url, 
                headers=custom_headers,
                timeout=aiohttp.ClientTimeout(total=8),
                allow_redirects=True,
                max_redirects=3
            ) as response:
                
                if response.status >= 400:
                    raise Exception(f'HTTP {response.status}')
                
                html = await response.text(encoding='utf-8')
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove scripts and styles
            for element in soup.find_all(['script', 'style', 'noscript']):
                element.decompose()
            
            logger.info(f"✅ Page loaded: {len(html):,} chars")
            
            # Website-specific extraction
            properties = await self._extract_properties_by_website(soup, website, url)
            
            logger.info(f"🏠 Extracted {len(properties)} properties from {website}")
            return properties
            
        except Exception as error:
            logger.error(f"❌ Error extracting from {url}: {error}")
            return []

    async def _extract_properties_by_website(self, soup: BeautifulSoup, 
                                           website: str, base_url: str) -> List[Dict[str, Any]]:
        """🎯 Website-specific property extraction"""
        properties = []
        
        # Website-specific selectors
        selectors_map = {
            'nhadat.cafeland.vn': {
                'containers': [
                    '.reales-items-list .reales-items',
                    '.product-item',
                    '.listing-item',
                    '.property-item'
                ],
                'title': 'h3 a, .reales-title a, .title a',
                'url': 'h3 a, .reales-title a, .title a',
                'price': '.reales-price, .price, [class*="price"]',
                'area': '.reales-area, .area, [class*="area"]',
                'detail': '.reales-preview, .preview, .description'
            },
            'alonhadat.com.vn': {
                'containers': [
                    '.content-item',
                    '.ct_item', 
                    '.product-item',
                    '.listing-item'
                ],
                'title': '.ct_title a, h3 a, .title a',
                'url': '.ct_title a, h3 a, .title a',
                'price': '.ct_price, .price, [class*="price"]',
                'area': '.ct_dt, .area, [class*="area"]',
                'detail': '.ct_brief, .brief, .description'
            },
            'guland.vn': {
                'containers': [
                    '.c-sdb-card',
                    '.l-sdb-list__single', 
                    '.prj-d-prds',
                    '.sdb-single',
                    '.property-item'
                ],
                'title': '.c-sdb-card__title a, .c-sdb-card__tle a, h3 a, .title a',
                'url': '.c-sdb-card__title a, .c-sdb-card__tle a, h3 a, .title a',
                'price': '.c-sdb-card__inf .sdb-inf-data, .data-l-s, [class*="price"], .price',
                'area': '.c-sdb-card__inf .sdb-inf-data, .data-l-s, [class*="area"], .area',
                'detail': '.c-sdb-card__exc, .c-sdb-card__description, .description'
            },
        }
        
        # Get selectors for this website
        selectors = selectors_map.get(website, selectors_map['nhadat.cafeland.vn'])
        
        # Try different container selectors
        items = []
        for container_selector in selectors['containers']:
            items = soup.select(container_selector)
            if len(items) > 0:
                logger.info(f"🎯 Using selector: {container_selector} ({len(items)} items)")
                break
        
        # Fallback selectors if no specific ones work
        if len(items) == 0:
            fallback_selectors = [
                '.item, .product',
                '[class*="item"], [class*="product"]',
                '[class*="listing"], [class*="property"]',
                'article, .article',
                '.row .col-md-6, .row .col-lg-6'
            ]
            
            for fallback in fallback_selectors:
                items = soup.select(fallback)
                if len(items) >= 3:
                    logger.info(f"🔄 Fallback selector: {fallback} ({len(items)} items)")
                    break
        
        # Extract properties
        for item in items[:15]:  # Limit to 15 properties
            property_data = self._extract_single_property(item, selectors, base_url)
            
            # Validate property
            if (property_data['title'] and 
                len(property_data['title'].strip()) > 10 and
                'javascript' not in property_data['title'].lower()):
                properties.append(property_data)
        
        return properties

    def _extract_single_property(self, item, selectors: Dict[str, str], 
                                base_url: str) -> Dict[str, Any]:
        """🏠 Extract data from single property item"""
        property_data = {
            'title': '',
            'url': '',
            'price': '',
            'area': '',
            'detail': '',
            'website': '',
            'extracted_at': ''
        }
        
        try:
            # Extract title and URL
            title_elements = item.select(selectors.get('title', 'a, h3, .title'))
            if title_elements:
                title_element = title_elements[0]
                property_data['title'] = title_element.get_text(strip=True)
                href = title_element.get('href', '')
                if href:
                    property_data['url'] = urljoin(base_url, href)
            
            # Extract price
            price_elements = item.select(selectors.get('price', '.price'))
            if price_elements:
                property_data['price'] = price_elements[0].get_text(strip=True)
            
            # Extract area
            area_elements = item.select(selectors.get('area', '.area'))
            if area_elements:
                property_data['area'] = area_elements[0].get_text(strip=True)
            
            # Extract detail
            detail_elements = item.select(selectors.get('detail', '.description'))
            if detail_elements:
                property_data['detail'] = detail_elements[0].get_text(strip=True)
            
            # Enhanced extraction from text if missing
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
            
            # Add metadata
            from urllib.parse import urlparse
            property_data['website'] = urlparse(base_url).netloc
            
            from datetime import datetime
            property_data['extracted_at'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error extracting single property: {e}")
        
        return property_data

# Global instance
web_search_utils = WebSearchUtils()

# ✅ NEW: Search ALL 3 websites simultaneously with 10s timeout
# ✅ FIX: Add explicit timeout and debug logs at critical points

async def search_real_estate_properties(search_query: str) -> Dict[str, Any]:
    """
    🚀 FAST: Search ALL 3 websites simultaneously with 10s total timeout
    """
    start_time = asyncio.get_event_loop().time()
    logger.info(f"🚀 Fast web search (10s max): {search_query}")
    
    # ✅ ALWAYS INITIALIZE RESULTS
    all_properties = []
    website_results = []
    all_websites = ['nhadat.cafeland.vn', 'alonhadat.com.vn', 'guland.vn']
    
    try:
        # ✅ FAST CONNECTOR SETTINGS
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=30,
            keepalive_timeout=5
        )
        
        timeout = aiohttp.ClientTimeout(total=12)  # 12s total timeout
        
        async with aiohttp.ClientSession(
            headers=web_search_utils.headers,
            connector=connector,
            timeout=timeout,
            auto_decompress=True
        ) as session:
            
            logger.info(f"📊 Searching ALL {len(all_websites)} websites simultaneously")
            
            # ✅ CREATE TASKS FOR ALL WEBSITES SIMULTANEOUSLY
            async def process_single_website(website: str) -> Dict[str, Any]:
                """Process a single website with individual timeout"""
                try:
                    logger.info(f"🌐 Starting {website}")
                    
                    # Search with individual timeout
                    site_query = f"{search_query} site:{website}"
                    search_task = web_search_utils.search_via_serpapi(site_query)
                    search_results = await asyncio.wait_for(search_task, timeout=4)  # 4s search
                    
                    if not search_results:
                        logger.warning(f"⚠️ {website}: No search results")
                        return {
                            'website': website,
                            'target_url': '',
                            'properties': [],
                            'property_count': 0,
                            'success': False,
                            'error': 'No search results found'
                        }
                    
                    # Get first result and extract
                    target_url = search_results[0]['link']
                    logger.info(f"🎯 {website}: {target_url}")
                    
                    extract_task = web_search_utils.extract_properties_from_listing_page(
                        session, target_url, website
                    )
                    properties = await asyncio.wait_for(extract_task, timeout=7)  # 7s extract
                    
                    if len(properties) > 0:
                        logger.info(f"✅ {website}: {len(properties)} properties")
                        return {
                            'website': website,
                            'target_url': target_url,
                            'properties': properties,
                            'property_count': len(properties),
                            'success': True
                        }
                    else:
                        logger.warning(f"⚠️ {website}: No properties extracted")
                        return {
                            'website': website,
                            'target_url': target_url,
                            'properties': [],
                            'property_count': 0,
                            'success': False,
                            'error': 'No properties extracted'
                        }
                        
                except asyncio.TimeoutError:
                    logger.error(f"⏰ {website}: Timeout")
                    return {
                        'website': website,
                        'target_url': '',
                        'properties': [],
                        'property_count': 0,
                        'success': False,
                        'error': 'Timeout'
                    }
                except Exception as e:
                    logger.error(f"❌ {website}: {e}")
                    return {
                        'website': website,
                        'target_url': '',
                        'properties': [],
                        'property_count': 0,
                        'success': False,
                        'error': str(e)
                    }
            
            # ✅ RUN ALL WEBSITES IN PARALLEL WITH EXPLICIT TIMEOUT
            try:
                tasks = [process_single_website(website) for website in all_websites]
                logger.info(f"🚀 Created {len(tasks)} parallel tasks")
                
                # ✅ USE asyncio.wait WITH EXPLICIT TIMEOUT
                try:
                    # Wait for completion or timeout (10s)
                    completed, pending = await asyncio.wait(
                        tasks, 
                        timeout=10,  # 10s timeout
                        return_when=asyncio.ALL_COMPLETED
                    )
                    
                    logger.info(f"✅ Completed {len(completed)}/{len(all_websites)} tasks in time")
                    
                    # ✅ COLLECT COMPLETED RESULTS
                    for task in completed:
                        try:
                            result = task.result()
                            website_results.append(result)
                            logger.info(f"📝 Added result for {result['website']}: success={result['success']}")
                        except Exception as task_error:
                            logger.error(f"Error getting completed task result: {task_error}")
                    
                    # ✅ HANDLE PENDING TASKS (if any)
                    if pending:
                        logger.warning(f"⏰ {len(pending)} tasks still pending after 10s - cancelling")
                        for task in pending:
                            task.cancel()
                            
                        # ✅ ADD TIMEOUT ENTRIES FOR PENDING TASKS
                        completed_websites = [r['website'] for r in website_results]
                        for website in all_websites:
                            if website not in completed_websites:
                                logger.warning(f"Adding timeout entry for {website}")
                                website_results.append({
                                    'website': website,
                                    'success': False,
                                    'error': 'Timeout - task cancelled',
                                    'properties': [],
                                    'property_count': 0,
                                    'target_url': ''
                                })
                    
                    logger.info(f"📊 Final website_results count: {len(website_results)}")
                    
                except Exception as wait_error:
                    logger.error(f"Error in asyncio.wait: {wait_error}")
                    
                    # ✅ FALLBACK: Try to get any completed results
                    for i, task in enumerate(tasks):
                        website = all_websites[i]
                        try:
                            if task.done() and not task.cancelled():
                                result = task.result()
                                website_results.append(result)
                                logger.info(f"✅ Got fallback result from {website}")
                            else:
                                task.cancel()
                                website_results.append({
                                    'website': website,
                                    'success': False,
                                    'error': 'Fallback timeout',
                                    'properties': [],
                                    'property_count': 0,
                                    'target_url': ''
                                })
                                logger.warning(f"❌ Fallback timeout for {website}")
                        except Exception as fallback_error:
                            logger.error(f"Fallback error for {website}: {fallback_error}")
                            website_results.append({
                                'website': website,
                                'success': False,
                                'error': f'Fallback error: {str(fallback_error)}',
                                'properties': [],
                                'property_count': 0,
                                'target_url': ''
                            })
                
            except Exception as global_parallel_error:
                logger.error(f"Global parallel execution error: {global_parallel_error}")
                
                # ✅ ENSURE ALL WEBSITES ARE REPRESENTED
                for website in all_websites:
                    website_results.append({
                        'website': website,
                        'success': False,
                        'error': f'Global error: {str(global_parallel_error)}',
                        'properties': [],
                        'property_count': 0,
                        'target_url': ''
                    })
            
            # ✅ COLLECT ALL PROPERTIES (EVEN PARTIAL) - WITH DETAILED LOGGING
            logger.info(f"🔍 DEBUG: Starting property collection from {len(website_results)} results")
            
            # ✅ SAVE DETAILED RESULTS TO FILE
            import json
            from datetime import datetime
            
            detailed_log = {
                'timestamp': datetime.now().isoformat(),
                'search_query': search_query,
                'total_elapsed': asyncio.get_event_loop().time() - start_time,
                'website_results_summary': [],
                'all_properties_details': []
            }
            
            for result in website_results:
                # Log summary
                result_summary = {
                    'website': result['website'],
                    'success': result.get('success', False),
                    'error': result.get('error', ''),
                    'property_count': len(result.get('properties', [])),
                    'target_url': result.get('target_url', '')
                }
                detailed_log['website_results_summary'].append(result_summary)
                
                if result.get('success', False) and result.get('properties', []):
                    properties_to_add = result['properties']
                    all_properties.extend(properties_to_add)
                    
                    logger.info(f"✅ Added {len(properties_to_add)} properties from {result['website']}")
                    
                    # ✅ LOG FIRST 3 PROPERTIES WITH DETAILS
                    for i, prop in enumerate(properties_to_add[:3]):
                        logger.info(f"   📄 Property {i+1}: {prop.get('title', 'No title')[:80]}...")
                        logger.info(f"       💰 Price: {prop.get('price', 'N/A')}")
                        logger.info(f"       📐 Area: {prop.get('area', 'N/A')}")
                        logger.info(f"       🔗 URL: {prop.get('url', 'N/A')[:100]}...")
                    
                    # ✅ ADD TO DETAILED LOG
                    for prop in properties_to_add:
                        detailed_log['all_properties_details'].append({
                            'title': prop.get('title', ''),
                            'price': prop.get('price', ''),
                            'area': prop.get('area', ''),
                            'url': prop.get('url', ''),
                            'detail': prop.get('detail', '')[:200] + '...' if len(prop.get('detail', '')) > 200 else prop.get('detail', ''),
                            'website': prop.get('website', ''),
                            'extracted_at': prop.get('extracted_at', '')
                        })
                else:
                    logger.info(f"❌ Skipped {result['website']}: success={result.get('success', False)}, properties={len(result.get('properties', []))}")
            
            # ✅ SAVE DETAILED LOG TO FILE
            try:
                log_filename = f"web_search_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    json.dump(detailed_log, f, ensure_ascii=False, indent=2)
                logger.info(f"💾 Detailed search results saved to: {log_filename}")
            except Exception as save_error:
                logger.error(f"Error saving detailed log: {save_error}")
                
        logger.info(f"🔍 Session closed - collected {len(all_properties)} total properties")
        
    except Exception as global_error:
        logger.error(f"❌ Global error: {global_error}")
        
        # ✅ ENSURE WEBSITE_RESULTS EXISTS EVEN ON GLOBAL ERROR
        if not website_results:
            logger.warning(f"🔧 Creating empty website_results due to global error")
            for website in all_websites:
                website_results.append({
                    'website': website,
                    'success': False,
                    'error': f'Global error: {str(global_error)}',
                    'properties': [],
                    'property_count': 0,
                    'target_url': ''
                })
    
    # ✅ CALCULATE RESULTS (GUARANTEED TO WORK) - WITH DEBUG LOGS
    logger.info(f"🔍 DEBUG: Starting final calculations")
    logger.info(f"🔍 DEBUG: all_properties length: {len(all_properties)}")
    logger.info(f"🔍 DEBUG: website_results length: {len(website_results)}")
    
    total_properties = len(all_properties)
    successful_websites = len([r for r in website_results if r.get('success', False)])
    total_elapsed = asyncio.get_event_loop().time() - start_time
    
    logger.info(f"🔍 DEBUG: Calculated basic stats - total: {total_properties}, successful: {successful_websites}, elapsed: {total_elapsed:.1f}s")
    
    # ✅ DETERMINE STATUS BASED ON RESULTS AND TIME
    if total_elapsed >= 9.5:
        status = 'partial_timeout' if total_properties > 0 else 'timeout_no_results'
    else:
        status = 'completed' if total_properties > 0 else 'no_results'
    
    logger.info(f"🔍 DEBUG: Determined status: {status}")
    
    # ✅ ALWAYS RETURN VALID RESULT - WITH EXPLICIT RETURN CHECK
    logger.info(f"🔍 DEBUG: Creating result object...")
    
    try:
        result = {
            'search_query': search_query,
            'total_properties': total_properties,
            'successful_websites': successful_websites,
            'total_websites_tried': len(all_websites),
            'website_results': website_results,
            'all_properties': all_properties,
            'processing_time': total_elapsed,
            'status': status,
            'strategy': 'parallel_all_websites_with_timeout',
            'is_partial': total_elapsed >= 9.5,
            'timeout_occurred': total_elapsed >= 9.5
        }
        
        logger.info(f"🔍 DEBUG: Result object created successfully")
        logger.info(f"🎉 FINAL RESULTS (in {total_elapsed:.1f}s):")
        logger.info(f"   - Total properties: {total_properties}")
        logger.info(f"   - Successful websites: {successful_websites}/{len(all_websites)}")
        logger.info(f"   - Status: {status}")
        logger.info(f"   - Is partial: {result['is_partial']}")
        logger.info(f"🔍 DEBUG: ===== ABOUT TO RETURN RESULT =====")
        
        # ✅ VALIDATE RESULT BEFORE RETURN
        if not isinstance(result, dict):
            logger.error(f"🔍 DEBUG: Result is not dict: {type(result)}")
            raise Exception("Result is not a dictionary")
        
        if 'total_properties' not in result:
            logger.error(f"🔍 DEBUG: Result missing total_properties")
            raise Exception("Result missing required fields")
        
        logger.info(f"🔍 DEBUG: Result validation passed - returning...")
        return result
        
    except Exception as result_error:
        logger.error(f"🔍 DEBUG: Error creating result: {result_error}")
        
        # ✅ EMERGENCY FALLBACK RESULT
        fallback_result = {
            'search_query': search_query,
            'total_properties': len(all_properties) if all_properties else 0,
            'successful_websites': 0,
            'total_websites_tried': 3,
            'website_results': [],
            'all_properties': all_properties if all_properties else [],
            'processing_time': total_elapsed,
            'status': 'error',
            'strategy': 'emergency_fallback',
            'is_partial': True,
            'timeout_occurred': True,
            'error': str(result_error)
        }
        
        logger.info(f"🔍 DEBUG: Returning emergency fallback result")
        return fallback_result

async def search_real_estate_properties_with_logging(search_query: str, analysis_log: dict):
    """Enhanced web search with comprehensive logging of URLs and responses"""
    
    try:
        # Call existing search function
        result = await search_real_estate_properties(search_query=search_query)
        
        if result and isinstance(result, dict):
            # ✅ LOG TARGET URLS
            target_urls = []
            website_results = result.get('website_results', [])
            
            for site_result in website_results:
                if site_result.get('success'):
                    website_name = site_result.get('website', 'unknown')
                    properties = site_result.get('properties', [])
                    
                    for prop in properties:
                        if prop.get('url'):
                            target_urls.append({
                                "website": website_name,
                                "url": prop.get('url'),
                                "title": prop.get('title', ''),
                                "price": prop.get('price', ''),
                                "area": prop.get('area', ''),
                                "full_content": prop.get('detail', '') + ' ' + prop.get('title', ''),
                                "scraped_at": datetime.now().isoformat()
                            })
            
            # ✅ UPDATE ANALYSIS LOG WITH DETAILED INFO
            analysis_log["web_search"]["target_urls"] = target_urls
            analysis_log["web_search"]["full_responses"] = {
                "search_query": search_query,
                "total_urls_scraped": len(target_urls),
                "websites_accessed": list(set([url["website"] for url in target_urls])),
                "raw_result": result,
                "scraped_content": target_urls
            }
            
            logger.info(f"🌐 Logged {len(target_urls)} target URLs with full content")
            
        return result
        
    except Exception as e:
        logger.error(f"Enhanced web search error: {e}")
        
        # ✅ LOG ERROR
        analysis_log["web_search"]["error"] = {
            "error_message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        return None