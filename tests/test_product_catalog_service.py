"""
Unit Tests for ProductCatalogService
Test tự động cho dịch vụ quản lý danh mục sản phẩm

Run tests:
python -m pytest tests/test_product_catalog_service.py -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Import service to test
from src.services.product_catalog_service import (
    ProductCatalogService,
    get_product_catalog_service,
)


@pytest.fixture
def mock_collection():
    """Mock MongoDB collection for testing"""
    collection = AsyncMock()
    return collection


@pytest.fixture
def catalog_service(mock_collection):
    """Create ProductCatalogService with mocked MongoDB"""
    service = ProductCatalogService()
    service.collection = mock_collection
    return service


@pytest.fixture
def sample_product_data():
    """Sample product data from AI extraction"""
    return {
        "name": "Phở Bò Tái",
        "description": "Phở bò tái nạm chín với bánh phở tươi",
        "price": 65000,
        "quantity": 50,
        "category": "Món chính",
        "tags": ["phở", "bò", "nước dùng"],
        "currency": "VND",
    }


@pytest.fixture
def sample_service_data():
    """Sample service data from AI extraction"""
    return {
        "name": "Phòng Deluxe Double",
        "description": "Phòng deluxe view biển với 2 giường đôi",
        "price": 1200000,
        "category": "Accommodation",
        "tags": ["deluxe", "sea view", "double bed"],
    }


class TestProductCatalogService:
    """Test cases for ProductCatalogService"""

    @pytest.mark.asyncio
    async def test_register_product_success(
        self, catalog_service, mock_collection, sample_product_data
    ):
        """Test successful product registration"""
        # Mock successful insertion
        mock_collection.insert_one.return_value.inserted_id = "mock_object_id"

        # Register product
        result = await catalog_service.register_item(
            item_data=sample_product_data,
            company_id="restaurant_123",
            item_type="product",
        )

        # Verify result contains new product_id
        assert "product_id" in result
        assert result["product_id"].startswith("prod_")
        assert result["name"] == "Phở Bò Tái"
        assert result["catalog_price"] == 65000
        assert result["catalog_quantity"] == 50

        # Verify MongoDB insert was called with correct data
        mock_collection.insert_one.assert_called_once()
        inserted_doc = mock_collection.insert_one.call_args[0][0]
        assert inserted_doc["name"] == "Phở Bò Tái"
        assert inserted_doc["company_id"] == "restaurant_123"
        assert inserted_doc["item_type"] == "product"
        assert "product_id" in inserted_doc

    @pytest.mark.asyncio
    async def test_register_service_success(
        self, catalog_service, mock_collection, sample_service_data
    ):
        """Test successful service registration"""
        # Mock successful insertion
        mock_collection.insert_one.return_value.inserted_id = "mock_object_id"

        # Register service
        result = await catalog_service.register_item(
            item_data=sample_service_data, company_id="hotel_456", item_type="service"
        )

        # Verify result contains new service_id
        assert "service_id" in result
        assert result["service_id"].startswith("serv_")
        assert result["name"] == "Phòng Deluxe Double"

        # Verify MongoDB insert was called
        mock_collection.insert_one.assert_called_once()
        inserted_doc = mock_collection.insert_one.call_args[0][0]
        assert inserted_doc["item_type"] == "service"
        assert "service_id" in inserted_doc

    @pytest.mark.asyncio
    async def test_get_catalog_for_prompt_with_query(
        self, catalog_service, mock_collection
    ):
        """Test getting catalog data for AI prompt with search query"""
        # Mock MongoDB find results
        mock_docs = [
            {
                "product_id": "prod_123",
                "item_type": "product",
                "name": "Phở Bò Tái",
                "quantity": 25,
                "price": 65000,
            },
            {
                "product_id": "prod_456",
                "item_type": "product",
                "name": "Phở Gà",
                "quantity": 0,  # Out of stock
                "price": 60000,
            },
        ]

        # Mock async cursor
        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter(mock_docs)
        mock_collection.find.return_value.sort.return_value.limit.return_value = (
            mock_cursor
        )

        # Call method
        results = await catalog_service.get_catalog_for_prompt(
            company_id="restaurant_123", query="phở", limit=5
        )

        # Verify results structure
        assert len(results) == 2

        # Check first item (in stock)
        item1 = results[0]
        assert item1["item_id"] == "prod_123"
        assert item1["name"] == "Phở Bò Tái"
        assert item1["quantity_display"] == "Còn 25"
        assert item1["price_display"] == "65,000 VND"
        assert item1["quantity_raw"] == 25
        assert item1["price_raw"] == 65000

        # Check second item (out of stock)
        item2 = results[1]
        assert item2["quantity_display"] == "Hết hàng"
        assert item2["quantity_raw"] == 0

    @pytest.mark.asyncio
    async def test_get_catalog_for_prompt_no_query(
        self, catalog_service, mock_collection
    ):
        """Test getting catalog data without search query"""
        mock_docs = [
            {
                "service_id": "serv_789",
                "item_type": "service",
                "name": "Phòng VIP",
                "quantity": -1,  # Not tracked
                "price": 2000000,
            }
        ]

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__.return_value = iter(mock_docs)
        mock_collection.find.return_value.sort.return_value.limit.return_value = (
            mock_cursor
        )

        results = await catalog_service.get_catalog_for_prompt(
            company_id="hotel_456", query="", limit=10
        )

        assert len(results) == 1
        item = results[0]
        assert item["item_id"] == "serv_789"
        assert item["quantity_display"] == "Không theo dõi"
        assert item["price_display"] == "2,000,000 VND"

    @pytest.mark.asyncio
    async def test_find_by_name_success(self, catalog_service, mock_collection):
        """Test finding product by name"""
        mock_doc = {
            "product_id": "prod_123",
            "name": "Phở Bò Tái",
            "company_id": "restaurant_123",
        }

        mock_collection.find_one.return_value = mock_doc

        result = await catalog_service.find_by_name(
            company_id="restaurant_123", item_name="phở bò"
        )

        assert result == mock_doc
        mock_collection.find_one.assert_called_once()
        query = mock_collection.find_one.call_args[0][0]
        assert query["company_id"] == "restaurant_123"
        assert "$text" in query

    @pytest.mark.asyncio
    async def test_find_by_name_not_found(self, catalog_service, mock_collection):
        """Test finding product by name when not found"""
        mock_collection.find_one.return_value = None

        result = await catalog_service.find_by_name(
            company_id="restaurant_123", item_name="pizza"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, catalog_service, mock_collection):
        """Test getting item by ID"""
        mock_doc = {"product_id": "prod_123", "name": "Phở Bò Tái"}

        mock_collection.find_one.return_value = mock_doc

        result = await catalog_service.get_by_id("prod_123")

        assert result == mock_doc
        mock_collection.find_one.assert_called_once()
        query = mock_collection.find_one.call_args[0][0]
        assert "$or" in query

    @pytest.mark.asyncio
    async def test_update_quantity_success(self, catalog_service, mock_collection):
        """Test updating item quantity"""
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        success = await catalog_service.update_quantity("prod_123", 30)

        assert success is True
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_quantity_not_found(self, catalog_service, mock_collection):
        """Test updating quantity for non-existent item"""
        mock_result = MagicMock()
        mock_result.modified_count = 0
        mock_collection.update_one.return_value = mock_result

        success = await catalog_service.update_quantity("prod_999", 30)

        assert success is False

    @pytest.mark.asyncio
    async def test_get_company_stats(self, catalog_service, mock_collection):
        """Test getting company statistics"""
        mock_results = [{"_id": "product", "count": 15}, {"_id": "service", "count": 8}]

        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = mock_results
        mock_collection.aggregate.return_value = mock_cursor

        stats = await catalog_service.get_company_stats("company_123")

        assert stats["products"] == 15
        assert stats["services"] == 8
        assert stats["total"] == 23

    def test_extract_price_from_number(self, catalog_service):
        """Test price extraction from numeric value"""
        item_data = {"price": 65000}
        price = catalog_service._extract_price(item_data)
        assert price == 65000.0

    def test_extract_price_from_string(self, catalog_service):
        """Test price extraction from string value"""
        item_data = {"price": "65,000 VND"}
        price = catalog_service._extract_price(item_data)
        assert price == 65000.0

    def test_extract_price_no_price(self, catalog_service):
        """Test price extraction when no price field"""
        item_data = {"name": "Test Item"}
        price = catalog_service._extract_price(item_data)
        assert price == 0.0

    @pytest.mark.asyncio
    async def test_register_item_db_error(
        self, catalog_service, mock_collection, sample_product_data
    ):
        """Test handling database errors during registration"""
        # Mock database error
        mock_collection.insert_one.side_effect = Exception("Database error")

        # Should return original data without ID
        result = await catalog_service.register_item(
            item_data=sample_product_data, company_id="company_123", item_type="product"
        )

        # Should return original data unchanged
        assert result == sample_product_data
        assert "product_id" not in result


class TestSingleton:
    """Test singleton pattern for service"""

    @pytest.mark.asyncio
    async def test_get_singleton_instance(self):
        """Test singleton returns same instance"""
        # Clear any existing instance
        import src.services.product_catalog_service as module

        module._catalog_service = None

        # Get two instances
        with patch.object(
            module.ProductCatalogService, "initialize_indexes", new_callable=AsyncMock
        ):
            service1 = await get_product_catalog_service()
            service2 = await get_product_catalog_service()

        # Should be same instance
        assert service1 is service2


if __name__ == "__main__":
    # Run tests with coverage
    import subprocess

    subprocess.run(
        [
            "python",
            "-m",
            "pytest",
            "tests/test_product_catalog_service.py",
            "-v",
            "--cov=src.services.product_catalog_service",
            "--cov-report=term-missing",
        ]
    )
