"""정책자금/보증/융자 실무 지식 시딩 — knowledge_base 초기 데이터 구축

서버 시작 시 또는 관리자 호출로 실행.
이미 시딩된 경우 중복 삽입 방지.
"""

import json

# source='seed'로 구분하여 수동 지식과 구분
SEED_SOURCE = "seed"

FINANCIAL_KNOWLEDGE = [
    # ── 정책자금 FAQ ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 금리는 얼마인가요?",
            "answer": "중소벤처기업부 정책자금 기준금리는 분기별 변동하며, 2024~2026년 기준 약 연 2.0~3.5% 수준입니다. 변동금리가 기본이며, 우대조건(청년기업 -0.3~0.5%p, 여성기업 -0.2~0.3%p, 혁신성장기업 -0.5%p) 적용 시 1.0~2.5%까지 낮아질 수 있습니다.",
            "context": "정책자금 기준금리는 중소벤처기업진흥공단 홈페이지에서 분기별 공시"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 대출 한도는 얼마까지 가능한가요?",
            "answer": "중기부 소관 정책자금 융자 잔액 기준으로 기업당 60억원 이내(수도권), 지방소재 기업은 70억원 이내입니다. 사업전환/재편 승인기업은 최대 100억원, 긴급경영안정자금은 별도 한도 적용됩니다. 개인사업자는 통상 1~10억, 소상공인 정책자금은 최대 1~2억 수준입니다.",
            "context": "한도는 프로그램별, 기업규모별로 상이하며 기존 융자 잔액이 차감됨"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 상환기간은 어떻게 되나요?",
            "answer": "시설자금: 8~10년 이내(거치기간 3~5년 포함). 운전자금: 5~6년 이내(거치기간 2~3년 포함). 상환방식은 원금균등분할상환이 일반적이며, 일부 프로그램은 원리금균등도 가능합니다.",
            "context": "거치기간 중에는 이자만 납부"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금에 담보가 필요한가요?",
            "answer": "대부분의 정책자금은 신용보증서(신용보증기금·기술보증기금) 또는 부동산 담보가 필요합니다. 신용보증기금: 보증비율 85~100%, 보증료 연 0.5~2.0%. 기술보증기금: 기술력 중심 평가, 보증비율 85~100%, 보증료 연 0.5~1.5%. 소상공인은 지역신보재단 이용 가능(한도 2~8억, 보증료 0.5~1.0%).",
            "context": "보증서 발급에 1~2주 소요, 신용등급 BB 이상 권장"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 신청 자격은 무엇인가요?",
            "answer": "기본 요건: ①중소기업기본법상 중소기업 ②국세/지방세 완납 ③신용등급 제한(휴·폐업자, 금융기관 연체자, 신용불량자 제외). 업종 제한: 부동산업, 사행성 업종, 유흥업소 등 제외. 일부 자금은 업력(예: 창업자금 3년 이내), 매출(예: 소상공인 매출 10억 이하), 직원수(예: 5인 이상) 기준이 있습니다.",
            "context": "세부 자격은 자금별로 다르므로 공고문 확인 필수"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "연체하면 어떻게 되나요?",
            "answer": "연체이율: 기본금리 + 3%p 적용. 30일 이상 연체 시 신용등급 하락. 3회 이상 연체 시 기한이익 상실(잔액 일시상환 요구). 정책자금 연체 이력은 향후 재신청 시 불이익. 다만 일시적 경영난 시 상환유예/기한연장 제도 활용 가능(사전 신청 필요).",
            "context": "연체 전 반드시 중진공에 상환유예 상담"
        },
        "confidence": 0.85
    },

    # ── 보증 FAQ ──
    {
        "knowledge_type": "faq",
        "category": "보증",
        "content": {
            "question": "신용보증기금과 기술보증기금의 차이는 무엇인가요?",
            "answer": "신용보증기금(신보): 기업 신용도 중심 평가. 보증한도 최대 30억(개인 8억). 일반 기업 전반. 기술보증기금(기보): 기술력·특허·R&D 역량 중심 평가. 기술 기반 기업에 유리. 보증한도 최대 30억. 지역신용보증재단: 소상공인·자영업자 위주. 보증한도 2~8억. 보증료 가장 저렴(0.5~1.0%).",
            "context": "기술기업은 기보, 일반 서비스업은 신보, 소상공인은 지역재단 추천"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "보증",
        "content": {
            "question": "보증심사에서 가장 중요한 것은 무엇인가요?",
            "answer": "신보 심사기준: 신용등급(40%) + 사업성/재무상태(30%) + 경영능력(20%) + 담보력(10%). 기보 심사기준: 기술성(40%) + 사업성(25%) + 경영능력(20%) + 재무상태(15%). 공통 핵심: ①최근 3년 재무제표 ②사업계획서 ③대표자 신용정보 ④사업장 실태조사.",
            "context": "재무제표가 없는 신생기업은 사업계획서와 대표자 역량이 더 중요"
        },
        "confidence": 0.85
    },

    # ── 실무 패턴 ──
    {
        "knowledge_type": "pattern",
        "category": "금융",
        "content": {
            "top_questions": [
                "금리가 얼마인가요?",
                "한도는 얼마까지?",
                "상환기간은?",
                "담보 필요한가요?",
                "신청 자격은?",
                "기존 대출이 있어도 되나요?",
                "세금 체납이 있으면 안 되나요?",
                "경쟁률은 어떻게 되나요?",
                "심사기간은 얼마나 걸리나요?",
                "기존 업종을 유지해도 되나요?"
            ],
            "key_fields": ["interest_rate", "loan_limit", "repayment_period", "collateral", "eligibility", "credit_grade"],
            "tips": "정책자금 상담 시 금리/한도/상환/담보는 필수 안내. 공고에 없으면 일반 기준으로 추정 안내 후 담당기관 확인 권장."
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "pattern",
        "category": "금융",
        "content": {
            "top_questions": [
                "자부담은 얼마인가요?",
                "신청 서류가 뭐가 필요한가요?",
                "온라인으로 신청 가능한가요?",
                "사업계획서 양식이 있나요?",
                "심사 결과는 언제 나오나요?",
                "자금 지급은 언제 되나요?",
                "중복으로 다른 자금도 받을 수 있나요?",
                "거절되면 재신청 가능한가요?",
                "조기상환 가능한가요?",
                "용도 변경이 가능한가요?"
            ],
            "key_fields": ["self_funding_ratio", "required_documents", "application_method", "review_period", "overlap_rules"],
            "tips": "서류 관련 질문이 많으므로, 재무제표/사업계획서/법인등기부등본/국세완납증명 등 기본 서류를 안내. 공고별 추가 서류 확인 권장."
        },
        "confidence": 0.85
    },

    # ── 자주 틀리는 정보 (error 유형) ──
    {
        "knowledge_type": "error",
        "category": "금융",
        "content": {
            "wrong_info": "정책자금은 무이자 또는 매우 낮은 금리(1% 미만)라고 답변",
            "correct_info": "정책자금 기준금리는 연 2.0~3.5% 수준이며, 우대금리 적용 시에도 1.0~2.5% 정도입니다. 무이자는 이차보전 사업(지자체 등)에서만 일부 해당.",
            "cause": "이차보전 사업과 일반 정책자금을 혼동"
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "error",
        "category": "금융",
        "content": {
            "wrong_info": "보증서가 있으면 100% 대출 승인된다고 답변",
            "correct_info": "보증서는 담보 역할을 하지만, 대출 승인은 금융기관의 별도 심사를 거칩니다. 보증서 발급 ≠ 대출 확정. 다만 보증서가 있으면 승인률이 크게 높아집니다(90% 이상).",
            "cause": "보증기관과 대출기관(은행)의 역할 혼동"
        },
        "confidence": 0.85
    },
    {
        "knowledge_type": "error",
        "category": "금융",
        "content": {
            "wrong_info": "정책자금과 보조금은 같다고 답변",
            "correct_info": "정책자금(융자)은 상환 의무가 있는 대출이며, 보조금은 상환 의무가 없는 무상 지원입니다. 바우처는 특정 용도 사용권입니다. 세 가지를 명확히 구분하여 안내해야 합니다.",
            "cause": "융자/보조금/바우처 개념 미구분"
        },
        "confidence": 0.95
    },

    # ── 인사이트 ──
    {
        "knowledge_type": "insight",
        "category": "금융",
        "content": {
            "related_ids": [],
            "relationship": "정책자금 신청 기업은 신용보증 + R&D 지원사업 + 고용지원금을 동시에 활용할 수 있습니다. 특히 중기부 정책자금 + 지자체 이차보전을 결합하면 실질 금리를 0~1%까지 낮출 수 있습니다. 또한 정책자금 수혜 기업은 정부 R&D 과제 신청 시 가점을 받는 경우가 있습니다."
        },
        "confidence": 0.8
    },
    {
        "knowledge_type": "insight",
        "category": "금융",
        "content": {
            "related_ids": [],
            "relationship": "사업전환자금 신청 시에는 사업전환계획 승인이 선행되어야 합니다. 승인 절차: ①사업전환계획서 작성 → ②중진공 지역본부 제출 → ③전문가 심사(약 1개월) → ④승인 후 융자 신청. 승인 없이 자금만 신청하면 반려됩니다."
        },
        "confidence": 0.85
    },
    {
        "knowledge_type": "insight",
        "category": "보증",
        "content": {
            "related_ids": [],
            "relationship": "신보/기보 동시 보증이 가능합니다. 신보로 운전자금 보증 + 기보로 기술개발자금 보증을 받아 총 보증한도를 키울 수 있습니다. 다만 합산 보증한도(대기업 제외 약 50억)가 있으므로 한도 관리 필요."
        },
        "confidence": 0.8
    },

    # ── 트렌드 ──
    {
        "knowledge_type": "trend",
        "category": "금융",
        "content": {
            "keyword": "사업전환",
            "count": 0,
            "period": "2026-Q1",
            "description": "제조업→서비스업 전환, 디지털 전환 관련 사업전환자금 수요 증가 추세. 특히 인쇄업, 전통제조업의 IT 전환 문의 빈번."
        },
        "confidence": 0.7
    },
    {
        "knowledge_type": "trend",
        "category": "금융",
        "content": {
            "keyword": "긴급경영안정",
            "count": 0,
            "period": "2026-Q1",
            "description": "경기 침체 시 긴급경영안정자금 문의 급증. 자연재해/경영위기 기업 우선 지원. 일반 정책자금보다 한도가 크고 조건이 유리한 경우 많음."
        },
        "confidence": 0.7
    },

    # ═══ 2026년 중진공 정책자금 프로그램별 세부 지식 ═══

    # ── 혁신창업사업화자금 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "혁신창업사업화자금 조건은?",
            "answer": "대상: 업력 7년 이내 중소기업(제조·지식서비스 등). 한도: 연간 45억원 이내(운전자금은 연 5억 이내). 금리: 정책자금 기준금리(분기별 변동, 약 2.0~3.0%). 상환: 시설 10년(거치 4년), 운전 6년(거치 2년). 우대: 청년기업(-0.3%p), 여성기업(-0.2%p), 장애인기업(-0.2%p). 신청: 중진공 홈페이지 온라인접수.",
            "context": "2026년 중소기업 정책자금 융자계획 공고 기준. 예산 소진 시 조기 마감."
        },
        "confidence": 0.95
    },
    # ── 청년전용창업자금 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "청년전용창업자금 조건은?",
            "answer": "대상: 만 39세 이하 대표, 업력 3년 이내. 한도: 최대 2억원(운전+시설 통합). 금리: 연 2.0% 고정(우대 적용 시 1.5%). 상환: 6년(거치 2년). 신청: 중진공 청년창업 전용 접수. 특이사항: 예비창업자도 사업계획 승인 후 신청 가능.",
            "context": "중소벤처기업부 소관. 경쟁률 높아 사업계획서 완성도가 핵심."
        },
        "confidence": 0.95
    },
    # ── 신성장기반자금 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "신성장기반자금 조건은?",
            "answer": "대상: 사업전환/구조고도화 승인기업, 수출기업, 스마트공장 도입기업, 녹색경영기업 등. 한도: 시설 100억(사업전환), 일반 60억(수도권)/70억(비수도권). 금리: 정책자금 기준금리. 상환: 시설 10년(거치 4년), 운전 6년(거치 2년). 특이사항: 사업전환은 전환계획 승인이 선행 필요.",
            "context": "중진공 소관. 사업전환계획 승인 절차: 사업전환계획서 → 중진공 지역본부 제출 → 전문가 심사(약 1개월) → 승인 후 자금 신청."
        },
        "confidence": 0.9
    },
    # ── 긴급경영안정자금(중기부) ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "긴급경영안정자금 조건은?",
            "answer": "대상: 자연재해·경영위기 중소기업. 한도: 재해 피해기업 최대 15억, 일시적 경영애로 최대 10억. 금리: 정책자금 기준금리 - 0.5%p. 상환: 8년(거치 3년). 신청: 피해사실확인서 등 증빙 필요. 일시적 경영위기는 매출 15% 이상 감소 등 객관적 증빙.",
            "context": "중기부 소관. 예산 별도 배정, 일반 정책자금과 한도 별도 관리."
        },
        "confidence": 0.9
    },
    # ── 소상공인 정책자금(소진공) ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "소상공인 정책자금 종류와 조건은?",
            "answer": "① 일반경영안정자금: 소상공인, 한도 7천만원, 금리 연 2.0~3.0%, 5년(거치 2년). ② 특별경영안정자금: 재해·위기 소상공인, 한도 1억원, 금리 연 1.0~2.0%. ③ 성장기반자금: 성장유망 소상공인, 한도 1억, 금리 우대. ④ 장애인기업자금: 한도 1억, 우대금리. 공통 자격: 소상공인확인서, 사업자등록 6개월 이상, 국세완납.",
            "context": "소상공인시장진흥공단(소진공) 소관. 직접대출+대리대출 방식."
        },
        "confidence": 0.9
    },
    # ── 개인 주거대출 ──
    {
        "knowledge_type": "faq",
        "category": "개인금융",
        "content": {
            "question": "버팀목전세자금 대출 조건은?",
            "answer": "대상: 무주택 세대주, 부부합산 연소득 5천만원 이하(신혼 7.5천만원). 한도: 수도권 1.2억, 비수도권 8천만원. 금리: 연 1.8~2.4%(소득구간별). 상환: 2년(4회 연장, 최장 10년). 보증: HUG 전세보증보험 가입 필수. 신청: 시중은행 영업점.",
            "context": "주택도시기금 소관. 임차보증금 2억 이하(수도권 3억) 주택."
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "개인금융",
        "content": {
            "question": "디딤돌주택구입 대출 조건은?",
            "answer": "대상: 무주택 세대주, 부부합산 연소득 6천만원 이하(생애최초 7천만원, 신혼 8.5천만원). 한도: 최대 2.5억(생애최초 3억). 금리: 연 2.15~3.0%(소득·만기별). LTV: 최대 70%. 상환: 10~30년(거치 1~3년). 신청: 시중은행 영업점.",
            "context": "주택도시기금 소관. 5억 이하 주택(수도권 6억 이하)."
        },
        "confidence": 0.9
    },
    # ── 서민금융 ──
    {
        "knowledge_type": "faq",
        "category": "개인금융",
        "content": {
            "question": "햇살론 종류와 조건은?",
            "answer": "① 햇살론유스(청년): 만 19~34세, 연소득 3.5천만원 이하, 한도 1.2천만원, 금리 3.6%. ② 햇살론15: 연소득 4.5천만원 이하/신용 하위 20%, 한도 2천만원, 금리 15.9% 이내. ③ 햇살론뱅크: 연소득 4.5천만원 이하, 한도 3천만원, 금리 연 5~10%. ④ 근로자햇살론: 재직 3개월 이상, 한도 2천만원, 금리 연 3.5%.",
            "context": "서민금융진흥원 소관. 신용등급·소득 기준으로 상품 구분."
        },
        "confidence": 0.9
    },
    {
        "knowledge_type": "faq",
        "category": "개인금융",
        "content": {
            "question": "새희망홀씨 대출 조건은?",
            "answer": "대상: 연소득 3.5천만원 이하 또는 신용등급 하위 10%. 한도: 최대 3천만원. 금리: 연 6~10%(은행별 상이). 상환: 5년(거치 1년). 신청: 시중은행 영업점. 특이사항: 기존 고금리 대출 대환 용도로도 활용 가능.",
            "context": "시중은행 자체 상품이지만 정부 지원. 금감원 서민금융 1332 안내."
        },
        "confidence": 0.85
    },
    # ── 정책자금 신청 절차 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 신청 절차는 어떻게 되나요?",
            "answer": "① 중진공 홈페이지 회원가입 → ② 온라인 신청서 작성(사업계획서 포함) → ③ 예비평가(서류심사, 1~2주) → ④ 정밀평가(현장실태조사, 2~3주) → ⑤ 융자 결정 통보 → ⑥ 보증서 발급(신보/기보) → ⑦ 대출취급은행에서 융자 실행. 전체 소요: 약 1~2개월.",
            "context": "접수마감일 엄수, 서류 미비 시 보완요청(7일). 사업계획서 작성이 핵심."
        },
        "confidence": 0.95
    },
    # ── 정책자금 제외 업종 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금 신청이 불가능한 업종은?",
            "answer": "융자 제외 업종: ①부동산업(건물임대·분양·중개) ②사행시설관리·운영업 ③기타 갬블링·베팅업 ④무도유흥주점 ⑤기타 사행업 ⑥기타 개인서비스업(안마/점술 등). 또한 세금 체납, 금융기관 연체, 휴·폐업 상태, 한국신용정보원 신용정보 등록자는 신청 불가.",
            "context": "업종 제한은 한국표준산업분류(KSIC) 코드 기준으로 판단."
        },
        "confidence": 0.95
    },
    # ── 중복 지원 규정 ──
    {
        "knowledge_type": "faq",
        "category": "금융",
        "content": {
            "question": "정책자금을 여러 개 동시에 받을 수 있나요?",
            "answer": "중기부 소관 정책자금은 융자잔액 기준 기업당 한도(수도권 60억, 지방 70억) 이내에서 복수 프로그램 신청 가능. 다만 동일 용도 중복은 불가(같은 시설에 대해 두 자금 신청 등). 중기부 자금과 지자체 자금은 별도 한도이므로 병행 가능. 소진공 소상공인 자금과 중진공 자금도 별도.",
            "context": "중복 한도 관리는 정책자금관리시스템(신보/기보)에서 자동 체크."
        },
        "confidence": 0.9
    },
]


