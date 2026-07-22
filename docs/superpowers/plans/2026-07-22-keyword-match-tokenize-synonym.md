# 관심/키워드 매칭 토큰화+동의어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관심/키워드 매칭을 부분문자열 → 토큰화(AND)+동의어(OR)로 개선해 "전문기관 모집" 같은 입력이 관련 공고를 찾도록. 흩어진 로직을 단일 공용 헬퍼로 통일.

**Architecture:** 신규 `app/core/keyword_match.py`에 기존 `SYNONYM_MAP`을 이관·확장하고 `tokenize/expand_token/keyword_hit/build_match_sql`을 둔다. matcher.py는 SYNONYM_MAP을 import만 바꾸고 custom_keywords 매칭을 헬퍼로 교체. main.py의 배치·실시간·맞춤 관심 매칭 3곳을 헬퍼로 교체.

**Tech Stack:** Python(순수 함수), PostgreSQL ILIKE, 기존 test 하네스(`python -m pytest`).

**설계서:** `docs/superpowers/specs/2026-07-22-keyword-match-tokenize-synonym-design.md`

---

## File Structure
- Create: `backend/app/core/keyword_match.py` — SYNONYM_MAP(이관+확장) + tokenize/expand_token/keyword_hit/build_match_sql.
- Create: `backend/test_keyword_match_unit.py` — 헬퍼 단위 테스트.
- Modify: `backend/app/core/matcher.py` — SYNONYM_MAP 정의 제거→import, custom_keywords 직접매칭을 keyword_hit로.
- Modify: `backend/app/main.py` — 배치(1081)·실시간(3250)·맞춤(3533) 관심 매칭을 헬퍼로.

주의: SYNONYM_MAP 이관 시 matcher.py의 기존 사용처(701·1342)가 값 동일하게 계속 동작해야 함(회귀 금지).

---

## Task 1: `keyword_match.py` 모듈 + 단위 테스트 (TDD)

**Files:**
- Create: `backend/app/core/keyword_match.py`
- Test: `backend/test_keyword_match_unit.py`

- [ ] **Step 1: 실패 테스트 작성** — `backend/test_keyword_match_unit.py`:

```python
# -*- coding: utf-8 -*-
"""keyword_match: 토큰화+동의어 매칭 헬퍼 단위 테스트."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.keyword_match import tokenize, expand_token, keyword_hit, build_match_sql, SYNONYM_MAP


def test_tokenize():
    assert tokenize("전문기관 모집") == ["전문기관", "모집"]
    assert tokenize("  창업  ") == ["창업"]
    assert tokenize("") == []

def test_expand_token_synonym():
    exp = expand_token("전문기관")
    assert "전문기관" in exp and "수행기관" in exp and "운영기관" in exp
    # 사전 밖 단어는 자기 자신만
    assert expand_token("바이오") == ["바이오"]

def test_keyword_hit_multiword_and_synonym():
    # 양 토큰이 동의어로 매칭 (수행기관=전문기관族, 지정=모집族)
    assert keyword_hit(["전문기관 모집"], "2026 수행기관 지정 공고") is True
    # 한 토큰만 매칭되면 False (AND)
    assert keyword_hit(["전문기관 모집"], "수행기관 컨설팅 지원") is False
    # 무관
    assert keyword_hit(["전문기관 모집"], "청년 창업 지원사업") is False

def test_keyword_hit_out_of_dict_word_still_matches():
    assert keyword_hit(["바이오"], "바이오헬스 창업기업 모집") is True
    assert keyword_hit(["바이오"], "제조 자동화 지원") is False

def test_keyword_hit_or_across_keywords():
    assert keyword_hit(["수출", "전문기관 모집"], "수출바우처 지원") is True

def test_keyword_hit_empty():
    assert keyword_hit([], "무엇이든") is False
    assert keyword_hit(["  "], "무엇이든") is False

def test_build_match_sql_structure():
    field = "(title || ' ' || COALESCE(category,''))"
    sql, params = build_match_sql(["전문기관 모집"], field)
    # 토큰 2개 → AND 2블록, 각 블록은 동의어 OR
    assert sql is not None
    assert " AND " in sql
    # 파라미터 = 전문기관族(5) + 모집족(4) = 9개
    assert len(params) == 9
    assert all(p.startswith("%") and p.endswith("%") for p in params)

def test_build_match_sql_empty():
    sql, params = build_match_sql([], "F")
    assert sql is None and params == []
```

