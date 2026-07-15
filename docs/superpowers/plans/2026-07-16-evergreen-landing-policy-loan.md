# 에버그린 랜딩(소상공인정책자금) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "소상공인정책자금" 검색자를 잡는 에버그린 가이드 랜딩(`/guide/소상공인-정책자금`)을 SSR로 신설한다.

**Architecture:** Next.js App Router 서버컴포넌트 1개(`guide/[slug]/page.tsx`) + slug→콘텐츠 매핑 모듈. 가이드 본문은 정적(코드 내), 라이브 공고는 기존 `/api/announcements/public`을 서버사이드 fetch. 백엔드 무변경. 기존 Toss-블루 Tailwind 클래스 재사용.

**Tech Stack:** Next.js(App Router, RSC, ISR), TypeScript, Tailwind. 백엔드 FastAPI(호출만).

**참조 스펙:** `docs/superpowers/specs/2026-07-16-evergreen-landing-policy-loan-design.md`

**공통 규칙:** 커밋은 브랜치 `feat/evergreen-landing-policy-loan`. 검증은 프런트 특성상 `npm run build` + `curl -A Googlebot`로 SSR HTML에 실제 텍스트가 있는지 확인(정적분석 아닌 실측). 최종 배포는 main 머지·push(Vercel).

---

### Task 1: 가이드 콘텐츠 모듈 (slug→콘텐츠 매핑)

**Files:**
- Create: `frontend/src/app/guide/content.ts`

콘텐츠 구조를 타입으로 정의하고 소상공인정책자금 1건을 채운다. 본문 산문은 일반적으로 확립된 사실(소진공 직접/대리대출 구조, 자격 개념)로 작성하되, **연도별로 변동하는 구체 금리·한도 수치는 넣지 않고** `numericsToVerify` 필드에 "대표 검수 시 소진공 공고 기준으로 채울 항목"으로 남긴다(추측 금지 — 이 값들은 Task 6 검수 게이트에서 확정).

- [ ] **Step 1: 콘텐츠 타입 + 데이터 작성**

