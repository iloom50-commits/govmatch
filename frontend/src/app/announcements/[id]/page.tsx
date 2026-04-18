import { Metadata } from "next";
import AnnouncementDetail from "./AnnouncementDetail";

const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

// SSR — 서버에서 공고 데이터를 가져와서 메타데이터 + HTML 렌더링
async function getAnnouncement(id: string) {
  try {
    const res = await fetch(`${API}/api/announcements/${id}`, {
      next: { revalidate: 3600 }, // 1시간 캐시
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.data || data;
  } catch {
    return null;
  }
}

// 동적 메타데이터 — 네이버/구글 봇이 읽음
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const ann = await getAnnouncement(id);
  if (!ann) {
    return { title: "공고를 찾을 수 없습니다" };
  }

  const title = `${ann.title} | 지원금AI`;
  const description = ann.summary_text
    ? ann.summary_text.slice(0, 150)
    : `${ann.department || "정부"} ${ann.title} - 자격요건, 지원금액, 신청방법을 AI가 분석해드립니다.`;

  return {
    title,
    description,
    openGraph: {
      title: ann.title,
      description,
      url: `https://www.govmatch.kr/announcements/${id}`,
      type: "article",
    },
    alternates: {
      canonical: `https://www.govmatch.kr/announcements/${id}`,
    },
  };
}

export default async function AnnouncementPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ann = await getAnnouncement(id);

  if (!ann) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-xl font-bold text-slate-800 mb-2">공고를 찾을 수 없습니다</h1>
          <a href="/" className="text-indigo-600 hover:underline">메인으로 이동</a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* SEO 정적 콘텐츠 — 네이버 봇이 읽음 */}
        <nav className="text-sm text-slate-400 mb-4">
          <a href="/" className="hover:text-indigo-600">지원금AI</a>
          <span className="mx-2">/</span>
          <span>{ann.category || "지원사업"}</span>
        </nav>

        <article>
          <h1 className="text-2xl font-bold text-slate-900 mb-4 leading-tight">{ann.title}</h1>

          <div className="flex flex-wrap gap-2 mb-6">
            {ann.department && (
              <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium">{ann.department}</span>
            )}
            {ann.category && (
              <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-sm">{ann.category}</span>
            )}
            {ann.region && ann.region !== "All" && (
              <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm">{ann.region}</span>
            )}
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 mb-6">
            <dl className="grid grid-cols-2 gap-4 text-sm">
              {ann.support_amount && (
                <>
                  <dt className="text-slate-400 font-medium">지원금액</dt>
                  <dd className="text-slate-900 font-bold">{ann.support_amount}</dd>
                </>
              )}
              {ann.deadline_date && (
                <>
                  <dt className="text-slate-400 font-medium">마감일</dt>
                  <dd className="text-slate-900">{String(ann.deadline_date).slice(0, 10)}</dd>
                </>
              )}
              {ann.region && (
                <>
                  <dt className="text-slate-400 font-medium">지역</dt>
                  <dd className="text-slate-900">{ann.region}</dd>
                </>
              )}
              {ann.target_type && (
                <>
                  <dt className="text-slate-400 font-medium">대상</dt>
                  <dd className="text-slate-900">{ann.target_type === "individual" ? "개인" : ann.target_type === "business" ? "기업" : "전체"}</dd>
                </>
              )}
            </dl>
          </div>

          {ann.summary_text && (
            <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 mb-6">
              <h2 className="text-lg font-bold text-slate-800 mb-3">공고 내용</h2>
              <p className="text-slate-600 text-sm leading-relaxed whitespace-pre-line">{ann.summary_text.slice(0, 2000)}</p>
            </div>
          )}

          {/* 클라이언트 컴포넌트 — AI 상담 버튼 등 */}
          <AnnouncementDetail announcement={ann} />

          {ann.origin_url && (
            <div className="mt-6 text-center">
              <a
                href={ann.final_url || ann.origin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-slate-400 hover:text-indigo-600 underline"
              >
                원문 공고 보기
              </a>
            </div>
          )}
        </article>

        {/* SEO 푸터 */}
        <footer className="mt-12 pt-6 border-t border-slate-100 text-xs text-slate-400">
          <p>지원금AI는 정부 지원금, 보조금, 정책자금 공고를 AI가 분석하여 맞춤 매칭해주는 서비스입니다.</p>
          <p className="mt-1">이 페이지의 정보는 공식 공고를 기반으로 하며, 최종 확인은 주관기관에서 해주세요.</p>
        </footer>
      </div>
    </div>
  );
}