- [ ] **Step 2: 실패 확인** — Run: `cd backend && python -m pytest test_keyword_match_unit.py -v`. Expected: ImportError(모듈 없음).

- [ ] **Step 3: 구현** — `backend/app/core/keyword_match.py` 생성. `SYNONYM_MAP`은 **matcher.py:240의 기존 항목 전체를 그대로 옮기고**(컨설팅/전문가/수행기관/용역기관/인증/특허/바우처/사업화/입주/해외/디자인/홍보/네트워킹) 아래 기관族·모집族을 추가·정합:

```python
# -*- coding: utf-8 -*-
"""관심/키워드 매칭 공용 헬퍼 — 토큰화 + 동의어 확장.
matcher.py에서 이관한 SYNONYM_MAP의 단일 진실원. DB·IO 없는 순수 함수."""

# 단어 단위 유의어 확장 맵 (커스텀 입력 키워드 → 유사 표현)
SYNONYM_MAP = {
    "컨설팅":   ["컨설팅", "자문", "경영지도", "경영컨설팅", "진단"],
    "전문가":   ["전문가", "멘토", "전문인력", "자문위원", "코치"],
    "수행기관": ["수행기관", "전문기관", "운영기관", "전담기관", "주관기관", "용역", "위탁", "대행", "수탁기관"],
    "용역기관": ["용역기관", "용역", "수행기관", "위탁", "대행"],
    "인증":     ["인증", "인증서", "ISO", "품질인증", "기술인증", "인정"],
    "특허":     ["특허", "지식재산", "IP", "실용신안", "지재권"],
    "바우처":   ["바우처", "쿠폰", "이용권", "지원권"],
    "사업화":   ["사업화", "상용화", "제품화", "양산", "시제품"],
    "입주":     ["입주", "센터입주", "보육", "인큐베이팅", "창업공간"],
    "해외":     ["해외", "수출", "글로벌", "해외진출", "해외시장"],
    "디자인":   ["디자인", "브랜딩", "패키지디자인", "BI", "CI"],
    "홍보":     ["홍보", "마케팅", "광고", "프로모션", "SNS마케팅"],
    "네트워킹": ["네트워킹", "네트워크", "교류", "매칭", "협업"],
    # 기관族 (신규)
    "전문기관": ["전문기관", "수행기관", "운영기관", "전담기관", "주관기관"],
    "운영기관": ["운영기관", "전문기관", "수행기관", "전담기관", "주관기관"],
    "전담기관": ["전담기관", "전문기관", "수행기관", "운영기관", "주관기관"],
    "주관기관": ["주관기관", "전문기관", "수행기관", "운영기관", "전담기관"],
    # 모집族 (신규)
    "모집": ["모집", "지정", "선정", "공모"],
    "지정": ["지정", "모집", "선정", "공모"],
    "선정": ["선정", "모집", "지정", "공모"],
    "공모": ["공모", "모집", "지정", "선정"],
}


def tokenize(keyword):
    """공백 분리, 빈 토큰 제거."""
    return [t for t in (keyword or "").strip().split() if t]


def expand_token(token):
    """동의어 사전에 있으면 동의어 전체, 없으면 자기 자신만."""
    return SYNONYM_MAP.get(token, [token])


def keyword_hit(keywords, text):
    """파이썬용: 키워드 리스트 중 하나라도(OR) 모든 토큰이(AND) 동의어로(OR) text에 매칭되면 True."""
    if not keywords:
        return False
    low = (text or "").lower()
    for kw in keywords:
        toks = tokenize(kw)
        if not toks:
            continue
        if all(any(syn.lower() in low for syn in expand_token(tok)) for tok in toks):
            return True
    return False


def build_match_sql(keywords, field_expr):
    """SQL용: (field ILIKE ...) 조각 + 파라미터. keyword 간 OR / token 간 AND / 동의어 OR.
    keywords 비면 (None, [])."""
    kws = [kw for kw in (keywords or []) if tokenize(kw)]
    if not kws:
        return None, []
    kw_clauses = []
    params = []
    for kw in kws:
        tok_clauses = []
        for tok in tokenize(kw):
            syns = expand_token(tok)
            tok_clauses.append("(" + " OR ".join([f"{field_expr} ILIKE %s" for _ in syns]) + ")")
            params.extend([f"%{s}%" for s in syns])
        kw_clauses.append("(" + " AND ".join(tok_clauses) + ")")
    return "(" + " OR ".join(kw_clauses) + ")", params
```

