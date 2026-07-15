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