```ts
// frontend/src/app/guide/content.ts
export interface GuideFAQ { q: string; a: string; }
export interface GuideContent {
  slug: string;
  keyword: string;              // 대표 키워드(메타·H1용)
  h1: string;
  title: string;                // <title>용(브랜드 접미사 없이 — 루트 template이 붙임)
  description: string;          // 150자 내
  intro: string;
  sections: { id: string; h2: string; body: string[] }[];  // body = 문단 배열
  faqs: GuideFAQ[];
  liveFilter: { param: "category" | "search"; value: string }; // Task 3에서 확정
  numericsToVerify: string[];   // 대표 검수 대상(금리/한도 등)
}

export const GUIDES: Record<string, GuideContent> = {
  "소상공인-정책자금": {
    slug: "소상공인-정책자금",
    keyword: "소상공인정책자금",
    h1: "소상공인 정책자금 총정리 — 자격·종류·금리·신청방법 (2026)",
    title: "소상공인 정책자금 총정리 — 자격·종류·신청방법",
    description: "소상공인 정책자금의 종류(직접대출·대리대출), 자격요건, 금리, 신청 절차를 정리했습니다. 지금 신청 가능한 공고도 함께 확인하세요.",
    intro: "정책자금은 정부·공공기관이 소상공인에게 낮은 금리로 지원하는 융자입니다. 일반 대출과 무엇이 다른지, 어떤 종류가 있고 어떻게 신청하는지 한 번에 정리했습니다.",
    sections: [
      { id: "what", h2: "정책자금이란? 일반 대출과의 차이", body: [
        "정책자금은 소상공인시장진흥공단(소진공) 등 공공기관 재원으로, 시중 대출보다 낮은 금리와 완화된 조건으로 제공되는 융자입니다.",
        "일반 은행 대출과 달리 정책 목적(창업·경영안정·재도전 등)에 따라 자금 종류가 나뉘고, 자격 요건을 충족해야 신청할 수 있습니다."
      ]},
      { id: "types", h2: "정책자금의 종류와 집행기관", body: [
        "소진공 직접대출: 소진공이 직접 심사·대출하는 방식입니다.",
        "소진공 대리대출: 소진공이 보증·이차보전하고 시중은행이 실행하는 방식입니다.",
        "지역신용보증재단 보증부 대출, 지자체 이차보전 사업도 있습니다.",
        "참고로 규모가 더 큰 중소기업은 중소벤처기업진흥공단(중진공)의 정책자금(창업기반·신성장기반 등)을 이용하며, 이는 소상공인 정책자금과 대상·한도가 다릅니다."
      ]},
      { id: "eligible", h2: "자격요건 (소상공인·개인사업자 기준)", body: [
        "업종별 상시근로자 수 기준(예: 제조업 10인 미만, 서비스업 5인 미만 등)을 충족하는 소상공인이 대상입니다.",
        "개인사업자·법인 모두 신청 가능하며, 업력·업종에 따라 이용 가능한 자금 종류가 달라집니다.",
        "일부 업종(사행성·유흥 등)은 지원에서 제외됩니다."
      ]},
      { id: "rate", h2: "한도·금리", body: [
        "자금 종류에 따라 한도와 금리가 다르며, 금리는 분기별 정책자금 기준금리에 연동되어 변동됩니다.",
        "최신 한도·금리는 소진공 공고 기준으로 확인해야 합니다(연도·분기별 변동)."
      ]},
      { id: "how", h2: "신청 절차와 필요서류", body: [
        "온라인 신청은 소상공인정책자금 사이트(ols.semas.or.kr)를 통해 진행합니다.",
        "사업자등록증, 소상공인 확인서, 재무 관련 서류 등이 필요하며 자금 종류별로 다릅니다.",
        "예산 소진 시 조기 마감되므로 공고 기간을 확인해 신청하는 것이 중요합니다."
      ]},
      { id: "mistakes", h2: "흔한 실수와 탈락 사유", body: [
        "자격 요건(업종·상시근로자 수) 미확인, 제외 업종 여부 미확인이 대표적입니다.",
        "폐업 예정이거나 세금 체납이 있으면 제한될 수 있습니다(폐업 시에는 별도의 폐업지원·재도전 사업을 확인하세요)."
      ]},
    ],
    faqs: [
      { q: "직접대출과 대리대출의 차이는?", a: "직접대출은 소진공이 직접 심사·실행하고, 대리대출은 소진공 보증 아래 시중은행이 실행합니다. 자금 종류와 신청 조건이 다릅니다." },
      { q: "개인사업자도 신청할 수 있나요?", a: "네. 소상공인 요건(업종별 상시근로자 수 등)을 충족하는 개인사업자·법인 모두 신청 가능합니다." },
      { q: "온라인으로 신청하나요?", a: "소상공인정책자금 사이트(ols.semas.or.kr)에서 온라인 신청합니다. 자금별로 필요서류가 다릅니다." },
      { q: "금리는 어떻게 정해지나요?", a: "분기별 정책자금 기준금리에 자금 종류별 가산·차감이 적용됩니다. 최신 금리는 소진공 공고를 확인하세요." },
      { q: "중진공 정책자금과 다른가요?", a: "네. 소상공인 정책자금은 소진공, 중진공 정책자금은 중소벤처기업진흥공단이 운영하며 대상 기업 규모와 한도가 다릅니다." },
    ],
    liveFilter: { param: "search", value: "정책자금" },  // Task 3에서 category 값 확인 후 확정
    numericsToVerify: [
      "자금 종류별 최대 한도(직접대출/대리대출/재도전 등)",
      "2026년 분기 정책자금 기준금리 및 자금별 가산·차감",
      "업종별 상시근로자 수 기준 최신값",
    ],
  },
};

export function getGuide(slug: string): GuideContent | null {
  return GUIDES[slug] ?? null;
}
```

