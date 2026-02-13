"""
So sánh chi tiết database vs conversations_data.py
Tạo report file để phân tích
"""
import sys
sys.path.append('/app')

from src.database.db_manager import DBManager
from crawler.conversations_data import TOPICS, get_conversations_by_topic
import json


def main():
    db_manager = DBManager()
    db = db_manager.db
    
    print("=" * 80)
    print("DETAILED COMPARISON: DATABASE vs conversations_data.py")
    print("=" * 80)
    
    report = []
    report.append("=" * 80)
    report.append("CHI TIẾT SO SÁNH DATABASE vs conversations_data.py")
    report.append("=" * 80)
    report.append("")
    
    total_db_convs = 0
    total_file_convs = 0
    topics_with_issues = []
    
    for topic_num in range(1, 31):
        print(f"\n{'='*80}")
        print(f"TOPIC {topic_num}")
        print(f"{'='*80}")
        
        report.append(f"\n{'='*80}")
        report.append(f"TOPIC {topic_num}: {TOPICS[topic_num-1]['en']} ({TOPICS[topic_num-1]['slug']})")
        report.append(f"{'='*80}")
        
        # Get from file
        file_convs = get_conversations_by_topic(topic_num)
        total_file_convs += len(file_convs)
        
        # Get from database
        db_convs = list(db.conversation_library.find(
            {"topic_number": topic_num}
        ).sort("conversation_id", 1))
        total_db_convs += len(db_convs)
        
        print(f"File: {len(file_convs)} conversations")
        print(f"Database: {len(db_convs)} conversations")
        
        report.append(f"\nFile: {len(file_convs)} conversations")
        report.append(f"Database: {len(db_convs)} conversations")
        
        # Check count match
        if len(file_convs) != len(db_convs):
            issue = f"❌ MISMATCH: File={len(file_convs)}, DB={len(db_convs)}"
            print(issue)
            report.append(issue)
            topics_with_issues.append(topic_num)
        else:
            status = "✅ Count matches"
            print(status)
            report.append(status)
        
        # Expected slug from file
        expected_slug = TOPICS[topic_num-1]['slug']
        
        # Compare each conversation
        report.append("\nDETAILED COMPARISON:")
        report.append("-" * 80)
        
        # Create lookup for file conversations
        file_conv_map = {c['conversation_index']: c for c in file_convs}
        
        # Check database conversations
        if db_convs:
            report.append("\nDATABASE CONVERSATIONS:")
            for i, db_conv in enumerate(db_convs):
                # Extract index from conversation_id
                # Format: conv_{level}_{slug}_{topic:02d}_{index:03d}
                parts = db_conv['conversation_id'].split('_')
                db_index_str = parts[-1]  # Last part is index
                db_index = int(db_index_str)
                
                db_slug = db_conv.get('topic_slug', 'N/A')
                
                report.append(f"\n  [{i+1}] ID: {db_conv['conversation_id']}")
                report.append(f"      Index: {db_index:03d} | Slug: {db_slug}")
                report.append(f"      Title EN: {db_conv['title']['en']}")
                report.append(f"      Title VI: {db_conv['title']['vi']}")
                
                # Check issues
                issues = []
                
                # Check slug
                if db_slug != expected_slug:
                    issues.append(f"❌ Wrong slug: '{db_slug}' (expected '{expected_slug}')")
                
                # Check index range (should be 1-20)
                if db_index < 1 or db_index > 20:
                    issues.append(f"❌ Wrong index: {db_index} (should be 001-020)")
                
                # Compare with file if index in range
                if 1 <= db_index <= 20 and db_index in file_conv_map:
                    file_conv = file_conv_map[db_index]
                    if db_conv['title']['en'] != file_conv['title_en']:
                        issues.append(f"❌ Title EN mismatch:")
                        issues.append(f"   DB:   {db_conv['title']['en']}")
                        issues.append(f"   File: {file_conv['title_en']}")
                    if db_conv['title']['vi'] != file_conv['title_vi']:
                        issues.append(f"❌ Title VI mismatch:")
                        issues.append(f"   DB:   {db_conv['title']['vi']}")
                        issues.append(f"   File: {file_conv['title_vi']}")
                    if not issues:
                        issues.append("✅ Matches file data")
                elif db_index in file_conv_map:
                    issues.append("⚠️  Index exists in file but out of range in DB")
                else:
                    issues.append("⚠️  No matching conversation in file")
                
                # Check audio
                if db_conv.get('audio_url'):
                    issues.append(f"🎵 Has audio: {db_conv['audio_url'][:50]}...")
                else:
                    issues.append("🔇 No audio")
                
                for issue in issues:
                    report.append(f"      {issue}")
        
        # List file conversations not in database
        db_indices = set()
        for db_conv in db_convs:
            parts = db_conv['conversation_id'].split('_')
            db_index = int(parts[-1])
            db_indices.add(db_index)
        
        missing_in_db = []
        for idx in range(1, 21):
            if idx not in db_indices:
                missing_in_db.append(idx)
        
        if missing_in_db:
            report.append(f"\n⚠️  MISSING IN DATABASE (from file):")
            for idx in missing_in_db:
                file_conv = file_conv_map[idx]
                report.append(f"  [{idx:03d}] {file_conv['title_en']} | {file_conv['title_vi']}")
        
        report.append("")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total in file: {total_file_convs} (should be 600)")
    print(f"Total in database: {total_db_convs}")
    print(f"Topics with issues: {len(topics_with_issues)}")
    if topics_with_issues:
        print(f"  Topic numbers: {topics_with_issues}")
    
    report.append("\n" + "=" * 80)
    report.append("SUMMARY")
    report.append("=" * 80)
    report.append(f"Total in file: {total_file_convs} (should be 600)")
    report.append(f"Total in database: {total_db_convs}")
    report.append(f"Topics with issues: {len(topics_with_issues)}")
    if topics_with_issues:
        report.append(f"  Topic numbers: {topics_with_issues}")
    
    # Write report to file
    report_path = "/tmp/conversation_comparison_report.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\n✅ Report saved to: {report_path}")
    print(f"📄 Total lines: {len(report)}")
    

if __name__ == "__main__":
    main()
