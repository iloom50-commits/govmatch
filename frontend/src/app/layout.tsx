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
  description: "지원금AI — 정부 지원금·보조금·정책자금을 AI가 자동 분석합니다. 중소기업·소상공인·청년·개인 맞춤 17,000건 이상의 공고를 30초 안에 찾아드립니다. 무료로 시작하세요.",
  keywords: [
    "지원금AI", "정부지원금", "정부보조금", "정책자금", "지원금찾기", "AI매칭",
    "중소기업지원금", "소상공인지원금", "창업지원금", "청년지원금", "R&D지원",
    "소상공인정책자금", "사업화지원금", "스타트업지원", "바우처사업",
    "청년창업", "예비창업패키지", "초기창업패키지",
    "전세자금", "주거지원", "복지바우처", "출산지원금", "육아지원금",
    "지자체지원사업", "중소기업진흥공단", "기업마당", "정부지원사업",
    "보조금신청", "정책자금신청", "지원금신청방법", "소상공인보조금",
  ],
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
    description: "정부 지원금·보조금·정책자금을 AI가 자동 분석합니다. 중소기업·소상공인·청년 맞춤 17,000건 이상의 공고를 30초 안에 찾아드립니다.",
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
    description: "정부 지원금·보조금·정책자금을 AI가 자동 분석합니다. 중소기업·소상공인·청년 맞춤 17,000건 이상의 공고를 30초 안에 찾아드립니다.",
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
              "alternateName": "govmatch",
              "url": "https://www.govmatch.kr",
              "description": "정부 지원금·보조금·정책자금 공고를 AI가 실시간 분석하여 중소기업·소상공인·청년·개인 조건에 맞는 지원사업을 자동 매칭해드리는 서비스. 17,000건 이상 공고 보유.",
              "applicationCategory": "BusinessApplication",
              "operatingSystem": "Web",
              "inLanguage": "ko",
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
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "FAQPage",
              "mainEntity": [
                {
                  "@type": "Question",
                  "name": "지원금AI란 무엇인가요?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "지원금AI(govmatch.kr)는 중앙부처와 전국 지자체의 정부 지원금·보조금·정책자금 공고 17,000건 이상을 AI가 실시간 분석하여, 기업과 개인 조건에 꼭 맞는 지원사업을 자동으로 찾아드리는 AI 매칭 서비스입니다."
                  }
                },
                {
                  "@type": "Question",
                  "name": "어떤 지원금을 찾을 수 있나요?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "중소기업 R&D 지원사업, 소상공인 정책자금·융자, 창업지원금(예비창업패키지·초기창업패키지·TIPS), 수출바우처, 고용지원금, 청년지원금, 주거지원, 복지바우처, 출산·육아 지원, 장학금 등 기업과 개인을 위한 모든 정부 지원사업을 찾아드립니다."
                  }
                },
                {
                  "@type": "Question",
                  "name": "지원금AI는 무료인가요?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "네, 기본 기능은 무료입니다. 회원가입 후 업종·지역·매출 정보를 입력하면 맞춤 지원금 공고를 무제한으로 받아볼 수 있으며, AI 상담은 월 3회 무료로 이용 가능합니다."
                  }
                },
                {
                  "@type": "Question",
                  "name": "소상공인도 이용할 수 있나요?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "네. 소상공인진흥공단의 정책자금·융자·보증, 각 지자체 소상공인 지원사업, 경영환경 개선 지원 등 소상공인 전용 지원사업을 별도로 분류하여 안내해드립니다."
                  }
                },
                {
                  "@type": "Question",
                  "name": "개인도 지원금을 받을 수 있나요?",
                  "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "네. 청년 취업·창업 지원금, 신혼부부·청년 주거 지원, 출산·육아 지원금, 복지바우처, 장학금 등 개인 대상 지원사업도 AI가 조건에 맞게 자동 매칭해드립니다."
                  }
                }
              ]
            }),
          }}
        />
        <div className="flex-1 flex flex-col">
          <Providers>{children}</Providers>
        </div>

        {/* ── SEO 정적 콘텐츠 (SSR) — 검색엔진 노출용
             비로그인: details로 접힘 제공
             로그인: 아래 is-logged-in CSS로 완전 숨김 (크롤러는 항상 비로그인이라 SEO 영향 0) ── */}
        <section className="seo-intro w-full border-t border-slate-200/60 bg-gradient-to-b from-white to-slate-50/50" aria-label="서비스 소개">
          <div className="max-w-5xl mx-auto px-4 py-8 text-slate-700">
            <h1 className="text-xl md:text-2xl font-bold text-slate-900 mb-3">
              지원금AI — 정부 지원금·보조금·정책자금 AI 자동 매칭 서비스
            </h1>
            <p className="text-[13px] md:text-sm leading-relaxed text-slate-600 mb-6">
              <strong>지원금AI(govmatch.kr)</strong>는 중앙부처와 전국 지자체가 공고하는 <strong>정부 지원금, 보조금, 정책자금, 창업지원금, R&amp;D 과제, 소상공인 지원사업</strong>을 매시간 자동 수집·분석합니다.
              기업과 개인의 업종·지역·매출·연령 조건에 꼭 맞는 지원사업을 AI가 자동으로 찾아드리는 서비스로, 17,000건 이상의 공고를 실시간 분석하여 신청 자격·마감일·지원금액을 한눈에 정리해드립니다.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
              <div className="bg-white rounded-xl p-4 border border-slate-100 shadow-sm">
                <h2 className="text-[13px] font-bold text-slate-800 mb-2">🏢 기업·소상공인 지원금</h2>
                <ul className="text-[12px] text-slate-600 space-y-1 list-disc pl-4">
                  <li>중소기업 R&amp;D·기술개발 지원사업</li>
                  <li>소상공인 정책자금·융자·보증</li>
                  <li>수출·해외마케팅 바우처</li>
                  <li>스마트공장·디지털전환 자금</li>
                  <li>창업·벤처 전용 지원사업</li>
                  <li>여성·장애인·사회적기업 지원</li>
                </ul>
              </div>
              <div className="bg-white rounded-xl p-4 border border-slate-100 shadow-sm">
                <h2 className="text-[13px] font-bold text-slate-800 mb-2">👤 개인·청년 지원금</h2>
                <ul className="text-[12px] text-slate-600 space-y-1 list-disc pl-4">
                  <li>청년 취업·구직 지원금</li>
                  <li>신혼부부·청년 전세·월세 지원</li>
                  <li>출산·육아·다자녀 지원금</li>
                  <li>저소득·차상위 복지바우처</li>
                  <li>국가장학금·학자금 지원</li>
                  <li>에너지·농어업인 지원금</li>
                </ul>
              </div>
              <div className="bg-white rounded-xl p-4 border border-slate-100 shadow-sm">
                <h2 className="text-[13px] font-bold text-slate-800 mb-2">🤖 AI 서비스 특징</h2>
                <ul className="text-[12px] text-slate-600 space-y-1 list-disc pl-4">
                  <li>17,000건 이상 공고 실시간 분석</li>
                  <li>조건 입력 후 30초 내 맞춤 매칭</li>
                  <li>AI 전문가 상담 (LITE·PRO)</li>
                  <li>마감 임박 공고 자동 알림</li>
                  <li>사업계획서 작성 지원</li>
                  <li>무료로 시작 가능</li>
                </ul>
              </div>
            </div>

            <div className="mb-5">
              <h2 className="text-[13px] font-bold text-slate-800 mb-2">주요 지원금 카테고리</h2>
              <nav className="flex flex-wrap gap-2 text-[12px]">
                {["정부지원금", "소상공인지원금", "창업지원금", "청년지원금", "R&D지원", "수출지원", "주거지원", "복지지원", "출산지원", "장학금"].map(kw => (
                  <a key={kw} href={`/search?q=${encodeURIComponent(kw)}`}
                    className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full hover:bg-indigo-100 transition-colors">
                    {kw}
                  </a>
                ))}
              </nav>
            </div>

            <div className="mb-5">
              <h2 className="text-[13px] font-bold text-slate-800 mb-2">주요 페이지</h2>
              <nav className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] md:text-[13px]">
                <a href="/" className="text-indigo-600 hover:underline">홈 · 맞춤 매칭</a>
                <a href="/search" className="text-indigo-600 hover:underline">공고 검색</a>
                <a href="/calendar" className="text-indigo-600 hover:underline">지원금 캘린더</a>
                <a href="/api-partnership" className="text-indigo-600 hover:underline">API 제휴</a>
                <a href="/support" className="text-indigo-600 hover:underline">고객상담</a>
              </nav>
            </div>

            <div className="text-[11px] text-slate-500 leading-relaxed pt-4 border-t border-slate-100">
              <p className="mb-1">
                <strong>데이터 출처:</strong> 기업마당(bizinfo.go.kr), K-Startup, 중소벤처기업부, 중소기업기술정보진흥원, 과학기술정보통신부, 정부24, 복지로, 각 지자체 공식 공고 등 17,000건 이상 실시간 연동.
              </p>
              <p>
                <strong>검색 키워드:</strong> 지원금AI, 정부지원금, 정부보조금, 중소기업지원금, 소상공인지원금, 창업지원금, 정책자금신청, 청년지원금, 지자체지원사업, 바우처사업, R&amp;D과제, 지원금찾기, AI보조금매칭
              </p>
            </div>
          </div>
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