- [ ] **Step 2: 타입체크 통과 확인**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음(content.ts 타입 정합).

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/app/guide/content.ts
git commit -m "feat(guide): 소상공인정책자금 가이드 콘텐츠 모듈"
```

---

### Task 2: 랜딩 라우트 (SSR 본문 + 메타 + JSON-LD)

**Files:**
- Create: `frontend/src/app/guide/[slug]/page.tsx`

기존 `announcements/[id]/page.tsx`의 서버컴포넌트·generateMetadata·JSON-LD 패턴을 그대로 따른다. 라이브 공고 섹션은 Task 3에서 붙이므로 이 태스크에서는 자리(주석)만 두고 가이드 본문까지 렌더한다.

- [ ] **Step 1: 페이지 컴포넌트 작성**

```tsx
// frontend/src/app/guide/[slug]/page.tsx
import type { Metadata } from "next";
import { getGuide } from "../content";

export const revalidate = 3600;

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const g = getGuide(decodeURIComponent(slug));
  if (!g) return { title: "가이드를 찾을 수 없습니다", robots: { index: false } };
  return {
    title: g.title,   // 루트 layout template("%s | 지원금AI")이 접미사 부착 — 여기서 안 붙임
    description: g.description,
    alternates: { canonical: `https://www.govmatch.kr/guide/${g.slug}` },
    openGraph: { title: g.h1, description: g.description, type: "article",
      url: `https://www.govmatch.kr/guide/${g.slug}` },
    robots: { index: true, follow: true },
  };
}

export default async function GuidePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const g = getGuide(decodeURIComponent(slug));
  if (!g) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-xl font-bold text-slate-800 mb-2">가이드를 찾을 수 없습니다</h1>
          <a href="/" className="text-indigo-600 hover:underline">메인으로 이동</a>
        </div>
      </div>
    );
  }

  const faqLd = {
    "@context": "https://schema.org", "@type": "FAQPage",
    mainEntity: g.faqs.map((f) => ({ "@type": "Question", name: f.q,
      acceptedAnswer: { "@type": "Answer", text: f.a } })),
  };
  const crumbLd = {
    "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "지원금AI", item: "https://www.govmatch.kr" },
      { "@type": "ListItem", position: 2, name: "가이드", item: "https://www.govmatch.kr/guide" },
      { "@type": "ListItem", position: 3, name: g.keyword, item: `https://www.govmatch.kr/guide/${g.slug}` },
    ],
  };

  return (
    <main className="min-h-screen bg-white">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqLd) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(crumbLd) }} />

      <div className="max-w-3xl mx-auto px-4 py-8">
        <nav className="text-[13px] text-slate-400 mb-4">
          <a href="/" className="hover:text-blue-600">지원금AI</a> › 가이드 › <span className="text-slate-600">{g.keyword}</span>
        </nav>

        <h1 className="text-[26px] md:text-[30px] font-bold text-slate-900 leading-snug mb-3">{g.h1}</h1>
        <p className="text-[16px] text-slate-600 mb-6">{g.intro}</p>

        {/* 목차 */}
        <div className="bg-slate-50 rounded-xl p-4 mb-8">
          <p className="text-[13px] font-bold text-slate-400 mb-2">목차</p>
          <ul className="space-y-1">
            {g.sections.map((s) => (
              <li key={s.id}><a href={`#${s.id}`} className="text-[14px] text-blue-600 hover:underline">{s.h2}</a></li>
            ))}
          </ul>
        </div>

        {/* 본문 */}
        {g.sections.map((s) => (
          <section key={s.id} id={s.id} className="mb-8 scroll-mt-20">
            <h2 className="text-[20px] font-bold text-slate-900 mb-3">{s.h2}</h2>
            {s.body.map((p, i) => (
              <p key={i} className="text-[15px] text-slate-700 leading-relaxed mb-2">{p}</p>
            ))}
          </section>
        ))}

        {/* 라이브 공고 섹션 — Task 3에서 삽입 */}

        {/* FAQ */}
        <section className="mb-8">
          <h2 className="text-[20px] font-bold text-slate-900 mb-4">자주 묻는 질문</h2>
          {g.faqs.map((f, i) => (
            <div key={i} className="border-b border-slate-100 py-3">
              <p className="text-[15px] font-semibold text-slate-900 mb-1">Q. {f.q}</p>
              <p className="text-[15px] text-slate-700 leading-relaxed">{f.a}</p>
            </div>
          ))}
        </section>

        {/* CTA */}
        <div className="bg-blue-600 rounded-2xl p-6 text-center">
          <p className="text-[18px] font-bold text-white mb-1">내 조건에 맞는 정책자금, 30초 만에</p>
          <p className="text-[14px] text-blue-100 mb-4">업종·지역·매출을 입력하면 AI가 맞춤 공고를 찾아드립니다.</p>
          <a href="/?q=소상공인+정책자금" className="inline-block bg-white text-blue-600 font-bold px-6 py-3 rounded-xl">맞춤 지원금 찾기 →</a>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 2: 빌드 통과 확인**

