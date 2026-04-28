import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: "#2563eb",
};

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "지원금AI — 내 지원금 찾기 30초",
    template: "%s | 지원금AI",
  },
  description: "찾지말고, 받으세요.",
  keywords: ["지원금AI", "정부지원금", "보조금", "정책자금", "중소기업지원", "소상공인지원", "창업지원", "개인복지", "AI매칭", "지원금찾기", "정부보조금", "소상공인정책자금", "청년지원금", "전세자금대출", "R&D지원"],
  manifest: "/manifest.json",
  metadataBase: new URL("https://www.govmatch.kr"),
  alternates: {
    canonical: "https://www.govmatch.kr",
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: "https://www.govmatch.kr",
    siteName: "지원금AI",
    title: "지원금AI — 내 지원금 찾기 30초",
    description: "찾지말고, 받으세요.",
    images: [
      {
        url: "/og-image-wide-v2.png",
        width: 1200,
        height: 630,
        alt: "지원금AI — AI 정부 지원금 자동 매칭",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "지원금AI — 내 지원금 찾기 30초",
    description: "찾지말고, 받으세요.",
    images: ["/og-image-wide-v2.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  verification: {
    google: "u3SIJ5Y_wqzTLLCOwPCzh4r1h8JRLj-WBemyH6nKml8",
    other: {
      "naver-site-verification": "00bdd6b3ada570ff91546b15bbb1743a73b83158",
    },
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "지원금AI",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://govmatch-production.up.railway.app" crossOrigin="anonymous" />
        <link rel="dns-prefetch" href="https://govmatch-production.up.railway.app" />
        <link rel="preconnect" href="https://t1.kakaocdn.net" crossOrigin="anonymous" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        {/* Google Analytics 4 */}
        {process.env.NEXT_PUBLIC_GA_ID && (
          <>
            <script async src={`https://www.googletagmanager.com/gtag/js?id=${process.env.NEXT_PUBLIC_GA_ID}`} />
            <script
              dangerouslySetInnerHTML={{
                __html: `
                  window.dataLayer = window.dataLayer || [];
                  function gtag(){dataLayer.push(arguments);}
                  gtag('js', new Date());
                  gtag('config', '${process.env.NEXT_PUBLIC_GA_ID}', {
                    page_title: document.title,
                    send_page_view: true
                  });
                `,
              }}
            />
          </>
        )}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              // ── 카톡 인앱 → 외부 브라우저 자동 전환 (Android만, iOS는 시스템 제약으로 불가) ──
              (function(){
                try {
                  var ua = navigator.userAgent || '';
                  var isKakao = /KAKAOTALK/i.test(ua);
                  var isAndroid = /Android/i.test(ua);
                  if (!isKakao || !isAndroid) return;
                  // 제외 경로: 결제/OAuth 콜백 등 세션 민감 페이지
                  var path = location.pathname || '/';
                  var skip = /^\\/(payment|auth\\/callback|api\\/auth)/.test(path);
                  if (skip) return;
                  // 무한 루프 방지 — 세션당 1회만
                  if (sessionStorage.getItem('ext_redirect_tried') === '1') return;
                  sessionStorage.setItem('ext_redirect_tried', '1');
                  // Chrome intent URL로 즉시 전환
                  var url = 'www.govmatch.kr' + path + (location.search || '') + (location.hash || '');
                  location.href = 'intent://' + url + '#Intent;scheme=https;package=com.android.chrome;end';
                } catch(_) {}
              })();

              window.__pwaPrompt = null;
              window.addEventListener('beforeinstallprompt', function(e) {
                e.preventDefault();
                window.__pwaPrompt = e;
              });
              if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js').catch(function(){});
              }
              // 로그인 상태 감지 → SEO 섹션 숨김용 클래스 (FOUC 방지)
              try {
                if (localStorage.getItem('auth_token')) {
                  document.documentElement.classList.add('is-logged-in');
                }
              } catch(_) {}
            `,
          }}
        />
        <script src="https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js" crossOrigin="anonymous" async />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              function _initKakao() {
                if (window.Kakao && !window.Kakao.isInitialized()) {
                  window.Kakao.init('832265e411dd686c3fcf925f3558d8f0');
                }
              }
              if (document.readyState === 'complete') _initKakao();
              else window.addEventListener('load', _initKakao);
            `,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased overflow-x-hidden flex flex-col min-h-screen`}
      >
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebApplication",
              "name": "지원금AI",
              "url": "https://www.govmatch.kr",
              "description": "17,000+ 정부 지원금 공고를 AI가 실시간 분석하여 내 조건에 맞는 보조금·정책자금을 자동 매칭해드리는 서비스",
              "applicationCategory": "BusinessApplication",
              "operatingSystem": "Web",
              "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "KRW",
                "description": "무료 플랜 — 맞춤 공고 알림 무제한, AI 상담 월 3회"
              },
              "provider": {
                "@type": "Organization",
                "name": "밸류파인더",
                "url": "https://www.govmatch.kr",
                "email": "osung94@naver.com",
                "address": {
                  "@type": "PostalAddress",
                  "addressLocality": "부산광역시",
                  "addressRegion": "해운대구",
                  "addressCountry": "KR"
                }
              },
              "aggregateRating": {
                "@type": "AggregateRating",
                "ratingValue": "4.8",
                "ratingCount": "57",
                "bestRating": "5"
              }
            }),
          }}
        />
        <div className="flex-1 flex flex-col">
          <Providers>{children}</Providers>
        </div>

        {/* ── SEO 정적 콘텐츠 (SSR) — 검색엔진 노출용
             비로그인: details로 접힘 제공
             로그인: 아래 is-logged-in CSS로 완전 숨김 (크롤러는 항상 비로그인이라 SEO 영향 0) ── */}
        <section className="seo-intro w-full border-t border-slate-200/60 bg-white" aria-label="서비스 소개">
          <details className="max-w-5xl mx-auto px-4 py-6 text-slate-700">
            <summary className="cursor-pointer list-none flex items-center gap-2 text-[13px] md:text-sm font-semibold text-slate-600 hover:text-indigo-600 select-none">
              <span className="text-indigo-500">💡</span>
              <span>지원금AI 서비스 소개 · 주요 키워드 · 데이터 출처</span>
              <span className="ml-auto text-[11px] text-slate-400 group-open:hidden">펼치기 ▼</span>
            </summary>
            <div className="pt-6">
            <h2 className="text-lg md:text-xl font-bold text-slate-900 mb-3">
              지원금AI — 정부 지원금·보조금·정책자금 AI 자동 매칭 서비스
            </h2>
            <p className="text-[13px] md:text-sm leading-relaxed text-slate-600 mb-5">
              지원금AI(govmatch.kr)는 중앙부처와 전국 지자체가 공고하는 <strong>정부 지원금, 보조금, 정책자금, 창업지원금, R&amp;D 과제, 소상공인 지원사업</strong>을 매시간 자동 수집·분석해,
              기업과 개인의 조건에 꼭 맞는 지원사업을 찾아드리는 AI 매칭 서비스입니다. 17,000건 이상의 공고를 AI가 실시간 분석하여 신청 자격·마감일·지원금액을 한눈에 정리해드립니다.
              회원가입 후 업종·지역·매출·관심분야만 입력하면 맞춤 알림까지 자동 발송됩니다.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
              <div>
                <h3 className="text-[13px] font-bold text-slate-800 mb-2">🏢 기업 대상 주요 서비스</h3>
                <ul className="text-[12px] md:text-[13px] text-slate-600 space-y-1 list-disc pl-5">
                  <li>중소기업 R&amp;D 및 기술개발 지원사업 매칭</li>
                  <li>수출·해외마케팅 바우처 자동 추천</li>
                  <li>스마트공장·디지털전환 정책자금 검색</li>
                  <li>창업기업·벤처기업 전용 지원사업</li>
                  <li>소상공인 융자·보증·경영환경 개선 지원</li>
                  <li>여성·장애인·사회적경제기업 전용 사업</li>
                </ul>
              </div>
              <div>
                <h3 className="text-[13px] font-bold text-slate-800 mb-2">👤 개인 대상 주요 서비스</h3>
                <ul className="text-[12px] md:text-[13px] text-slate-600 space-y-1 list-disc pl-5">
                  <li>청년 구직·취업 지원금 안내</li>
                  <li>신혼부부·다자녀 주거 지원</li>
                  <li>저소득·차상위 복지바우처 매칭</li>
                  <li>출산·육아·보육 지원사업</li>
                  <li>에너지·농어업인 지원금</li>
                  <li>장학금·학자금·교육훈련 지원</li>
                </ul>
              </div>
            </div>

            <div className="mb-6">
              <h3 className="text-[13px] font-bold text-slate-800 mb-2">🔗 주요 페이지</h3>
              <nav className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] md:text-[13px]">
                <a href="/" className="text-indigo-600 hover:underline">홈 (맞춤 매칭)</a>
                <a href="/search" className="text-indigo-600 hover:underline">공고 검색</a>
                <a href="/api-partnership" className="text-indigo-600 hover:underline">API 제휴</a>
                <a href="/support" className="text-indigo-600 hover:underline">고객상담</a>
                <a href="/calendar" className="text-indigo-600 hover:underline">지원금 캘린더</a>
                <a href="/terms" className="text-indigo-600 hover:underline">이용약관</a>
                <a href="/privacy" className="text-indigo-600 hover:underline">개인정보 처리방침</a>
                <a href="/refund" className="text-indigo-600 hover:underline">환불 정책</a>
              </nav>
            </div>

            <div className="text-[11px] text-slate-500 leading-relaxed pt-4 border-t border-slate-100">
              <p className="mb-1">
                <strong>주요 데이터 출처:</strong> 기업마당(bizinfo.go.kr), K-Startup, 중소벤처기업부, 중소기업기술정보진흥원, 과학기술정보통신부, 한국식품안전관리인증원, 정부24, 지방자치단체 복지포털 등 17,000건 이상의 공고 실시간 연동.
              </p>
              <p>
                <strong>연관 키워드:</strong> 정부지원금, 정부보조금, 중소기업지원금, 소상공인지원금, 창업지원금, 정책자금 신청, 청년지원금, 지자체 지원사업, 바우처 사업, R&amp;D 과제, 사업계획서 컨설팅, 지원금 찾기
              </p>
            </div>
            </div>
          </details>
        </section>

        <footer className="w-full border-t border-slate-200/60 bg-slate-50/80">
          <div className="max-w-5xl mx-auto px-4 py-5 text-[11px] text-slate-400 leading-relaxed">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
              <span className="font-semibold text-slate-500">밸류파인더</span>
              <span className="text-slate-300">|</span>
              <span>대표 권오성</span>
              <span className="text-slate-300">|</span>
              <span>사업자등록번호 141-17-02215</span>
              <span className="text-slate-300">|</span>
              <span>AI솔루션 개발 및 기술경영 컨설팅</span>
              <span className="text-slate-300">|</span>
              <span>부산광역시 해운대구 센텀중앙로 145, 109동 3405호</span>
              <span className="text-slate-300">|</span>
              <span>Tel 010-5565-2299</span>
              <span className="text-slate-300">|</span>
              <span>osung94@naver.com</span>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
              <a href="/terms" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">이용약관</a>
              <a href="/privacy" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">개인정보 처리방침</a>
              <a href="/refund" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">환불 정책</a>
              <a href="/api-partnership" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">API 제휴</a>
              <a href="/support" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">고객상담</a>
              <span className="text-slate-300 ml-auto">&copy; {new Date().getFullYear()} 밸류파인더. All rights reserved.</span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
