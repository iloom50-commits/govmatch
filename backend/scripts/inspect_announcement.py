"""특정 공고의 DB 저장 상태 점검 — parsed_sections / deep_analysis 유무 확인.

Usage: python scripts/inspect_announcement.py "공고 제목 일부"
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

if len(sys.argv) < 2:
    print("Usage: python inspect_announcement.py '제목 일부'")
    sys.exit(1)

title_query = sys.argv[1]
conn = get_db_connection()
cur = conn.cursor()

print(f"=== 제목에 '{title_query}' 포함된 공고 검색 ===\n")
cur.execute("""
    SELECT announcement_id, title, department, analysis_status,
           created_at, ai_analyzed_at,
           eligibility_logic IS NOT NULL AS has_elig,
           summary_text IS NOT NULL AND summary_text != '' AS has_summary
    FROM announcements
    WHERE title ILIKE %s
    ORDER BY announcement_id DESC
    LIMIT 10
""", (f"%{title_query}%",))

rows = cur.fetchall()
if not rows:
    print("  (매칭 없음)")
    conn.close()
    sys.exit(0)

for r in rows:
    print(f"#{r['announcement_id']}: {r['title'][:80]}")
    print(f"  기관: {r['department']}")
    print(f"  analysis_status: {r['analysis_status']}")
    print(f"  created_at: {r['created_at']}")
    print(f"  ai_analyzed_at: {r['ai_analyzed_at']}")
    print(f"  eligibility_logic 채움: {r['has_elig']}")
    print(f"  summary_text 채움: {r['has_summary']}")
    print()

# 첫 번째 매칭 공고에 대해 announcement_analysis 조회
aid = rows[0]['announcement_id']
print(f"=== #{aid} announcement_analysis 테이블 상태 ===\n")
cur.execute("""
    SELECT announcement_id,
           parsed_sections IS NOT NULL AS has_parsed,
           deep_analysis IS NOT NULL AS has_deep,
           full_text IS NOT NULL AND LENGTH(full_text) > 100 AS has_fulltext,
           LENGTH(full_text) AS ft_len,
           analyzed_at,
           CASE WHEN parsed_sections IS NOT NULL
                THEN LEFT(parsed_sections::text, 200) ELSE '(null)' END AS parsed_preview,
           CASE WHEN deep_analysis IS NOT NULL
                THEN LEFT(deep_analysis::text, 200) ELSE '(null)' END AS deep_preview
    FROM announcement_analysis
    WHERE announcement_id = %s
""", (aid,))
aa = cur.fetchone()
if not aa:
    print(f"  announcement_analysis 행 없음 (아직 분석 안 됨)")
else:
    print(f"  parsed_sections 있음: {aa['has_parsed']}")
    print(f"  deep_analysis 있음: {aa['has_deep']}")
    print(f"  full_text 있음: {aa['has_fulltext']} (길이 {aa['ft_len']})")
    print(f"  analyzed_at: {aa['analyzed_at']}")
    print(f"\n  parsed_sections 미리보기:")
    print(f"    {aa['parsed_preview']}")
    print(f"\n  deep_analysis 미리보기:")
    print(f"    {aa['deep_preview']}")

# 상담 로그에 이 공고에 대한 기록이 있는지
print(f"\n=== #{aid} 관련 상담 이력 (ai_consult_logs) ===\n")
try:
    cur.execute("""
        SELECT log_id, user_id, created_at, agent_type,
               LEFT(user_message, 100) AS user_msg,
               LEFT(ai_response, 150) AS ai_resp
        FROM ai_consult_logs
        WHERE announcement_id = %s OR user_message ILIKE %s OR ai_response ILIKE %s
        ORDER BY created_at DESC
        LIMIT 10
    """, (aid, f"%{title_query[:20]}%", f"%{title_query[:20]}%"))
    logs = cur.fetchall()
    if not logs:
        print("  (상담 이력 없음)")
    else:
        for lg in logs:
            print(f"  [{lg['created_at']}] agent={lg.get('agent_type')} user={lg['user_id']}")
            print(f"    Q: {lg['user_msg']}")
            print(f"    A: {lg['ai_resp']}")
            print()
except Exception as e:
    print(f"  상담 로그 조회 실패: {e}")

conn.close()
