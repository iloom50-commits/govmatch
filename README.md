# AI 맞춤 정부지원금 매칭

사업자등록번호 입력만으로 기업 프로필을 분석하고, 5,000개 이상의 정부 지원사업 공고 중에서 AI가 최적의 매칭 결과를 제공하는 서비스입니다.

## 주요 기능

- **AI 기업 분석** — 사업자등록번호 기반 기업 프로필 자동 구성 및 KSIC 업종 추천
- **하이브리드 매칭 엔진** — SQL 필터링 + Rule Engine + Gemini AI 심층 분석
- **공공 API 연동** — K-Startup, 기업마당, 중소벤처24, 과기부 R&D 등 8개 API
- **웹 스크래핑** — SBC(중진공) + 관리자 수동 URL 등록을 통한 추가 데이터 수집
- **알림 서비스** — 이메일 다이제스트 + 웹 푸시 알림
- **관리자 대시보드** — 데이터 소스 관리, 사용자 관리, 수동 동기화

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | Python, FastAPI, SQLite, Uvicorn |
| Frontend | Next.js 16, React 19, TypeScript, TailwindCSS 4 |
| AI | Google Gemini 2.0 Flash |
| Scraping | Playwright, BeautifulSoup |
| Push | Web Push (VAPID), pywebpush |

## 프로젝트 구조

```
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 엔트리포인트
│   │   ├── config.py                # DB 경로 등 중앙 설정
│   │   ├── core/
│   │   │   ├── matcher.py           # 하이브리드 매칭 엔진
│   │   │   ├── ai_matcher.py        # AI 심층 매칭
│   │   │   ├── ai_parser.py         # AI 공고 파싱
│   │   │   └── url_checker.py       # URL 중복 검사
│   │   └── services/
│   │       ├── public_api_service.py # 공공 API 통합
│   │       ├── sync_service.py      # 데이터 동기화 오케스트레이터
│   │       ├── ai_service.py        # Gemini AI 서비스
│   │       ├── notification_service.py # 이메일/푸시 알림
│   │       ├── admin_scraper.py     # 수동 URL 스크래핑
│   │       ├── rule_engine.py       # 규칙 기반 필터링
│   │       └── scrapers/
│   │           └── sbc.py           # 중진공 스크래퍼
│   ├── .env                         # 환경변수 (비공개)
│   ├── .env.example                 # 환경변수 템플릿
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx             # 메인 페이지
│   │   │   ├── layout.tsx           # 레이아웃 + SEO
│   │   │   └── admin/page.tsx       # 관리자 대시보드
│   │   └── components/
│   │       ├── Dashboard.tsx        # 매칭 결과 대시보드
│   │       ├── ResultCard.tsx       # 공고 카드
│   │       ├── OnboardingWizard.tsx # 기업 정보 입력
│   │       ├── ProfileSettings.tsx  # 프로필 수정
│   │       └── NotificationModal.tsx # 알림 설정
│   └── public/sw.js                 # 푸시 서비스 워커
└── .gitignore
```

## 설치 및 실행

### 1. 환경변수 설정

```bash
cd backend
cp .env.example .env
# .env 파일을 열어 API 키 등을 입력
```

### 2. 백엔드

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

- 프론트엔드: http://localhost:3000
- 백엔드 API: http://localhost:8000
- 관리자 페이지: http://localhost:3000/admin

## 필수 API 키

| 키 | 발급처 | 용도 |
|----|--------|------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com) | AI 매칭 분석 |
| `PUBLIC_DATA_PORTAL_KEY` | [data.go.kr](https://data.go.kr) | K-Startup, 과기부 R&D 등 |
| `BIZINFO_PORTAL_KEY` | [bizinfo.go.kr](https://www.bizinfo.go.kr) | 기업마당 공고 |
| `ADMIN_PASSWORD` | 직접 설정 | 관리자 페이지 인증 |

선택 API 키와 VAPID 키는 `.env.example` 참고.
