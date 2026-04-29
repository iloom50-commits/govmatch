"""
중진공 정책자금 소상공인 예외 규칙 knowledge_base 저장
실행: python backend/seed_knowledge_jinjungong.py
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import psycopg2, psycopg2.extras

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

entries = [
    {
        "source": "manual_rule",
        "knowledge_type": "faq",
        "category": "정책자금",
        "source_agent": "seed",
        "content": {
            "question": "소상공인도 중진공 정책자금 신청이 가능한가요?",
            "answer": (
                "원칙적으로 소상공인은 중진공(중소벤처기업진흥공단) 정책자금 신청 불가입니다. "
                "중진공 정책자금은 중소기업기본법상 중소기업을 대상으로 하며, 소상공인은 소진공(소상공인시장진흥공단) 자금을 이용해야 합니다.\n\n"
                "단, 중요한 예외가 있습니다: 업종코드(사업자등록증 기준)와 무관하게, "
                "재무제표상 제품매출이 전체 매출의 50%를 초과하면 실질 제조업으로 인정되어 중진공 정책자금 신청이 가능합니다.\n\n"
                "예시: 사업자등록 업종이 도소매업인 소상공인이라도, "
                "직접 제조·생산한 제품 매출이 전체 매출의 60%라면 제조업으로 간주하여 중진공 신청 자격이 생깁니다."
            ),
            "context": "업종코드가 아닌 재무제표상 제품매출 비중이 기준. 사업자등록 업종만 보고 불가 단정 금지."
        }
    },
    {
        "source": "manual_rule",
        "knowledge_type": "error",
        "category": "정책자금",
        "source_agent": "seed",
        "content": {
            "question": "중진공 정책자금 소상공인 자격 판단",
            "wrong_info": "사업자등록증 업종코드가 도소매·서비스업이면 소상공인이므로 중진공 신청 불가",
            "correct_info": (
                "소상공인 여부 및 중진공 신청 가능 여부는 업종코드가 아닌 재무제표 기준으로 판단해야 합니다. "
                "재무제표상 제품매출 비중이 50% 초과이면 실질 제조업으로 인정되어 중진공 신청 가능. "
                "반드시 '직접 제품을 제조·생산하시나요? 재무제표상 제품매출 비중은 얼마나 되나요?'를 확인할 것."
            )
        }
    },
    {
        "source": "manual_rule",
        "knowledge_type": "insight",
        "category": "정책자금",
        "source_agent": "seed",
        "content": {
            "relationship": (
                "중진공 정책자금 상담 시 소상공인 고객이 있으면 반드시 제품매출 비중을 확인하세요. "
                "많은 소규모 제조업체가 사업자등록을 도소매업으로 해두고 직접 제조를 하는 경우가 많아, "
                "제품매출 50% 초과 여부만 확인하면 중진공 정책자금 신청 기회가 열립니다. "
                "소진공 자금(최대 7천만원)보다 중진공 자금(최대 수십억)이 한도가 훨씬 크므로, "
                "이 예외 조건은 고객에게 매우 중요한 정보입니다."
            ),
            "tips": "소상공인 + 제조 활동 있음 = 재무제표 제품매출 비중 확인 필수"
        }
    }
]

inserted = 0
for e in entries:
    cur.execute("""
        INSERT INTO knowledge_base (source, knowledge_type, category, source_agent, content, confidence)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT DO NOTHING
    """, (
        e["source"], e["knowledge_type"], e["category"],
        e["source_agent"], json.dumps(e["content"], ensure_ascii=False), 0.99
    ))
    inserted += cur.rowcount

conn.commit()
print(f"저장 완료: {inserted}/{len(entries)}건")

# 저장 확인
cur.execute("""
    SELECT knowledge_type, LEFT(content::text, 100) as preview
    FROM knowledge_base
    WHERE source = 'manual_rule' AND category = '정책자금'
    ORDER BY created_at DESC LIMIT 5
""")
for r in cur.fetchall():
    print(f"[{r['knowledge_type']}] {r['preview']}")

conn.close()
