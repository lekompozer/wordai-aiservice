import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from src.utils.logger import setup_logger

logger = setup_logger()

@dataclass
class LocationData:
    """Location information structure"""
    address: Optional[str] = None
    street: Optional[str] = None
    ward: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    province: Optional[str] = None
    full: List[str] = None

    def __post_init__(self):
        if self.full is None:
            self.full = []

@dataclass
class RealEstateAnalysis:
    """Complete analysis result for real estate query"""
    has_price_intent: bool = False
    has_question_pattern: bool = False
    property_type: Optional[str] = None
    project_name: Optional[str] = None
    dientich: Optional[str] = None  # ✅ THÊM MỚI: diện tích
    bedrooms: Optional[str] = None
    location: LocationData = None
    search_query: Optional[str] = None
    confidence: float = 0.0
    original_question: str = ""

    def __post_init__(self):
        if self.location is None:
            self.location = LocationData()

class RealEstateQueryAnalyzer:
    """
    🏠 Advanced Real Estate Query Analyzer - Python version
    Chuyển đổi chính xác từ JavaScript sang Python
    """
    
    def __init__(self):
        logger.info("🏠 Initializing Real Estate Query Analyzer...")

    def analyze_real_estate_query(self, question: str) -> RealEstateAnalysis:
        """
        🔍 Analyze real estate question - Main function
        """
        # ✅ Initialize analysis object
        analysis = RealEstateAnalysis(
            original_question=question,
            location=LocationData()
        )

        if not question or not isinstance(question, str):
            return analysis

        # ✅ Log câu hỏi gốc đầy đủ
        logger.info("=" * 60)
        logger.info(f"[REAL ESTATE ANALYZER] ORIGINAL QUESTION (FULL): \"{question}\"")
        logger.info(f"[REAL ESTATE ANALYZER] Question length: {len(question)} characters")
        logger.info("=" * 60)

        # ✅ Normalize question
        normalized_question = self._normalize_question(question)
        logger.info(f"[REAL ESTATE ANALYZER] NORMALIZED QUESTION: \"{normalized_question}\"")

        # ✅ 1. Kiểm tra ý định về giá (price intent) - MỞ RỘNG
        self._detect_price_intent(normalized_question, analysis)

        # ✅ 2. Kiểm tra các pattern câu hỏi - MỚI THÊM
        self._detect_question_patterns(normalized_question, analysis)

        # ✅ 3. Trích xuất loại bất động sản - MỞ RỘNG
        self._extract_property_type(normalized_question, analysis)

        # ✅ 4. Trích xuất số phòng ngủ
        self._extract_bedrooms(normalized_question, analysis)

        # ✅ 5. Trích xuất tên dự án bất động sản - MỚI THÊM
        self._extract_project_name(normalized_question, analysis)

        # ✅ 6. Xử lý 63 tỉnh thành Việt Nam - HOÀN CHỈNH
        self._extract_province(normalized_question, analysis)

        # ✅ 7. Trích xuất quận/huyện (CHÍNH XÁC HƠN)
        self._extract_district(normalized_question, analysis)

        # ✅ 8. Trích xuất tên đường - MỚI THÊM
        self._extract_street(normalized_question, analysis)

        # ✅ 9. Trích xuất diện tích
        self._extract_area_size(normalized_question, analysis)

        # ✅ 10. Trích xuất khu vực/quận huyện - CHÍNH XÁC HƠN
        self._extract_area_info(normalized_question, analysis)

        # ✅ 11. Tạo search query SẠCH SẼ HƠN
        self._generate_search_query(analysis)

        # ✅ Log kết quả cuối cùng - CẬP NHẬT
        self._log_final_results(analysis)

        return analysis

    def _normalize_question(self, question: str) -> str:
        """Normalize question text"""
        normalized = question.lower()
        # Replace non-word characters except Vietnamese and question marks
        normalized = re.sub(r'[^\w\sÀ-ỹ\?]', ' ', normalized)
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    def _detect_price_intent(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 1. Kiểm tra ý định về giá (price intent) - MỞ RỘNG"""
        price_keywords = [
            'định giá', 'giá', 'giá cả', 'bao nhiêu tiền', 'chi phí', 'cost',
            'price', 'giá trị', 'thị giá', 'giá thị trường', 'ước tính',
            'tham khảo giá', 'báo giá', 'pricing', 'valuation', 'định giá',
            'giá bán', 'giá mua', 'bao nhiêu', 'giá hiện tại', 'giá mới nhất'
        ]

        for keyword in price_keywords:
            if keyword in normalized_question:
                analysis.has_price_intent = True
                analysis.confidence += 0.3
                logger.info(f"[REAL ESTATE ANALYZER] ✅ Price intent detected: \"{keyword}\"")
                break

    def _detect_question_patterns(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 2. Kiểm tra các pattern câu hỏi - MỚI THÊM"""
        question_patterns = [
            (r'bao nhiêu', re.IGNORECASE),
            (r'thế nào', re.IGNORECASE),
            (r'như nào', re.IGNORECASE),
            (r'ra sao', re.IGNORECASE),
            (r'\?', 0),
            (r'có đắt không', re.IGNORECASE),
            (r'có rẻ không', re.IGNORECASE),
            (r'khoảng', re.IGNORECASE),
            (r'tầm', re.IGNORECASE),
            (r'từ.*đến', re.IGNORECASE)
        ]

        for pattern, flags in question_patterns:
            if re.search(pattern, normalized_question, flags):
                analysis.has_question_pattern = True
                analysis.confidence += 0.2
                logger.info(f"[REAL ESTATE ANALYZER] ✅ Question pattern detected: {pattern}")
                break

    def _extract_property_type(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 3. Trích xuất loại bất động sản - MỞ RỘNG"""
        property_types = [
            {'keywords': ['bất động sản', 'real estate', 'property'], 'type': 'bất động sản'},
            {'keywords': ['nhà đất', 'đất nhà'], 'type': 'nhà đất'},
            {'keywords': ['căn hộ', 'apartment', 'condo'], 'type': 'căn hộ'},
            {'keywords': ['chung cư', 'condominiums'], 'type': 'chung cư'},
            {'keywords': ['nhà riêng', 'nhà phố', 'townhouse'], 'type': 'nhà riêng'},
            {'keywords': ['biệt thự', 'villa'], 'type': 'biệt thự'},
            {'keywords': ['đất nền', 'lô đất', 'mảnh đất', 'land'], 'type': 'đất nền'},
            {'keywords': ['shophouse', 'nhà mặt tiền'], 'type': 'shophouse'},
            {'keywords': ['văn phòng', 'office'], 'type': 'văn phòng'},
            {'keywords': ['kho xưởng', 'warehouse'], 'type': 'kho xưởng'},
            {'keywords': ['penthouse'], 'type': 'penthouse'},
            {'keywords': ['duplex'], 'type': 'duplex'},
            {'keywords': ['studio'], 'type': 'studio'}
        ]

        for property_type in property_types:
            for keyword in property_type['keywords']:
                if keyword in normalized_question:
                    analysis.property_type = property_type['type']
                    analysis.confidence += 0.25
                    logger.info(f"[REAL ESTATE ANALYZER] ✅ Property type detected: \"{property_type['type']}\" (keyword: \"{keyword}\")")
                    return

    def _extract_bedrooms(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 4. Trích xuất số phòng ngủ"""
        bedroom_patterns = [
            r'(\d+)\s*pn',           # 2PN, 3PN
            r'(\d+)\s*phòng ngủ',    # 2 phòng ngủ
            r'(\d+)\s*bedroom'       # 2 bedroom
        ]

        for pattern in bedroom_patterns:
            match = re.search(pattern, normalized_question, re.IGNORECASE)
            if match:
                analysis.bedrooms = f"{match.group(1)}PN"
                analysis.confidence += 0.1
                logger.info(f"[REAL ESTATE ANALYZER] ✅ Bedrooms: \"{analysis.bedrooms}\"")
                break

    def _extract_project_name(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 5. Trích xuất tên dự án bất động sản - FIXED: Better project detection"""
        project_patterns = [
            # ✅ FIXED: Generic pattern to catch project names after property type (3 words max)
            r'(?:căn hộ|chung cư|nhà phố|biệt thự|đất nền)\s+([A-Za-z][A-Za-z0-9\s]{2,30}?)(?:\s+\d+pn|\s+\d+m|\s+tại|\s+giá|$)',
            
            # ✅ FIXED: Specific patterns for known developers (capture full names)
            r'(vinhomes\s+grand\s+park)',           # Vinhomes Grand Park
            r'(vinhomes\s+central\s+park)',         # Vinhomes Central Park
            r'(vinhomes\s+golden\s+river)',         # Vinhomes Golden River
            r'(vinhomes\s+smart\s+city)',           # Vinhomes Smart City
            r'(vinhomes\s+ocean\s+park)',           # Vinhomes Ocean Park
            r'(vinhomes\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)', # Generic Vinhomes projects (1-2 words)
            
            r'(masteri\s+thảo\s+điền)',             # Masteri Thảo Điền
            r'(masteri\s+an\s+phú)',                # Masteri An Phú
            r'(masteri\s+millennium)',              # Masteri Millennium
            r'(masteri\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)', # Generic Masteri projects
            
            # ✅ FIXED: Bcons projects - capture full name
            r'(bcons\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',              # Bcons Solary, Bcons Garden, etc.
            
            r'(saigon\s+pearl)',
            r'(landmark\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            r'(eco\s+green\s+saigon)',
            r'(eco\s+green)',
            r'(golden\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            r'(sunrise\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            r'(feliz\s+en\s+vista)',
            r'(the\s+manor)',
            r'(estella\s+heights)',
            r'(diamond\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            r'(imperia\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            r'(kingdom\s+[^,.\n\s]+(?:\s+[^,.\n\s]+)?)',
            
            # Pattern chung cho dự án
            r'dự án\s+([^,.\n]{3,30})',
            r'khu đô thị\s+([^,.\n]{3,30})',
            r'khu dân cư\s+([^,.\n]{3,30})'
        ]

        for pattern in project_patterns:
            match = re.search(pattern, normalized_question, re.IGNORECASE)
            if match:
                # ✅ FIXED: Get the full match for developer patterns, or captured group for generic patterns
                if pattern.startswith('(?:căn hộ|chung cư'):
                    # Generic pattern after property type
                    project_name = match.group(1).strip()
                    # Clean up common trailing words
                    project_name = re.sub(r'\s+(tại|giá|ở|thuộc).*$', '', project_name, flags=re.IGNORECASE)
                    project_name = re.sub(r'\s+\d+.*$', '', project_name)  # Remove numbers at end
                elif pattern.startswith('dự án|khu đô thị|khu dân cư'):
                    # Pattern with prefix
                    project_name = match.group(1).strip()
                else:
                    # Developer-specific patterns - take full match
                    project_name = match.group(1).strip() if match.groups() else match.group(0).strip()
                
                # ✅ Clean up common words from project name
                project_name = re.sub(r'\b(dự án|khu đô thị|khu dân cư)\s+', '', project_name, flags=re.IGNORECASE)
                project_name = project_name.strip()
                
                # ✅ FIXED: Limit to 3 words max, but allow full developer + project name
                words = project_name.split()
                if len(words) > 3:
                    project_name = ' '.join(words[:3])
                
                if project_name and len(project_name) > 1:
                    analysis.project_name = project_name
                    analysis.confidence += 0.15
                    logger.info(f"[REAL ESTATE ANALYZER] ✅ Project name detected: \"{analysis.project_name}\"")
                    break

    def _extract_province(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 6. Xử lý 63 tỉnh thành Việt Nam - HOÀN CHỈNH"""
        vietnam_provinces = [
            # Thành phố trung ương
            'hồ chí minh', 'tp hồ chí minh', 'sài gòn', 'ho chi minh city', 'hcmc', 'tphcm',
            'hà nội', 'hanoi', 'thủ đô',
            'đà nẵng', 'da nang', 'danang',
            'hải phòng', 'hai phong',
            'cần thơ', 'can tho',

            # ✅ NEW: Add Bình Dương và các thành phố
            'bình dương', 'binh duong', 'thủ dầu một', 'thu dau mot',
            'dĩ an', 'di an', 'tp dĩ an', 'tp di an', 'thành phố dĩ an',
            'thuận an', 'thuan an',
            'tân uyên', 'tan uyen',
            'bến cát', 'ben cat',
            
            # Tỉnh miền Bắc
            'hà giang', 'cao bằng', 'lào cai', 'điện biên', 'lai châu', 'sơn la',
            'yên bái', 'hoà bình', 'thái nguyên', 'lạng sơn', 'quảng ninh',
            'bắc giang', 'phú thọ', 'vĩnh phúc', 'bắc ninh', 'hải dương',
            'hưng yên', 'thái bình', 'hà nam', 'nam định', 'ninh bình',
            
            # Tỉnh miền Trung
            'thanh hóa', 'nghệ an', 'hà tĩnh', 'quảng bình', 'quảng trị',
            'thừa thiên huế', 'quảng nam', 'quảng ngãi', 'bình định',
            'phú yên', 'khánh hòa', 'ninh thuận', 'bình thuận',
            
            # Tỉnh miền Nam
            'kon tum', 'gia lai', 'đắk lắk', 'đắk nông', 'lâm đồng',
            'bình phước', 'tây ninh', 'bình dương', 'đồng nai', 'bà rịa vũng tàu',
            'long an', 'tiền giang', 'bến tre', 'trà vinh', 'vĩnh long',
            'đồng tháp', 'an giang', 'kiên giang', 'hậu giang', 'sóc trăng',
            'bạc liêu', 'cà mau',
            
            # Thêm các cách gọi khác
            'vũng tàu', 'vung tau', 'nha trang', 'huế', 'hue',
            'biên hòa', 'bien hoa', 'thủ dầu một', 'thu dau mot',
            'long xuyên', 'rạch giá', 'cà mau', 'bạc liêu'
        ]

        for province in vietnam_provinces:
            if province in normalized_question:
                analysis.location.province = province
                analysis.confidence += 0.2
                logger.info(f"[REAL ESTATE ANALYZER] ✅ Province/City detected: \"{province}\"")
                break

    def _extract_district(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 7. Trích xuất quận/huyện (CHÍNH XÁC HƠN)"""
        district_pattern = r'quận\s+(\d+|[a-zA-ZÀ-ỹ\s]+)|huyện\s+([^,.\n\s]+)'
        district_match = re.search(district_pattern, normalized_question, re.IGNORECASE)
        if district_match:
            district_name = (district_match.group(1) or district_match.group(2)).strip()
            analysis.location.district = district_name
            analysis.confidence += 0.15
            logger.info(f"[REAL ESTATE ANALYZER] ✅ District: \"{district_name}\"")

    def _extract_street(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 8. Trích xuất tên đường - FIXED: capture full street names"""
        street_patterns = [
            r'đường\s+([^,.\n]+?)(?:\s+(?:quận|huyện|phường|xã|tp|thành phố|tỉnh)|$)',
            r'phố\s+([^,.\n]+?)(?:\s+(?:quận|huyện|phường|xã|tp|thành phố|tỉnh)|$)',
            r'street\s+([^,.\n]+?)(?:\s+(?:district|ward|city|province)|$)',
            r'road\s+([^,.\n]+?)(?:\s+(?:district|ward|city|province)|$)'
        ]

        for pattern in street_patterns:
            match = re.search(pattern, normalized_question, re.IGNORECASE)
            if match:
                # ✅ FIXED: Extract street name only, without location suffix
                street_name = match.group(1).strip()
                
                # ✅ Clean up the street name
                street_name = re.sub(r'\s+', ' ', street_name)  # Remove extra spaces
                
                analysis.location.street = f"đường {street_name}" if not street_name.startswith(('đường', 'phố')) else street_name
                analysis.location.full.append(analysis.location.street)
                analysis.confidence += 0.1
                logger.info(f"[REAL ESTATE ANALYZER] ✅ Street: \"{analysis.location.street}\"")
                break

    def _extract_area_size(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 9. Trích xuất diện tích"""
        dientich_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:m2|m²|mét vuông)',
            r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)',
            r'dt\s*:?\s*(\d+(?:\.\d+)?)'
        ]
        
        for pattern in dientich_patterns:
            match = re.search(pattern, normalized_question, re.IGNORECASE)
            if match:
                if 'x' in pattern:
                    # Trường hợp "5x20" -> tính diện tích
                    width = float(match.group(1))
                    length = float(match.group(2))
                    area_calculated = width * length
                    analysis.dientich = f"{area_calculated}m²"
                    logger.info(f"[REAL ESTATE ANALYZER] ✅ Area (calculated): {analysis.dientich}")
                else:
                    analysis.dientich = f"{match.group(1)}m²"
                    logger.info(f"[REAL ESTATE ANALYZER] ✅ Area: {analysis.dientich}")
                analysis.confidence += 0.15
                break

    def _extract_area_info(self, normalized_question: str, analysis: RealEstateAnalysis):
        """✅ 10. Trích xuất khu vực/quận huyện - CHÍNH XÁC HƠN"""
        area_patterns = [
            (r'khu vực\s+([^,.\n]+)', 'area'),
            (r'quận\s+(\d+|[a-zA-ZÀ-ỹ\s]+)', 'district'),
            (r'huyện\s+([^,.\n\s]+)', 'district'),
            (r'thị xã\s+([^,.\n\s]+)', 'district'),
            (r'(thủ đức|thu duc)', 'area')  # Đặc biệt cho Thủ Đức
        ]

        for pattern, location_type in area_patterns:
            match = re.search(pattern, normalized_question, re.IGNORECASE)
            if match:
                matched_text = match.group(0).strip()
                
                if location_type == 'area':
                    if 'khu vực' in pattern:
                        analysis.location.area = match.group(1).strip()
                        logger.info(f"[REAL ESTATE ANALYZER] ✅ Area: \"{analysis.location.area}\"")
                    elif 'thủ đức' in pattern.lower():
                        analysis.location.area = 'Thủ Đức'
                        logger.info(f"[REAL ESTATE ANALYZER] ✅ Area: \"Thủ Đức\"")
                elif location_type == 'district':
                    if 'quận' in pattern:
                        district_name = match.group(1).strip()
                        analysis.location.district = district_name
                        logger.info(f"[REAL ESTATE ANALYZER] ✅ District: quận {district_name}")
                    else:
                        district_name = match.group(1).strip()
                        analysis.location.district = district_name
                        logger.info(f"[REAL ESTATE ANALYZER] ✅ District: \"{matched_text}\"")
                
                analysis.location.full.append(matched_text)
                analysis.confidence += 0.15

    def _generate_search_query(self, analysis: RealEstateAnalysis):
        """✅ 11. Tạo search query SẠCH SẼ HƠN - FIXED: Include project name properly"""
        if (analysis.has_price_intent or analysis.has_question_pattern or 
            analysis.property_type or analysis.location.province):
            
            query_parts = []
            
            # Thêm từ khóa giá
            if analysis.has_price_intent or analysis.has_question_pattern:
                query_parts.append('giá')
            
            # Thêm loại bất động sản
            if analysis.property_type:
                query_parts.append(analysis.property_type)
            
            # ✅ FIXED: Thêm tên dự án ngay sau loại BĐS
            if analysis.project_name:
                query_parts.append(analysis.project_name)
            
            # Thêm số phòng ngủ
            if analysis.bedrooms:
                query_parts.append(analysis.bedrooms)
            
            # Thêm diện tích
            if analysis.dientich:
                query_parts.append(analysis.dientich)
            
            # ✅ FIXED: Only add street name without district/province
            if analysis.location.street:
                street_clean = analysis.location.street
                # Remove common location words that might duplicate with province/district
                street_clean = re.sub(r'\b(quận|huyện|thành phố|tp|tỉnh)\s+\w+', '', street_clean, flags=re.IGNORECASE)
                street_clean = street_clean.strip()
                if street_clean:
                    query_parts.append(street_clean)
            
            # ✅ FIXED: Add district only if not already in street
            if analysis.location.district:
                district_text = f"quận {analysis.location.district}" if analysis.location.district.isdigit() else analysis.location.district
                query_parts.append(district_text)
            
            # ✅ FIXED: Add area only if different from district
            if analysis.location.area and analysis.location.area != analysis.location.district:
                query_parts.append(analysis.location.area)
            
            # ✅ FIXED: Add province, but avoid duplication
            if analysis.location.province:
                province_clean = analysis.location.province
                # Don't add if already mentioned in street or area
                if not any(province_clean.lower() in part.lower() for part in query_parts if part):
                    query_parts.append(province_clean)
            
            # Từ khóa năm
            query_parts.append('2025')
            
            # ✅ FIXED: Advanced deduplication
            unique_parts = []
            seen_words = set()
            
            for part in query_parts:
                if part:
                    part_clean = part.strip().lower()
                    # Check if this part contains words we've already seen
                    part_words = set(re.findall(r'\w+', part_clean))
                    
                    # Only add if it doesn't significantly overlap with existing words
                    if not (part_words & seen_words) or len(part_words - seen_words) > 0:
                        unique_parts.append(part)
                        seen_words.update(part_words)
            
            # ✅ Join and limit length
            analysis.search_query = ' '.join(unique_parts).strip()[:100]
            
            # ✅ Final cleanup - remove common duplicated words
            query_words = analysis.search_query.split()
            final_words = []
            seen_normalized = set()
            
            for word in query_words:
                word_normalized = word.lower().strip()
                if word_normalized not in seen_normalized:
                    final_words.append(word)
                    seen_normalized.add(word_normalized)
            
            analysis.search_query = ' '.join(final_words)

    def _log_final_results(self, analysis: RealEstateAnalysis):
        """✅ Log kết quả cuối cùng - CẬP NHẬT"""
        logger.info("=" * 60)
        logger.info("[REAL ESTATE ANALYZER] FINAL ANALYSIS RESULT:")
        logger.info(f"[REAL ESTATE ANALYZER] - Has Price Intent: {analysis.has_price_intent}")
        logger.info(f"[REAL ESTATE ANALYZER] - Has Question Pattern: {analysis.has_question_pattern}")
        logger.info(f"[REAL ESTATE ANALYZER] - Property Type: {analysis.property_type or 'none'}")
        logger.info(f"[REAL ESTATE ANALYZER] - Project Name: {analysis.project_name or 'none'}")
        logger.info(f"[REAL ESTATE ANALYZER] - Bedrooms: {analysis.bedrooms or 'none'}")  # ✅ MỚI
        logger.info(f"[REAL ESTATE ANALYZER] - Area Size: {analysis.dientich or 'none'}")
        logger.info(f"[REAL ESTATE ANALYZER] - Location Street: {analysis.location.street or 'none'}")  # ✅ MỚI
        logger.info(f"[REAL ESTATE ANALYZER] - Location Area: {analysis.location.area or 'none'}")  # ✅ MỚI
        logger.info(f"[REAL ESTATE ANALYZER] - Location Province: {analysis.location.province or 'none'}")
        logger.info(f"[REAL ESTATE ANALYZER] - Location District: {analysis.location.district or 'none'}")
        logger.info(f"[REAL ESTATE ANALYZER] - All Locations: [{', '.join(analysis.location.full)}]")
        logger.info(f"[REAL ESTATE ANALYZER] - Search Query: \"{analysis.search_query or 'none'}\"")
        logger.info(f"[REAL ESTATE ANALYZER] - Confidence Score: {round(analysis.confidence * 100)}%")
        logger.info("=" * 60)

# ✅ Global instance
real_estate_analyzer = RealEstateQueryAnalyzer()

# ✅ Convenience function
def analyze_real_estate_query(question: str) -> RealEstateAnalysis:
    """
    🔍 Analyze real estate query - Convenience function
    """
    return real_estate_analyzer.analyze_real_estate_query(question)

# ✅ Export function for backward compatibility
def get_analysis_dict(question: str) -> Dict[str, Any]:
    """
    📊 Get analysis result as dictionary (for API responses)
    """
    analysis = analyze_real_estate_query(question)
    result = asdict(analysis)
    # Convert LocationData to dict manually if needed
    if hasattr(result['location'], '__dict__'):
        result['location'] = asdict(result['location'])
    return result