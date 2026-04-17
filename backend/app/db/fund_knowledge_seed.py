"""정책자금/보증 핵심 지식 시드 데이터 — knowledge_base 초기 적재용

출처: 중소벤처기업부, 중진공(KOSME), 신용보증기금(KODIT), 기술보증기금(KIBO),
     소상공인시장진흥공단, 주택도시기금, 서민금융진흥원 공식 안내 및 FAQ

용도: chat_lite_fund_expert 의 search_knowledge_base 도구가 자금/보증 질문 시 검색.
"""

# 각 항목: (knowledge_type, category, content_dict, confidence)
FUND_SEED_DATA = [
    # ━━━ 중진공 정책자금 ━━━
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "청년창업자금 신청 자격은?",
            "answer": "만 39세 이하 대표자가 운영하는 업력 7년 이내 중소기업. 한도 최대 1억원, 금리 연 2.0~2.5%(고정), 상환 10년 이내(거치 2년 포함). 사업자등록 후 6개월 경과 시 신청 권장. 휴·폐업자, 금융기관 연체자 제외."
        },
        "confidence": 0.95,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "신성장기반자금 자격과 한도는?",
            "answer": "혁신성장 분야(미래신산업, 디지털, 그린뉴딜 등) 기업 대상. 시설자금 최대 60억, 운전자금 최대 5억(시설자금 100% 한도 내). 업력 무관, 금리 정책자금 기준금리 분기별 변동. 평가 등급 BB 이상 권장."
        },
        "confidence": 0.92,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "긴급경영안정자금이 무엇인가요?",
            "answer": "재해, 불황, 환율급변동 등으로 일시적 경영난을 겪는 중소기업 대상. 한도 최대 10억(운전), 금리 연 1.9~2.5%, 상환 5년 이내(거치 2년). 매출 30% 이상 감소 등 객관적 어려움 입증 필요."
        },
        "confidence": 0.93,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "재창업자금 받을 수 있는 조건?",
            "answer": "재창업한 지 7년 이내 중소기업 대표 또는 폐업 후 재창업 준비 중인 자. 최대 60억(시설+운전), 금리 정책자금 기준금리 -0.3%p 우대. 신청 전 '재도전종합지원센터'에서 재창업 교육 이수 필수."
        },
        "confidence": 0.92,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "정책자금 공통 제외 대상은?",
            "answer": "①휴·폐업자(폐업 후 재창업자금 제외) ②국세·지방세 체납자 ③금융기관 연체 90일 이상 ④신용회복 진행 중 ⑤사행성·유흥업 ⑥부동산임대업·금융업 ⑦기업회생/파산 진행 중. 동일 자금 중복신청 제한 1년."
        },
        "confidence": 0.95,
    },
    {
        "type": "insight",
        "category": "정책자금",
        "content": {
            "topic": "정책자금 심사 핵심 포인트",
            "relationship": "심사위원이 가장 보는 것은 ①사업계획서의 시장성·기술성 ②매출 발생 증빙(세금계산서/통장사본) ③대표자 신용등급(개인 BB 이상 권장) ④자기자본 비율(20% 이상 유리) ⑤동종업종 경력. 사업계획서는 KAIST/창업진흥원 양식 기준 12~15페이지 권장."
        },
        "confidence": 0.85,
    },
    # ━━━ 신용보증기금 KODIT ━━━
    {
        "type": "faq",
        "category": "보증",
        "content": {
            "question": "신용보증기금(KODIT) 보증 신청 자격?",
            "answer": "중소기업기본법상 중소기업, 매출 200억 이하(제조업)/120억 이하(서비스). 업력 무관. 신용등급 B+ 이상 권장. 기업당 보증한도 30억(개별기업) ~ 100억(특수보증). 보증료율 연 0.5~3.0%, 부분보증(85~95%) 제공."
        },
        "confidence": 0.94,
    },
    {
        "type": "faq",
        "category": "보증",
        "content": {
            "question": "기술보증기금(KIBO) 신청 자격?",
            "answer": "기술 기반 중소기업·벤처·이노비즈. 기술평가 등급(K1~K5) 받아야 함. 대표자 동일기술분야 경력 3년 이상 권장. 한도 30억(일반)~100억(우수기술), 보증료율 연 0.5~3.0%. KIBO 기술등급 K3 이상이 보증 발급 통과율 높음."
        },
        "confidence": 0.93,
    },
    {
        "type": "faq",
        "category": "보증",
        "content": {
            "question": "지역신용보증재단(지역신보)은 KODIT과 뭐가 달라요?",
            "answer": "지역신보는 소상공인·영세기업 전담. 보증한도 1억 이하(특례 5억) 소액 위주. 지역별 16개 재단(서울·부산·인천 등). 보증료 연 0.5~2.0%(KODIT보다 저렴), 신용등급 진입장벽 낮음. 소상공인은 지역신보 우선 권장."
        },
        "confidence": 0.92,
    },
    {
        "type": "faq",
        "category": "보증",
        "content": {
            "question": "보증서 발급 통과 노하우?",
            "answer": "①사업장 실사 시 정돈된 모습 ②재무제표상 자본잠식·연속 적자 회피 ③매출세금계산서·전자세금계산서 발급 이력 풍부 ④대표자 신용 BB 이상 유지 ⑤기존 보증 여신 대비 신규 보증 비율 50% 이내. 거절 시 6개월 후 재신청 가능."
        },
        "confidence": 0.85,
    },
    {
        "type": "error",
        "category": "보증",
        "content": {
            "wrong_info": "보증료는 한 번만 내면 된다",
            "correct_info": "보증료는 연 단위로 매년 납부합니다. 보증료율(0.5~3.0%)은 신용등급에 따라 차등 적용되며, 대출 잔액 기준으로 산정됩니다. 보증 만료 전 갱신 시 재평가 받아야 합니다."
        },
        "confidence": 0.9,
    },
    # ━━━ 소상공인 정책자금 ━━━
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "소상공인 정책자금 종류와 한도?",
            "answer": "①일반경영안정자금(7천만~1억, 금리 2.0~2.7%) ②성장기반자금(2억, 시설/운전 통합) ③긴급경영안정자금(7천만, 재해/매출감소) ④혁신성장촉진자금(2억). 모두 소진공 직접 또는 위탁은행 신청. 신청 자격: 사업자등록 6개월 이상, 상시근로자 5인 미만(제조 10인)."
        },
        "confidence": 0.93,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "소상공인 희망리턴패키지가 뭔가요?",
            "answer": "폐업 위기 또는 재도전 소상공인 종합 지원 패키지. ①재기교육 ②사업정리컨설팅 ③전직장려수당(최대 100만) ④재창업 자금 연계. 폐업 직전·직후 12개월 이내 신청 가능. 소진공 또는 새출발기금에서 운영."
        },
        "confidence": 0.9,
    },
    # ━━━ 주거 대출 (정부 운영) ━━━
    {
        "type": "faq",
        "category": "주거대출",
        "content": {
            "question": "버팀목 전세자금 대출 자격?",
            "answer": "무주택 세대주, 부부합산 연소득 5천만 이하(2자녀 6천, 신혼/혁신성장 7.5천), 임차보증금 수도권 4억/그외 3억 이하. 한도 수도권 1.2억(2자녀 2.2억)/그외 8천(2자녀 1.8억). 금리 연 1.8~2.4%(소득·자녀수 우대). 만 19세 이상."
        },
        "confidence": 0.94,
    },
    {
        "type": "faq",
        "category": "주거대출",
        "content": {
            "question": "디딤돌 주택구입 대출 조건?",
            "answer": "무주택 세대주, 부부합산 연소득 6천만(생애최초 7천, 신혼 8.5천) 이하, 주택가격 6억 이하. 한도 최대 4억(생애최초 4억, 신혼 4억, 2자녀 4.2억). 금리 연 2.15~3.0%, 상환 10/15/20/30년. 만 30세 이상 또는 미혼 단독세대주는 금리 가산."
        },
        "confidence": 0.93,
    },
    {
        "type": "faq",
        "category": "주거대출",
        "content": {
            "question": "청년 전용 버팀목과 일반 버팀목 차이?",
            "answer": "청년 전용은 만 19~34세 청년 단독세대주 대상, 한도 최대 2억(보증금 3억 이하), 금리 연 1.5~2.1%(일반보다 0.3%p 우대), 임차주택 면적 60㎡ 이하. 일반 버팀목은 모든 세대주, 한도 1.2억, 금리 1.8~2.4%."
        },
        "confidence": 0.94,
    },
    # ━━━ 서민금융 ━━━
    {
        "type": "faq",
        "category": "서민금융",
        "content": {
            "question": "햇살론 종류와 자격?",
            "answer": "①햇살론15(연소득 4.5천 이하, 한도 1.5천만) ②햇살론17(연소득 3.5천 이하, 한도 1.7천만) ③근로자햇살론(연소득 3.5천, 1.5천만) ④햇살론유스(만19~34세, 1.2천만). 신용등급 6등급 이하 또는 연소득 4.5천 이하. 보증서 기반, 보증료 연 1.5~3.0%, 금리 연 4.9~10.5%."
        },
        "confidence": 0.93,
    },
    {
        "type": "faq",
        "category": "서민금융",
        "content": {
            "question": "미소금융이 뭐예요?",
            "answer": "기초생활수급자·차상위·신용 7등급 이하 등 금융 소외계층 대상 무담보 소액대출. 한도 ①창업자금 7천만 ②운영자금 2천만 ③긴급생계 1백만. 금리 연 2.0~4.5%(매우 저렴). 미소금융재단 또는 지점 신청. 신용회복 중인 자도 가능(특례)."
        },
        "confidence": 0.92,
    },
    {
        "type": "faq",
        "category": "서민금융",
        "content": {
            "question": "긴급복지 생계지원금은?",
            "answer": "갑작스러운 위기(실직, 질병, 화재 등)로 생계 곤란한 가구. 1인 약 71만/4인 196만 한도, 최대 6개월. 의료 300만, 주거 65만, 교육 22만 등 추가 지원. 무상 지원(상환 의무 없음). 주민센터 또는 보건복지콜센터 129 신청."
        },
        "confidence": 0.95,
    },
    # ━━━ 사업계획서/심사 인사이트 ━━━
    {
        "type": "insight",
        "category": "정책자금",
        "content": {
            "topic": "정책자금 사업계획서 가점 항목",
            "relationship": "주요 가점: ①여성기업확인서(5점) ②청년창업기업 만 39세 이하(5점) ③장애인기업확인서(5점) ④사회적기업 인증(3점) ⑤이노비즈/메인비즈/벤처기업확인서(각 3~5점) ⑥특허·실용신안 보유(2점/건) ⑦수출 실적(3점) ⑧고용창출(3점/명). 누적 최대 20점."
        },
        "confidence": 0.85,
    },
    {
        "type": "insight",
        "category": "보증",
        "content": {
            "topic": "보증 거절 흔한 사유",
            "relationship": "①신용등급 CCC 이하(B 미만) ②최근 1년 내 연체 발생 ③자본잠식(부채 > 자본) ④동일 보증 여신 한도 초과 ⑤대표자 거래정지 ⑥사업장 실재 확인 불가 ⑦업종 부적합(부동산/사행성). 거절 시 사유 확인 후 6개월 내 동일사유 미해소면 재신청 의미 없음."
        },
        "confidence": 0.88,
    },

    # ═══ 2026년 중진공 프로그램별 세부 ═══
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "혁신창업사업화자금 조건과 한도는?",
            "answer": "대상: 업력 7년 이내 중소기업(제조·지식서비스 등). 한도: 연간 45억원 이내(운전자금은 연 5억 이내). 금리: 정책자금 기준금리(분기별 변동, 약 2.0~3.0%). 상환: 시설 10년(거치 4년), 운전 6년(거치 2년). 우대: 청년기업(-0.3%p), 여성기업(-0.2%p), 장애인기업(-0.2%p). 신청: 중진공 홈페이지 온라인접수."
        },
        "confidence": 0.95,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "긴급경영안정자금 조건과 한도는?",
            "answer": "대상: 자연재해·경영위기 중소기업. 한도: 재해 피해기업 최대 15억, 일시적 경영애로 최대 10억. 금리: 정책자금 기준금리 - 0.5%p. 상환: 8년(거치 3년). 신청: 피해사실확인서 등 증빙 필요. 일시적 경영위기는 매출 15% 이상 감소 등 객관적 증빙."
        },
        "confidence": 0.9,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "소상공인 정책자금 종류와 조건은?",
            "answer": "① 일반경영안정자금: 소상공인, 한도 7천만원, 금리 연 2.0~3.0%, 5년(거치 2년). ② 특별경영안정자금: 재해·위기 소상공인, 한도 1억원, 금리 연 1.0~2.0%. ③ 성장기반자금: 성장유망 소상공인, 한도 1억, 금리 우대. 공통 자격: 소상공인확인서, 사업자등록 6개월 이상, 국세완납."
        },
        "confidence": 0.9,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "정책자금 신청 절차는?",
            "answer": "① 중진공 홈페이지 회원가입 → ② 온라인 신청서 작성(사업계획서 포함) → ③ 예비평가(서류심사, 1~2주) → ④ 정밀평가(현장실태조사, 2~3주) → ⑤ 융자 결정 통보 → ⑥ 보증서 발급(신보/기보) → ⑦ 대출취급은행에서 융자 실행. 전체 소요: 약 1~2개월."
        },
        "confidence": 0.95,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "정책자금 제외 업종은?",
            "answer": "융자 제외: ①부동산업(건물임대·분양·중개) ②사행시설관리·운영업 ③무도유흥주점 ④기타 사행업 ⑤기타 개인서비스업(안마/점술). 또한 세금 체납, 금융기관 연체, 휴·폐업 상태, 신용정보 등록자는 신청 불가."
        },
        "confidence": 0.95,
    },
    {
        "type": "faq",
        "category": "정책자금",
        "content": {
            "question": "정책자금 중복 수혜 가능한가요?",
            "answer": "중기부 소관 정책자금은 융자잔액 기준 기업당 한도(수도권 60억, 지방 70억) 이내에서 복수 프로그램 신청 가능. 동일 용도 중복 불가. 중기부 자금과 지자체 자금은 별도 한도로 병행 가능. 소진공 소상공인 자금과 중진공 자금도 별도."
        },
        "confidence": 0.9,
    },

    # ═══ 개인 금융 세부 ═══
    {
        "type": "faq",
        "category": "개인금융",
        "content": {
            "question": "버팀목 전세자금 대출 조건은?",
            "answer": "대상: 무주택 세대주, 부부합산 연소득 5천만원 이하(신혼 7.5천만원). 한도: 수도권 1.2억, 비수도권 8천만원. 금리: 연 1.8~2.4%(소득구간별). 상환: 2년(4회 연장, 최장 10년). 보증: HUG 전세보증보험 가입 필수."
        },
        "confidence": 0.9,
    },
    {
        "type": "faq",
        "category": "개인금융",
        "content": {
            "question": "디딤돌 주택구입 대출 조건은?",
            "answer": "대상: 무주택 세대주, 부부합산 연소득 6천만원 이하(생애최초 7천만원, 신혼 8.5천만원). 한도: 최대 2.5억(생애최초 3억). 금리: 연 2.15~3.0%. LTV: 최대 70%. 상환: 10~30년."
        },
        "confidence": 0.9,
    },
    {
        "type": "faq",
        "category": "개인금융",
        "content": {
            "question": "햇살론 종류와 조건은?",
            "answer": "① 햇살론유스(청년): 만 19~34세, 연소득 3.5천만원 이하, 한도 1.2천만원, 금리 3.6%. ② 햇살론15: 연소득 4.5천만원 이하/신용 하위 20%, 한도 2천만원, 금리 15.9% 이내. ③ 햇살론뱅크: 한도 3천만원, 금리 연 5~10%. ④ 근로자햇살론: 재직 3개월 이상, 한도 2천만원, 금리 연 3.5%."
        },
        "confidence": 0.9,
    },
    {
        "type": "faq",
        "category": "개인금융",
        "content": {
            "question": "새희망홀씨 대출 조건은?",
            "answer": "대상: 연소득 3.5천만원 이하 또는 신용등급 하위 10%. 한도: 최대 3천만원. 금리: 연 6~10%(은행별 상이). 상환: 5년(거치 1년). 기존 고금리 대출 대환 용도로도 활용 가능."
        },
        "confidence": 0.85,
    },
]