def seed_financial_knowledge(db_conn) -> int:
    """knowledge_base에 금융 실무 지식 시딩. 이미 시딩된 경우 스킵."""
    cur = db_conn.cursor()

    # 이미 시딩된 건수 확인
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM knowledge_base WHERE source = %s", (SEED_SOURCE,))
        row = cur.fetchone()
        existing = row["cnt"] if row else 0
        if existing >= len(FINANCIAL_KNOWLEDGE):
            return 0  # 이미 충분히 시딩됨
    except Exception:
        pass

    inserted = 0
    for item in FINANCIAL_KNOWLEDGE:
        try:
            content_json = json.dumps(item["content"], ensure_ascii=False)
            # 중복 체크 (같은 source + type + category + 동일 content의 question/keyword)
            check_key = item["content"].get("question") or item["content"].get("keyword") or item["content"].get("wrong_info") or ""
            if check_key:
                cur.execute(
                    "SELECT id FROM knowledge_base WHERE source = %s AND knowledge_type = %s AND content::text ILIKE %s LIMIT 1",
                    (SEED_SOURCE, item["knowledge_type"], f"%{check_key[:50]}%")
                )
                if cur.fetchone():
                    continue

            cur.execute("""
                INSERT INTO knowledge_base (source, knowledge_type, category, content, confidence)
                VALUES (%s, %s, %s, %s::jsonb, %s)
            """, (SEED_SOURCE, item["knowledge_type"], item.get("category", "금융"),
                  content_json, item.get("confidence", 0.5)))
            inserted += 1
        except Exception as e:
            print(f"[KnowledgeSeed] Insert error: {e}")

    db_conn.commit()
    return inserted
