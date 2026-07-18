import type { Metadata } from "next";
import { getGuide } from "../content";

export const revalidate = 3600;

const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

function safeDecode(s: string) { try { return decodeURIComponent(s); } catch { return s; } }

// DB support_amount의 원시 숫자(예: "200000000000원")를 억·만원으로 포맷. 7자리 이상 숫자런만 변환.
function formatKrwText(s: string): string {
  return String(s).replace(/(\d{7,})원?/g, (_, d) => {
    const n = parseInt(d, 10);
    const eok = Math.floor(n / 1e8);
    const man = Math.floor((n % 1e8) / 1e4);
    let out = "";
    if (eok > 0) out += `${eok.toLocaleString()}억`;
    if (man > 0) out += `${man.toLocaleString()}만`;
    return (out || n.toLocaleString()) + "원";
  });
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const g = getGuide(safeDecode(slug));
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
  const g = getGuide(safeDecode(slug));
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

  let live: any[] = [];
  try {
    const qs = g.liveFilter.param === "category"
      ? `category=${encodeURIComponent(g.liveFilter.value)}`
      : `search=${encodeURIComponent(g.liveFilter.value)}`;
    const r = await fetch(`${API}/api/announcements/public?target_type=${g.targetType || "business"}&size=8&${qs}`,
      { next: { revalidate: 3600 }, signal: AbortSignal.timeout(3000) });
    if (r.ok) { const d = await r.json(); live = d.data ?? d.announcements ?? []; }
  } catch { live = []; }

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
                    {a.support_amount && (() => {
                      const amt = formatKrwText(String(a.support_amount));
                      return (
                        <span className="block text-[13px] font-medium text-blue-600 mt-1">
                          {amt.length > 80 ? amt.slice(0, 80) + "…" : amt}
                        </span>
                      );
                    })()}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

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