- [ ] **Step 4: 통과 확인** — Run: `cd backend && python -m pytest test_keyword_match_unit.py -v`. Expected: 전부 PASS. 파라미터 수 불일치 등은 구현/테스트 정합으로 조정(단, 동작 검증은 약화 금지).

- [ ] **Step 5: Commit**
```
git add backend/app/core/keyword_match.py backend/test_keyword_match_unit.py
git commit -m "feat(match): keyword_match 공용 헬퍼(토큰화+동의어) + 단위테스트"
```

---

## Task 2: matcher.py — SYNONYM_MAP 이관(import로 교체)

**Files:** Modify `backend/app/core/matcher.py`

- [ ] **Step 1: SYNONYM_MAP 정의 제거 + import**
`matcher.py:240`의 `SYNONYM_MAP = { ... }` 블록 전체(주석 238-254 포함, 정의만) 삭제하고, 파일 상단 import 구역에 추가:
```python
from app.core.keyword_match import SYNONYM_MAP  # 단일 진실원(이관)
```
(matcher.py:701·1342의 `SYNONYM_MAP[tag]` 사용처는 그대로 — 값이 동일·확장됐으므로 동작 유지.)

- [ ] **Step 2: import·회귀 확인**
Run: `cd backend && python -c "import app.core.matcher; from app.core.matcher import SYNONYM_MAP; print('전문기관' in SYNONYM_MAP, len(SYNONYM_MAP))"`
Expected: `True <N>` (전문기관 포함, 오류 없음). 순환 import 없어야 함(keyword_match는 matcher를 import 안 함).
Run: `cd backend && python -m pytest test_keyword_match_unit.py -v` — 여전히 PASS.

- [ ] **Step 3: Commit**
```
git add backend/app/core/matcher.py
git commit -m "refactor(match): SYNONYM_MAP을 keyword_match로 이관(import)"
```

---

## Task 3: 배치 정렬 `_compute_public_order_for_user` 통합

**Files:** Modify `backend/app/main.py` (~975-1130)

- [ ] **Step 1: summary_text 필드 추가 + interest_hit 교체**
① `_compute_public_order_for_user`의 SELECT([main.py:980-985])에 `summary_text` 추가(없으면):
```python
        f"""SELECT announcement_id, title, region, category,
                   support_amount, support_amount_max, target_type, deadline_date, deadline_type,
                   eligibility_logic, summary_text
            FROM announcements
            WHERE {valid_announcement_where()}
            ORDER BY deadline_date ASC NULLS LAST, created_at DESC"""
```
② 함수 상단(파일 상단 import 가능하면 거기)에 `from app.core.keyword_match import keyword_hit`.
③ interest_hit 계산([main.py:1081])을 교체:
```python
        # 관심분야 일치 (50점) — 토큰화+동의어 매칭
        _match_text = f"{title} {category} {ann.get('summary_text','') or ''}"
        interest_hit = keyword_hit(interests, _match_text)
        if interest_hit:
            score += 50
```