Run: `cd frontend && npm run build`
Expected: 컴파일 성공, 라우트 목록에 `/guide/[slug]` 표시.

- [ ] **Step 3: 로컬 SSR 실측 (크롤러 시점 본문 존재)**

Run:
```bash
cd frontend && npx next start -p 3100 &
sleep 4
curl -s -A "Googlebot" "http://localhost:3100/guide/소상공인-정책자금" | grep -oE "정책자금이란|자주 묻는 질문|application/ld\+json" | sort | uniq -c
```
Expected: H2 텍스트("정책자금이란…")·"자주 묻는 질문"·`application/ld+json` 이 HTML에 존재(스켈레톤 아님).

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/app/guide/[slug]/page.tsx
git commit -m "feat(guide): 소상공인정책자금 랜딩 라우트(SSR 본문·메타·JSON-LD)"
```

---

### Task 3: 라이브 공고 섹션 (기존 public API 서버 fetch)

**Files:**
- Modify: `frontend/src/app/guide/[slug]/page.tsx` (라이브 공고 자리에 삽입)

- [ ] **Step 1: 실제 category 값 분포 확인 후 필터 확정**

Run:
```bash
curl -s "https://www.govmatch.kr/api/announcements/public?target_type=business&search=정책자금&size=10" | python -c "import sys,json;d=json.load(sys.stdin);print('건수:',len(d.get('data',d.get('announcements',[]))));[print(a.get('title'),'|',a.get('category')) for a in (d.get('data',d.get('announcements',[]))[:10])]"
```
Expected: 정책자금 관련 공고 목록. category 값이 일관된 "정책자금"이면 content.ts의 liveFilter를 `{param:'category', value:'정책자금'}`로 변경, 아니면 `search=정책자금` 유지. 응답 키(`data` vs `announcements`)도 여기서 확정.

- [ ] **Step 2: 서버 fetch 헬퍼 + 렌더 삽입**

`page.tsx`의 컴포넌트 상단(본문 렌더 전)에서 fetch하고, "라이브 공고 섹션 — Task 3에서 삽입" 주석 위치에 렌더한다.

```tsx
// GuidePage 함수 내 상단, getGuide 이후
const API = process.env.NEXT_PUBLIC_API_URL || "https://www.govmatch.kr";
let live: any[] = [];
try {
  const qs = g.liveFilter.param === "category"
    ? `category=${encodeURIComponent(g.liveFilter.value)}`
    : `search=${encodeURIComponent(g.liveFilter.value)}`;
  const r = await fetch(`${API}/api/announcements/public?target_type=business&size=8&${qs}`,
    { next: { revalidate: 3600 } });
  if (r.ok) { const d = await r.json(); live = d.data ?? d.announcements ?? []; }
} catch { live = []; }
```

```tsx
{/* 라이브 공고 섹션 주석을 아래로 교체 */}
{live.length > 0 && (
  <section className="mb-8">
    <h2 className="text-[20px] font-bold text-slate-900 mb-4">지금 신청 가능한 정책자금 공고</h2>
    <ul className="space-y-2">
      {live.map((a: any) => (
        <li key={a.announcement_id}>
          <a href={`/announcements/${a.announcement_id}`}
             className="block border border-slate-200 rounded-xl px-4 py-3 hover:border-blue-400 transition-colors">
            <span className="text-[15px] font-semibold text-slate-900">{a.title}</span>
            {a.department && <span className="block text-[13px] text-slate-500 mt-0.5">{a.department}</span>}
          </a>
        </li>
      ))}
    </ul>
  </section>
)}
```

- [ ] **Step 3: 빌드 + 라이브 공고 렌더 실측**

Run: `cd frontend && npm run build` → 성공.
로컬 start 후 `curl -s -A Googlebot "http://localhost:3100/guide/소상공인-정책자금" | grep -c "announcements/"`
Expected: 내부링크(`/announcements/{id}`)가 1개 이상 존재(백엔드 정상 시). 백엔드 장애 시 섹션 숨김 + 페이지 정상.

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/app/guide/[slug]/page.tsx frontend/src/app/guide/content.ts
git commit -m "feat(guide): 라이브 정책자금 공고 섹션(공고 내부링크)"
```

