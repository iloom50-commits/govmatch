// 서버 컴포넌트 — "use client" 없음. 네이버·구글 봇이 읽는 실제 공고 데이터
const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

interface Ann {
  announcement_id: number;
  title: string;
  department?: string;
  category?: string;
  support_amount?: string;
  deadline_date?: string;
  region?: string;
  summary_text?: string;
}

async function fetchPublicAnnouncements(targetType: "business" | "individual"): Promise<Ann[]> {
  try {
    const res = await fetch(
      `${API}/api/announcements/public?page=1&size=30&target_type=${targetType}`,
      {
        cache: "no-store",
        headers: {
          "x-bot-token": process.env.BOT_TOKEN || "GOVMATCH_BLOG_BOT_2026",
        },
      }
    );
    if (!res.ok) return [];
    const data = await res.json();
    return data.data || [];
  } catch {
    return [];
  }
}

function formatAmount(amount?: string) {
  if (!amount) return null;
  const str = String(amount);
  if (str.length > 20) return str.slice(0, 20) + "…";
  return str;
}

function formatDeadline(d?: string) {
  if (!d) return null;
  return String(d).slice(0, 10).replace(/-/g, ".");
}

export default async function HomeSSR() {
  const [bizAnns, indivAnns] = await Promise.all([
    fetchPublicAnnouncements("business"),
    fetchPublicAnnouncements("individual"),
  ]);

  if (bizAnns.length === 0 && indivAnns.length === 0) return null;

  return (
    <section
      className="home-seo-section w-full border-t border-slate-200/60 bg-white"
      aria-label="최신 정부지원금 공고"
    >
      <div className="max-w-5xl mx-auto px-4 py-8">
        {bizAnns.length > 0 && (
          <div className="mb-10">
            <h2 className="text-base font-bold text-slate-800 mb-4">
              🏢 기업·소상공인 최신 지원금 공고
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {bizAnns.map((ann) => (
                <article
                  key={ann.announcement_id}
                  className="bg-slate-50 border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-sm transition-all"
                >
                  <div className="flex flex-wrap gap-1 mb-2">
                    {ann.category && (
                      <span className="text-[11px] px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full">
                        {ann.category}
                      </span>
                    )}
                    {ann.region && ann.region !== "All" && (
                      <span className="text-[11px] px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full">
                        {ann.region}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 leading-snug mb-2 line-clamp-2">
                    <a href={`/announcements/${ann.announcement_id}`} className="hover:text-indigo-600">
                      {ann.title}
                    </a>
                  </h3>
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>{ann.department?.slice(0, 16)}</span>
                    {formatAmount(ann.support_amount) && (
                      <span className="text-rose-500 font-bold">{formatAmount(ann.support_amount)}</span>
                    )}
                  </div>
                  {formatDeadline(ann.deadline_date) && (
                    <p className="text-[11px] text-slate-400 mt-1">마감 {formatDeadline(ann.deadline_date)}</p>
                  )}
                </article>
              ))}
            </div>
            <div className="mt-3 text-right">
              <a href="/search?q=기업지원금" className="text-xs text-indigo-600 hover:underline">
                기업 지원금 더보기 →
              </a>
            </div>
          </div>
        )}

        {indivAnns.length > 0 && (
          <div>
            <h2 className="text-base font-bold text-slate-800 mb-4">
              👤 개인·청년 최신 지원금 공고
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {indivAnns.map((ann) => (
                <article
                  key={ann.announcement_id}
                  className="bg-slate-50 border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-sm transition-all"
                >
                  <div className="flex flex-wrap gap-1 mb-2">
                    {ann.category && (
                      <span className="text-[11px] px-2 py-0.5 bg-violet-50 text-violet-600 rounded-full">
                        {ann.category}
                      </span>
                    )}
                    {ann.region && ann.region !== "All" && (
                      <span className="text-[11px] px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full">
                        {ann.region}
                      </span>
                    )}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 leading-snug mb-2 line-clamp-2">
                    <a href={`/announcements/${ann.announcement_id}`} className="hover:text-indigo-600">
                      {ann.title}
                    </a>
                  </h3>
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>{ann.department?.slice(0, 16)}</span>
                    {formatAmount(ann.support_amount) && (
                      <span className="text-rose-500 font-bold">{formatAmount(ann.support_amount)}</span>
                    )}
                  </div>
                  {formatDeadline(ann.deadline_date) && (
                    <p className="text-[11px] text-slate-400 mt-1">마감 {formatDeadline(ann.deadline_date)}</p>
                  )}
                </article>
              ))}
            </div>
            <div className="mt-3 text-right">
              <a href="/search?q=청년지원금" className="text-xs text-indigo-600 hover:underline">
                개인 지원금 더보기 →
              </a>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