- [ ] **Step 2: import·smoke 확인**
Run: `cd backend && python -c "import app.main"` — 오류 없음.
(정렬 결과는 배치 실행 시 반영 — 실데이터 검증은 Task 7.)

- [ ] **Step 3: Commit**
```
git add backend/app/main.py
git commit -m "feat(match): 배치 관심 정렬을 토큰화+동의어(keyword_hit)로"
```

---

## Task 4: 실시간 public 경로 통합

**Files:** Modify `backend/app/main.py` (~3249-3300)

- [ ] **Step 1: interest_sql/params를 build_match_sql로 교체**
현재([main.py:3249-3257]):
```python
                    if interests:
                        interest_parts = " OR ".join(["(category ILIKE %s OR title ILIKE %s)" for _ in interests])
                        interest_sql = f"({interest_parts})"
                        interest_params = []
                        for it in interests:
                            interest_params.extend([f"%{it}%", f"%{it}%"])
                    else:
                        interest_sql = "FALSE"
                        interest_params = []
```
교체:
```python
                    from app.core.keyword_match import build_match_sql
                    _int_field = "(title || ' ' || COALESCE(category,'') || ' ' || COALESCE(summary_text,''))"
                    _int_sql, interest_params = build_match_sql(interests, _int_field)
                    interest_sql = _int_sql if _int_sql else "FALSE"
```
`bucket_params`([main.py:3300])는 `interest_params`를 그대로 사용하므로 그대로 둔다(개수는 build_match_sql이 산출한 params와 일치).

- [ ] **Step 2: import·smoke 확인**
Run: `cd backend && python -c "import app.main"` — 오류 없음.

- [ ] **Step 3: Commit**
```
git add backend/app/main.py
git commit -m "feat(match): 실시간 public 관심 버킷을 build_match_sql로"
```

---

## Task 5: 맞춤 목록 경로 통합

**Files:** Modify `backend/app/main.py` (~3532-3546)

- [ ] **Step 1: kw_parts를 build_match_sql로 교체**
현재([main.py:3533-3539]):
```python
        if _m_interests:
            kw_parts = " OR ".join(
                ["(title ILIKE %s OR category ILIKE %s OR summary_text ILIKE %s)" for _ in _m_interests]
            )
            _m_where += f" AND ({kw_parts})"
            for kw in _m_interests:
                _m_params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
```
교체:
```python
        if _m_interests:
            from app.core.keyword_match import build_match_sql
            _mf = "(title || ' ' || COALESCE(category,'') || ' ' || COALESCE(summary_text,''))"
            _kw_sql, _kw_params = build_match_sql(_m_interests, _mf)
            if _kw_sql:
                _m_where += f" AND {_kw_sql}"
                _m_params.extend(_kw_params)
```
(score_expr([main.py:3549])는 이번 범위 밖 — 필터 정합만. 그대로 둔다.)

- [ ] **Step 2: import·smoke 확인** — `cd backend && python -c "import app.main"`.

- [ ] **Step 3: Commit**
```
git add backend/app/main.py
git commit -m "feat(match): 맞춤 목록 관심 필터를 build_match_sql로"
```

---

## Task 6: 매처 custom_keywords 직접매칭 통합

**Files:** Modify `backend/app/core/matcher.py` (~1026-1033)

