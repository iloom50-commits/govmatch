# 관심/키워드 매칭 토큰화 + 동의어 (공용 헬퍼) — 설계서

- 작성일: 2026-07-22
- 목표: 사용자가 입력한 관심/키워드("전문기관 모집" 등)를 **의미에 가깝게 인식**해 관련 공고를 찾도록, 매칭을 **부분문자열 → 토큰화 + 핵심 동의어**로 개선. 정렬·매칭 여러 곳에 흩어진 로직을 **단일 공용 헬퍼**로 통일.
- 채택안: (D) A(토큰화) + B(동의어 사전). (C) 임베딩은 별도 — 기존 섀도우 하네스로 측정 후 결정.

## 문제 (실데이터 검증됨)

현재 관심/키워드 매칭은 순수 부분문자열(`keyword in title/category`)이라 입력 글자가 통째로 들어간 공고만 잡는다.
- 활성 공고 21,587건 기준, **관심 키워드 "전문기관 모집" → 단 2건** 매칭.
- 실제 관련: 제목 '전문기관' 19 · '수행기관' 26 · '운영기관' 20 · '전담기관'/'주관기관' 2/6 → **~60건 이상을 놓침**.
- 원인: ① 토큰 분리 안 함(구절 통째 매칭) ② 동의어(수행/운영/전담기관) 인식 못 함 ③ 변형(모집/지정/선정/공모) 구분.
- 참고: **검색**은 이미 공백 토큰화(AND)로 "전문기관 모집" → 10건을 잘 찾음([main.py:3543-3546](backend/app/main.py#L3543)). 관심 매칭만 우둔한 substring.

## 확정된 설계 결정

1. **적용 범위**: 공용 헬퍼로 전체 통일 — 관심/키워드 매칭하는 모든 곳이 동일 함수 사용(어디서든 같은 품질).
2. **동의어 범위**: 핵심 집단만, 데이터기반 — 기관族·모집族부터. 이후 데이터로 확장(YAGNI).

## 매칭 규칙 (3단 위계)

여러 관심 키워드 리스트에 대해:
- **키워드 간 OR** (관심사 중 하나라도 맞으면 hit)
- **키워드 내 토큰 간 AND** (공백 분리 — "전문기관 모집" = 전문기관 AND 모집)
- **토큰의 동의어 간 OR** (사전에 있으면 확장)

예) "전문기관 모집" →
```
(F ILIKE %전문기관% OR %수행기관% OR %운영기관% OR %전담기관% OR %주관기관%)
AND
(F ILIKE %모집% OR %지정% OR %선정% OR %공모%)
```
- 사전에 없는 단어(예 "바이오")는 동의어 확장 없이 그 토큰만 매칭 → **모든 키워드가 최소한 토큰 매칭은 됨**(현 substring보다 이미 개선).
- 매칭 필드 F = `title + category + summary_text` (검색은 department도 보지만, 관심 매칭은 노이즈 축소 위해 3필드).

## 신규 모듈 `backend/app/core/keyword_match.py`

```python
# 동의어 그룹(족). 대칭 확장은 그룹 멤버 전체로.
SYNONYM_GROUPS: list[list[str]] = [
    ["전문기관", "수행기관", "운영기관", "전담기관", "주관기관"],
    ["모집", "지정", "선정", "공모"],
]
```

- `expand_token(token: str) -> list[str]`: 토큰이 속한 그룹이 있으면 그룹 전체(자기 포함), 없으면 `[token]`.
- `tokenize(keyword: str) -> list[str]`: `keyword.strip().split()` (공백 분리). 빈 문자열 토큰 제거.
- `keyword_hit(keywords: list[str], text: str) -> bool`: (파이썬용 — 배치 루프에서 사용)
  - text 소문자화. 각 keyword: 각 token을 expand → 동의어 중 하나라도 text에 포함이면 그 토큰 hit; **모든 토큰 hit**이면 keyword hit(AND). **하나의 keyword라도 hit**이면 True(OR).
- `build_match_sql(keywords: list[str], field_expr: str) -> tuple[str | None, list]`: (SQL용 — 실시간/맞춤 경로)
  - `field_expr` = 이미 조립된 필드 표현식(예 `"(title || ' ' || COALESCE(category,'') || ' ' || COALESCE(summary_text,''))"`).
  - 각 keyword: 각 token → `(field ILIKE %s OR field ILIKE %s ...)`(동의어들); 토큰 간 AND; keyword 간 OR.
  - 반환: `(sql_fragment, params)` — keywords 비면 `(None, [])`(호출자가 처리).

빈 keywords·공백만 입력 등 방어. 순수 함수(DB·IO 없음) → 단위 테스트 용이.

## 통합 지점 (전부 헬퍼로 교체)

1. **배치** `_compute_public_order_for_user` ([main.py:1081](backend/app/main.py#L1081)) — `interest_hit` 계산을 `keyword_hit(interests, f"{title} {category} {summary_text}")`로. **필드 정합성**: 배치 SELECT([main.py:980](backend/app/main.py#L980))에 `summary_text`가 없으면 추가(SQL 경로와 동일한 title+category+summary 3필드로 통일).
2. **실시간 public** ([main.py:3250](backend/app/main.py#L3250)) — `interest_sql`/`interest_params`를 `build_match_sql`로.
3. **맞춤 목록** ([main.py:3533](backend/app/main.py#L3533)) — `kw_parts`를 `build_match_sql`로.
4. **매처 custom_keywords** ([matcher.py:1027](backend/app/core/matcher.py#L1027) 등) — 사용자 자유입력 키워드("전문기관 모집")가 들어오는 곳. custom_keywords의 substring 매칭을 헬퍼로 교체. (정확한 사이트는 구현 계획 단계에서 matcher.py의 708·1027·1327·1346·1684를 실사해 확정.)

> 각 사이트는 역할이 다름(불리언 hit / WHERE 조각 / 점수). 헬퍼는 `keyword_hit`(bool)와 `build_match_sql`(SQL 조각) 둘 다 제공해 사이트별로 알맞게 사용.

## 검증

### 단위 (TDD)
- `keyword_hit(["전문기관 모집"], "2026 수행기관 지정 공고")` == True (양 토큰 동의어 매칭)
- `keyword_hit(["전문기관 모집"], "청년 창업 지원사업")` == False
- `keyword_hit(["바이오"], "바이오헬스 창업")` == True (사전 밖 단어도 토큰 매칭)
- `tokenize("전문기관 모집")` == ["전문기관","모집"]; `expand_token("수행기관")` 그룹 전체 포함
- `build_match_sql(["전문기관 모집"], F)` → 토큰 2개·동의어 OR·토큰 AND 구조 + 파라미터 수 정확
- 빈 입력 방어: `keyword_hit([], x)` False; `build_match_sql([], F)` == (None, [])

### 실데이터 (통합)
- 통일 후 "전문기관 모집" 관심 매칭 **2건 → ~60건** 전후 비교(마스터 계정). 정렬 반영은 **배치 캐시 재계산 필요**(검증 시 강제 재배치 또는 실시간 경로로 확인).
- 회귀: 기존 관심 매칭이 깨지지 않는지(예 "창업" 단일 키워드 결과 수 유사).

## 리스크 / 경계 (정직)

- **과확장**: 단일 일반 토큰(예 "모집"만) 입력 시 광범위 매칭 — 단, 다토큰 AND라 "전문기관 모집"은 기관族으로 적절히 좁혀짐. 기존 substring도 동일 한계라 악화 아님.
- **배치 지연**: 정렬은 하루 1회 배치라 개선 반영에 캐시 재계산 필요.
- **성능**: ILIKE OR 증가 → 실시간 경로 약간 느려짐(허용 범위, 이미 seq scan).
- **동의어 유지보수**: 사전은 소규모 상수로 시작. 확장은 데이터 기반 후속.

## 범위 밖
- (C) 임베딩 의미검색 — 기존 섀도우 하네스(`EMBEDDING_MATCHING_MODE=shadow`)로 측정 후 별도 결정.
- 동의어 사전 대규모 구축 — 후속.