---

### Task 4: sitemap 등록

**Files:**
- Modify: `frontend/src/app/sitemap.ts`

- [ ] **Step 1: /guide URL 추가**

기존 정적 페이지 배열에 항목 추가(기존 패턴 그대로, priority 0.8):

```ts
// 정적 페이지 배열에 추가
{ url: `${BASE}/guide/소상공인-정책자금`, changeFrequency: "monthly", priority: 0.8 },
```
(변수명 `BASE`/필드는 기존 sitemap.ts 관행에 맞춰 조정.)

- [ ] **Step 2: sitemap 출력 확인**

Run: `cd frontend && npm run build` 후 로컬 start → `curl -s http://localhost:3100/sitemap.xml | grep guide`
Expected: `/guide/소상공인-정책자금`(URL 인코딩 형태) 포함.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/app/sitemap.ts
git commit -m "feat(guide): sitemap에 가이드 랜딩 등록"
```

---

### Task 5: 배포 + 라이브 검증

- [ ] **Step 1: main 머지·push**

```bash
git checkout main && git merge feat/evergreen-landing-policy-loan && git push origin main
```

- [ ] **Step 2: 배포 반영 후 라이브 SSR 실측**

Run(반영까지 폴링):
```bash
curl -s -A "Googlebot" "https://www.govmatch.kr/guide/소상공인-정책자금" | grep -oE "<title>[^<]*</title>|정책자금이란|자주 묻는 질문"
```
Expected: 고유 title("소상공인 정책자금 총정리 … | 지원금AI"), 본문 H2, FAQ 텍스트 존재. noindex 아님.

- [ ] **Step 3: 대표에게 GSC 색인 요청 안내**

GSC URL 검사 → `https://www.govmatch.kr/guide/소상공인-정책자금` → 색인 생성 요청. (대표 수행)

---

### Task 6: 콘텐츠 정확성 검수 게이트 (대표 수행 — 발행 전 필수)

**목적:** `numericsToVerify`(금리·한도·상시근로자 기준)는 연도별 변동이라 AI가 임의로 못 채운다. 대표가 소진공 최신 공고 기준으로 확인 후 채운다.

- [ ] **Step 1:** content.ts의 `numericsToVerify` 항목을 소진공 공고 기준 실제 수치로 확정, 해당 문장을 구체 수치로 갱신.
- [ ] **Step 2:** 자격·제외업종 서술이 최신 기준과 맞는지 대표 검토.
- [ ] **Step 3:** 반영 커밋 후 재배포.

> 이 게이트를 통과해야 "발행 완료"다. 검수 전에는 일반적 서술만 노출(부정확 수치 없음).

---

## Self-Review (작성자 점검)
- **스펙 커버리지:** URL/구조/SSR/JSON-LD/메타/라이브공고/sitemap/콘텐츠검수/디자인토큰 재사용 — 각 Task로 매핑됨. 중진공 흡수·연관어 소제목 = Task 1 sections에 반영.
- **플레이스홀더:** 콘텐츠 산문은 실제 작성됨. 연도변동 수치만 Task 6 검수 게이트로 분리(추측 금지 — 정당한 사유).
- **타입 정합:** GuideContent 필드(getGuide·liveFilter·faqs)가 Task 2·3에서 사용하는 이름과 일치.
- **필터 미확정 1건:** liveFilter param(category vs search)은 Task 3 Step 1에서 실데이터로 확정(백엔드 무변경이라 리스크 없음).
