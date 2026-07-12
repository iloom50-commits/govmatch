# 03 LITE 보고서 생성 — 상세 설계

---

## 1. 미션

> **LITE 상담 내용을 유저 본인이 보관·참고할 수 있는 간단 요약 문서로 정리한다.**

---

## 2. 트리거

**수동 버튼**: 상담 화면 상단 `📄 보고서 만들기` 클릭

---

## 3. 포맷

- **1~2페이지 간단 요약**
- 웹 페이지 + PDF 다운로드
- 내 상담 기록으로 저장 (재조회)

---

## 4. 템플릿 구조

```markdown
# 지원금AI 상담 보고서

**상담일**: {date}
**고객**: {user_name_or_email}
**상담 주제**: {topic}  (공고상담 / 정책자금 상담)

---

## 1. 상담 요약 (3줄)
{ai_3line_summary}

## 2. 내 프로필
- 업종/연령: ...
- 지역: ...
- 관심 분야: ...

## 3. 검토한 지원사업
{for each ann in mentioned_announcements}
### 공고명
- 지원 금액: ...
- 자격 요건: ...
- 판정: 해당 / 조건부 / 미해당
- 근거: ...

## 4. 다음 단계
1. {next_action_1}
2. {next_action_2}

## 5. 문의처
- 주관기관: {department}
- 연락처: {tel}

---
이 보고서는 지원금AI가 자동 생성했습니다. 최신 정보는 공고 원문을 확인하세요.
```

---

## 5. 데이터 소스 (07_data_flow §5 참조)

| 섹션 | 소스 |
|---|---|
| 상담 요약 | Gemini 단일 호출 (messages 요약) |
| 내 프로필 | `users` 테이블 |
| 검토한 지원사업 | 대화 중 언급된 announcement_id (regex 추출) |
| 자격 판정 | 대화의 verdict 필드 |
| 다음 단계 | AI가 생성한 action 목록 |
| 문의처 | `announcements.department` + 기관 대표번호 DB |

---

## 6. 생성 파이프라인

```python
def generate_lite_report(session_id, db_conn):
    # 1. 세션 대화 + 언급된 공고 수집
    messages = fetch_messages(session_id)
    mentioned_anns = extract_announcement_ids(messages)

    # 2. 프로필 조회
    profile = fetch_user_profile(session_id)

    # 3. 공고 상세 조회
    ann_details = [fetch_announcement(aid) for aid in mentioned_anns]

    # 4. Gemini 1회 호출 — 전체 대화·공고·프로필을 요약·구조화
    report_data = gemini_summarize(messages, profile, ann_details)

    # 5. Jinja2 템플릿 렌더
    html = render_template("lite_brief.j2", report_data)

    # 6. PDF 변환 (weasyprint)
    pdf_bytes = html_to_pdf(html)

    # 7. DB 저장
    save_to_client_reports(session_id, pdf_bytes, html)

    return {"html": html, "pdf_url": ...}
```

---

## 7. API

```
POST /api/lite/reports/generate
  body: {session_id}
  response: {report_id, html, pdf_url}

GET /api/lite/reports
  response: [{report_id, date, topic, preview}, ...]

GET /api/lite/reports/{report_id}
  response: {html, pdf_url}

GET /api/lite/reports/{report_id}/pdf
  response: PDF 파일 스트림
```

---

## 8. 프론트엔드

- 상담 화면 상단 `📄 보고서 만들기` 버튼
- 클릭 → 로딩 (5~10초) → 미리보기 모달 → 다운로드/이메일
- "내 상담 기록" 메뉴에서 재조회

---

## 9. 리스크

- 대화가 짧으면 (2~3턴) 보고서 의미 없음 → **최소 3턴 이상일 때만 버튼 활성화**
- PDF 한글 폰트 이슈 → Noto Sans KR 번들
