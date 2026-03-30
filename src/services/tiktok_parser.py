"""
TikTok Data Export Parser
Parses TikTok data export files (JSON or TXT) to extract video captions for brand analysis.
"""

import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_tiktok_export(raw: bytes, file_type: str) -> List[Dict[str, Any]]:
    """
    Parse TikTok data export file into a list of post dicts.

    Args:
        raw: Raw bytes of the file
        file_type: "json" or "txt"

    Returns:
        List of dicts with keys: date (optional), description, likes (optional), link (optional)
    """
    try:
        if file_type == "json":
            return _parse_json_export(raw)
        elif file_type == "txt":
            return _parse_txt_export(raw)
        else:
            logger.warning(f"Unknown TikTok file type: {file_type}")
            return []
    except Exception as e:
        logger.error(f"Failed to parse TikTok export: {e}")
        return []


def _parse_json_export(raw: bytes) -> List[Dict[str, Any]]:
    """Parse official TikTok JSON data export format."""
    data = json.loads(raw)

    # Standard TikTok Data Export format
    video_list = (
        data.get("Video", {})
        .get("Videos", {})
        .get("VideoList", [])
    )

    # Also support flat array format (some export tools)
    if not video_list and isinstance(data, list):
        video_list = data

    posts = []
    for v in video_list:
        desc = v.get("Desc", "") or v.get("description", "") or v.get("caption", "")
        if not desc:
            continue
        posts.append({
            "date": v.get("Date") or v.get("date"),
            "description": desc.strip(),
            "likes": str(v.get("Likes", "") or v.get("likes", "0")),
            "link": v.get("Link") or v.get("link", ""),
        })

    logger.info(f"📱 Parsed {len(posts)} TikTok posts from JSON export")
    return posts


def _parse_txt_export(raw: bytes) -> List[Dict[str, Any]]:
    """Parse TikTok TXT export (one description per line)."""
    text = raw.decode("utf-8", errors="ignore")
    lines = text.strip().splitlines()

    posts = []
    for line in lines:
        line = line.strip()
        if line:
            posts.append({"description": line})

    logger.info(f"📱 Parsed {len(posts)} TikTok posts from TXT export")
    return posts


def extract_tiktok_insights(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract basic insights from TikTok posts for brand analysis context.

    Args:
        posts: List of parsed TikTok posts

    Returns:
        Dict with descriptions_sample and basic stats
    """
    if not posts:
        return {
            "total_posts": 0,
            "descriptions_sample": [],
            "combined_text": "",
        }

    # Use up to 50 most recent posts for analysis
    sample = posts[:50]
    descriptions = [p["description"] for p in sample if p.get("description")]

    return {
        "total_posts": len(posts),
        "descriptions_sample": descriptions,
        "combined_text": "\n\n".join(descriptions[:50]),
    }
