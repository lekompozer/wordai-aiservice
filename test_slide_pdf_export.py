#!/usr/bin/env python3
"""
Test Playwright PDF export for slide document with overlay elements
"""
import sys
import asyncio

sys.path.insert(0, "/app")

from config.config import get_mongodb
from src.services.document_export_service import DocumentExportService
from src.storage.r2_client import R2Client
from src.core.config import APP_CONFIG


async def test_slide_pdf_export():
    """Test PDF export with Playwright for slide document"""

    # Document ID with overlay elements
    document_id = "doc_e2a3e0ae56e1"
    user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

    print(f"\n🧪 Testing Playwright PDF Export")
    print(f"   Document ID: {document_id}")
    print(f"   User ID: {user_id}")
    print("=" * 80)

    # Get document from MongoDB
    db = get_mongodb()
    documents_collection = db.documents

    doc = documents_collection.find_one(
        {"document_id": document_id, "user_id": user_id}
    )

    if not doc:
        print(f"❌ Document not found!")
        return

    print(f"\n✅ Document found:")
    print(f"   Title: {doc.get('title', 'Untitled')}")
    print(f"   Type: {doc.get('document_type', 'unknown')}")
    print(f"   HTML length: {len(doc.get('content_html', ''))} chars")

    # Get overlay elements
    slide_elements = doc.get("slide_elements", [])
    print(f"\n🎨 Overlay Elements: {len(slide_elements)} slide groups")

    for idx, slide_group in enumerate(slide_elements):
        slide_idx = slide_group.get("slideIndex", idx)
        elements = slide_group.get("elements", [])
        print(f"   Slide {slide_idx}: {len(elements)} elements")

        # Count element types
        types_count = {}
        for elem in elements:
            elem_type = elem.get("type", "unknown")
            types_count[elem_type] = types_count.get(elem_type, 0) + 1

        for elem_type, count in types_count.items():
            print(f"      - {elem_type}: {count}")

    # Initialize export service
    r2_client = R2Client(
        account_id=APP_CONFIG["r2_account_id"],
        access_key_id=APP_CONFIG["r2_access_key_id"],
        secret_access_key=APP_CONFIG["r2_secret_access_key"],
        bucket_name=APP_CONFIG["r2_bucket_name"],
    )

    export_service = DocumentExportService(r2_client=r2_client, db=db)

    # Reconstruct HTML with overlays
    html_content = doc.get("content_html", "")

    if slide_elements:
        print(f"\n🔧 Reconstructing HTML with overlay elements...")
        html_content = export_service.reconstruct_html_with_overlays(
            html_content, slide_elements
        )
        print(f"   Reconstructed HTML length: {len(html_content)} chars")

    # Test Playwright PDF export
    print(f"\n🎬 Generating PDF with Playwright...")
    try:
        pdf_bytes, filename = await export_service.export_to_pdf_playwright(
            html_content=html_content,
            title=doc.get("title", "Test Slide"),
            document_type="slide",
        )

        print(f"\n✅ PDF Generated Successfully!")
        print(f"   Filename: {filename}")
        print(
            f"   File size: {len(pdf_bytes):,} bytes ({len(pdf_bytes) / 1024:.1f} KB)"
        )

        # Save to local file for inspection
        output_path = f"/tmp/{filename}"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        print(f"\n💾 PDF saved to: {output_path}")
        print(f"   You can download and view it!")

    except Exception as e:
        print(f"\n❌ PDF Generation Failed!")
        print(f"   Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_slide_pdf_export())
