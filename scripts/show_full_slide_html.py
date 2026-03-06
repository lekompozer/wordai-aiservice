#!/usr/bin/env python3
"""
Show FULL HTML of first slide
"""
import sys

sys.path.insert(0, "/app")

from config.config import get_mongodb
from bs4 import BeautifulSoup

file_id = "file_66e18e975d12"
user_id = "17BeaeikPBQYk8OWeDUkqm0Ov8e2"

db = get_mongodb()
documents = db.documents

doc = documents.find_one(
    {"file_id": file_id, "user_id": user_id}, sort=[("created_at", -1)]
)

if doc:
    html = doc.get("content_html", "")
    soup = BeautifulSoup(html, "html.parser")
    slides = soup.find_all("div", class_="slide")

    if slides:
        print(f"\n🎬 SLIDE 1 FULL HTML:")
        print("=" * 80)
        print(str(slides[0]))
        print("=" * 80)

        if len(slides) > 1:
            print(f"\n🎬 SLIDE 2 FULL HTML:")
            print("=" * 80)
            print(str(slides[1]))
            print("=" * 80)