def seed_fund_knowledge(db_conn) -> dict:
    """knowledge_base에 자금/보증 시드 적재. 중복 방지: 같은 (type, content.question/topic)는 skip."""
    import json
    cur = db_conn.cursor()
    inserted = 0
    skipped = 0
    failed = 0
    for item in FUND_SEED_DATA:
        ktype = item["type"]
        cat = item["category"]
        content = item["content"]
        conf = item["confidence"]
        # 중복 체크: 같은 question/topic이 이미 있는지
        question_key = content.get("question") or content.get("topic") or content.get("wrong_info") or ""
        try:
            cur.execute("""
                SELECT id FROM knowledge_base
                WHERE knowledge_type = %s AND category = %s
                  AND (content->>'question' = %s OR content->>'topic' = %s OR content->>'wrong_info' = %s)
                LIMIT 1
            """, (ktype, cat, question_key, question_key, question_key))
            existing = cur.fetchone()
            if existing:
                skipped += 1
                continue
            cur.execute("""
                INSERT INTO knowledge_base (source, knowledge_type, category, content, confidence)
                VALUES (%s, %s, %s, %s::jsonb, %s)
            """, ("fund_seed", ktype, cat, json.dumps(content, ensure_ascii=False), conf))
            inserted += 1
        except Exception as e:
            print(f"[fund seed] insert error: {e}")
            try: db_conn.rollback()
            except: pass
            failed += 1
    db_conn.commit()
    return {"inserted": inserted, "skipped_duplicates": skipped, "failed": failed, "total_seed": len(FUND_SEED_DATA)}
