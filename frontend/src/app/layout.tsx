import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Providers from "@/components/Providers";

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
    default: "지원금AI — 지원금 찾지 마세요. AI가 구석구석 찾아드림",
    template: "%s | 지원금AI",
  },
  description: "17,000+ 정부 지원금 공고를 AI가 실시간 분석. 내 조건에 딱 맞는 정부지원금, 보조금, 정책자금을 자동 매칭해드립니다. 기업·개인 모두 무료!",
  keywords: ["정부지원금", "보조금", "정책자금", "중소기업지원", "소상공인지원", "창업지원", "개인복지", "AI매칭", "지원금찾기"],
  manifest: "/manifest.json",
  metadataBase: new URL("https://govmatch.kr"),
  alternates: {
    canonical: "https://govmatch.kr",
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: "https://govmatch.kr",
    siteName: "지원금AI",
    title: "지원금AI — AI가 구석구석 찾아드리는 정부 지원금 매칭",
    description: "17,000+ 정부 지원금 공고를 AI가 실시간 분석. 내 조건에 딱 맞는 보조금·정책자금을 자동 매칭. 무료!",
    images: [{
      url: "/icon-512.png",
      width: 512,
      height: 512,
      alt: "지원금AI 로고",
    }],
  },
  twitter: {
    card: "summary_large_image",
    title: "지원금AI — 정부 지원금 AI 자동 매칭",
    description: "17,000+ 정부 지원금 공고 AI 분석. 내 조건에 맞는 보조금 자동 매칭!",
    images: ["/icon-512.png"],
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
        <meta name="theme-color" content="#2563eb" />
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
              window.__pwaPrompt = null;
              window.addEventListener('beforeinstallprompt', function(e) {
                e.preventDefault();
                window.__pwaPrompt = e;
              });
              if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js').catch(function(){});
              }
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
              "url": "https://govmatch.kr",
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
                "url": "https://govmatch.kr",
                "email": "osung94@naver.com",
                "address": {
                  "@type": "PostalAddress",
                  "addressLocality": "부산광역시",
                  "addressRegion": "부산진구",
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
              <span>부산 부산진구 서면문화로27, 유원골든타워 1905호</span>
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