- [ ] **Step 1: 직접매칭을 keyword_hit로 교체**
현재([matcher.py:1028-1033]):
```python
        if custom_kw_list:
            title_lower = title.lower()
            direct_match = [kw for kw in custom_kw_list if kw.lower() in title_lower]
            if direct_match:
                score += min(30.0, len(direct_match) * 15.0)
                reasons.append(f'"{direct_match[0]}" 키워드 직접 매칭')
```
교체(title만→search_text, 토큰화+동의어):
```python
        if custom_kw_list:
            from app.core.keyword_match import keyword_hit
            _ck_text = f"{title} {ad_category or ''} {(ad.get('summary_text') or '')}"
            direct_match = [kw for kw in custom_kw_list if keyword_hit([kw], _ck_text)]
            if direct_match:
                score += min(30.0, len(direct_match) * 15.0)
                reasons.append(f'"{direct_match[0]}" 키워드 직접 매칭')
```
주의: 이 스코프에서 `title`/`ad_category`/`ad`의 실제 변수명을 확인해 정합(주변 코드가 `ad.get(...)`/지역변수 어느 쪽인지 실사 후 맞출 것). `search_text`가 이미 정의돼 있으면 그것을 재사용해도 됨.

- [ ] **Step 2: import·smoke 확인** — `cd backend && python -c "import app.core.matcher"`.

- [ ] **Step 3: Commit**
```
git add backend/app/core/matcher.py
git commit -m "feat(match): 매처 custom_keywords 직접매칭을 토큰화+동의어로"
```

---

## Task 7: 실데이터 검증 + 회귀

**Files:** 없음(검증)

- [ ] **Step 1: 단위 테스트 전체**
Run: `cd backend && python -m pytest test_keyword_match_unit.py -v`
Expected: 전부 PASS.

- [ ] **Step 2: 전체 import·기존 매칭 회귀**
Run: `cd backend && python -c "import app.main; import app.core.matcher; print('OK')"`
기존 매칭 관련 단위테스트가 있으면 실행(예: `python -m pytest test_*match*unit.py -v` 등 존재 시).

- [ ] **Step 3: 실데이터 전후 비교(로컬 스크립트)**
로컬 .env(프로덕션 Supabase)로 "전문기관 모집" 매칭 수를 헬퍼로 계산해 2→~60 개선 확인. 스크래치패드 스크립트:
```python
import os, sys; sys.path.insert(0, "backend")
from dotenv import load_dotenv; load_dotenv("backend/.env")
import psycopg2, psycopg2.extras
from app.core.keyword_match import keyword_hit
conn=psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=psycopg2.extras.RealDictCursor)
cur=conn.cursor(); cur.execute("SELECT title, category, COALESCE(summary_text,'') s FROM announcements WHERE deadline_date IS NULL OR deadline_date>=CURRENT_DATE")
rows=cur.fetchall()
hit=sum(1 for r in rows if keyword_hit(["전문기관 모집"], f"{r['title']} {r['category']} {r['s']}"))
old=sum(1 for r in rows if "전문기관 모집" in (r['title'] or '') or "전문기관 모집" in (r['category'] or ''))
print(f"구(substring): {old}건 / 신(토큰+동의어): {hit}건")
```
Expected: 신 매칭 수가 구 대비 대폭 증가(수십 건).

- [ ] **Step 4: 배포 참고(정렬 반영)**
배치 정렬(Task 3)은 하루 1회 캐시 재계산 시 반영. 즉시 확인하려면 배치 재실행 또는 실시간 경로(캐시 없는 계정)로 확인. 배포는 로컬 검증 후 git push(feature→main ff→push).

---

## Self-Review 메모
- 스펙 커버리지: 헬퍼=Task1, SYNONYM 이관=Task2, 배치=Task3, 실시간=Task4, 맞춤=Task5, 매처custom=Task6, 검증=Task7. 전부 매핑.
- 타입 일관성: `keyword_hit(keywords:list, text:str)->bool` / `build_match_sql(keywords:list, field_expr:str)->(sql|None, params)` — 전 사이트 동일 시그니처.
- 회귀 주의: SYNONYM_MAP 이관 후 matcher 기존 사용처(701·1342) 값 동일. 배치 SELECT에 summary_text 추가 시 dict 접근(`ann.get('summary_text')`) 정합.
- 실사 필요(구현자): Task6의 `title/ad_category/ad/search_text` 실제 변수명, Task4의 bucket_params 개수 정합.
