#!/usr/bin/env python3
"""
Debug CSV Processing Step by Step
Debug quá trình xử lý CSV từng bước
"""

import asyncio
import aiohttp
import pandas as pd
import io
from datetime import datetime


# Test CSV download and parsing directly
async def test_csv_processing():
    """Test CSV download and text extraction"""
    print("🔍 DEBUGGING CSV PROCESSING STEP BY STEP")
    print("=" * 60)

    csv_url = "https://agent8x.io.vn/companies/ivy-fashion-store/20250714_103032_ivy-fashion-products.csv"

    # Step 1: Download CSV
    print("📥 Step 1: Downloading CSV from R2...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(csv_url) as response:
                if response.status == 200:
                    file_content = await response.read()
                    print(f"✅ Downloaded: {len(file_content)} bytes")
                else:
                    print(f"❌ Download failed: HTTP {response.status}")
                    return
    except Exception as e:
        print(f"❌ Download error: {e}")
        return

    # Step 2: Decode to text
    print("\n📄 Step 2: Decoding to UTF-8 text...")
    try:
        csv_text = file_content.decode("utf-8")
        print(f"✅ Decoded: {len(csv_text)} characters")
        print(f"📝 First 200 chars: {csv_text[:200]}...")
    except Exception as e:
        print(f"❌ Decode error: {e}")
        return

    # Step 3: Parse with pandas
    print("\n📊 Step 3: Parsing CSV with pandas...")
    try:
        df = pd.read_csv(io.StringIO(csv_text))
        print(f"✅ Parsed CSV: {len(df)} rows, {len(df.columns)} columns")
        print(f"📋 Columns: {df.columns.tolist()}")
        print(f"📈 Sample row: {df.iloc[0].to_dict()}")
    except Exception as e:
        print(f"❌ Pandas parse error: {e}")
        return

    # Step 4: Convert to readable text format
    print("\n📝 Step 4: Converting to readable text format...")
    try:
        text_lines = []
        text_lines.append(f"CSV FILE: ivy-fashion-products.csv")
        text_lines.append(f"Total Rows: {len(df)}")
        text_lines.append(f"Columns: {', '.join(df.columns.tolist())}")
        text_lines.append("")

        # Add header
        text_lines.append("HEADER:")
        text_lines.append(" | ".join(df.columns.tolist()))
        text_lines.append("")

        # Add data rows (limit to prevent prompt overflow)
        text_lines.append("DATA ROWS:")
        max_rows = min(10, len(df))  # Show first 10 rows for testing
        for idx, row in df.head(max_rows).iterrows():
            row_text = " | ".join([str(val) for val in row.values])
            text_lines.append(f"Row {idx + 1}: {row_text}")

        if len(df) > max_rows:
            text_lines.append(f"... and {len(df) - max_rows} more rows")

        readable_text = "\n".join(text_lines)
        print(f"✅ Readable text created: {len(readable_text)} characters")
        print(f"📝 Preview:")
        print(
            readable_text[:500] + "..." if len(readable_text) > 500 else readable_text
        )

        return readable_text

    except Exception as e:
        print(f"❌ Text conversion error: {e}")
        return None


# Test the process
async def main():
    print("🚀 STARTING CSV PROCESSING DEBUG")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    result = await test_csv_processing()

    if result:
        print(f"\n🎉 CSV PROCESSING SUCCESSFUL!")
        print(f"📊 Final text length: {len(result)} characters")

        # Save for inspection
        with open("debug_csv_text.txt", "w", encoding="utf-8") as f:
            f.write(result)
        print(f"💾 Saved to: debug_csv_text.txt")
    else:
        print(f"\n❌ CSV PROCESSING FAILED!")

    print(f"\n🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(main())
