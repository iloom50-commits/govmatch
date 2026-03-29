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
  title: "지원금GO — 지원금 찾지 마세요. AI가 구석구석 찾아드림",
  description: "지원금 찾지 마세요. AI가 구석구석 찾아드림. 우리 기업에 딱 맞는 정부지원금, 보조금, 정책자금을 자동 매칭.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "지원금GO",
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
        <meta name="google-site-verification" content="u3SIJ5Y_wqzTLLCOwPCzh4r1h8JRLj-WBemyH6nKml8" />
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
        <script src="https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js" crossOrigin="anonymous" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              document.addEventListener('DOMContentLoaded', function() {
                if (window.Kakao && !window.Kakao.isInitialized()) {
                  window.Kakao.init('832265e411dd686c3fcf925f3558d8f0');
                }
              });
            `,
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased overflow-x-hidden`}
      >
        <Providers>{children}</Providers>
        <footer className="w-full border-t border-slate-200/60 bg-slate-50/80 mt-12">
          <div className="max-w-4xl mx-auto px-4 py-6 text-[11px] text-slate-400 leading-relaxed space-y-1">
            <p className="font-semibold text-slate-500">밸류파인더 | 대표 권오성</p>
            <p>사업자등록번호 141-17-02215 | 경영 컨설팅업</p>
            <p>부산광역시 해운대구 센텀중앙로 145, 109동 3405호</p>
            <p>이메일 osung94@naver.com | 전화 010-6346-7718</p>
            <p className="pt-2 flex gap-3">
              <a href="/terms" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">이용약관</a>
              <a href="/privacy" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">개인정보 처리방침</a>
              <a href="/refund" className="text-slate-400 hover:text-indigo-500 underline underline-offset-2">환불 정책</a>
            </p>
            <p className="pt-1 text-slate-300">&copy; {new Date().getFullYear()} 밸류파인더. All rights reserved.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
