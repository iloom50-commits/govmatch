import type { Metadata } from "next";

// 서버 컴포넌트 — "use client" 없음.
//
// 목적: blog.govmatch.kr의 글을 구글 크롤러에게 알린다.
// 2026-08-04 확인 결과 블로그 글 287건이 전부 "Google에 아직 알려지지 않은 URL"이었다.
// 사이트맵은 정상 처리(오류 0)됐지만 크롤링 예산이 배분되지 않았고, 외부 유입 링크도
// 사실상 없었다. www 도메인은 정기적으로 크롤링되므로, 여기서 글 링크를 걸어
// 크롤러가 따라오게 한다.
//
// 반드시 서버 렌더링이어야 한다. 클라이언트 탭·JS 렌더링이면 크롤러가 링크를 못 본다.

export const revalidate = 3600;

const WP_API = "https://blog.govmatch.kr/wp-json/wp/v2/posts";
const PER_PAGE = 30;

interface Post {
  link: string;
  title: { rendered: string };
  excerpt: { rendered: string };
  date: string;
  _embedded?: { "wp:term"?: { name: string }[][] };
}

function stripHtml(s: string) {
  return (s || "")
    .replace(/<[^>]*>/g, "")
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#8230;/g, "…")
    .trim();
}

function formatDate(d: string) {
  return String(d).slice(0, 10).replace(/-/g, ".");
}

async function fetchPosts(page: number): Promise<{ posts: Post[]; totalPages: number }> {
  try {
    const res = await fetch(
      `${WP_API}?per_page=${PER_PAGE}&page=${page}&_embed=wp:term&_fields=link,title,excerpt,date,_links,_embedded`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return { posts: [], totalPages: 0 };
    const totalPages = Number(res.headers.get("X-WP-TotalPages") || 1);
    return { posts: await res.json(), totalPages };
  } catch {
    // 블로그가 죽어도 이 페이지는 200으로 뜬다 — 404는 색인에서 빠진다
    return { posts: [], totalPages: 0 };
  }
}

export const metadata: Metadata = {
  title: "지원금 정보 블로그",
  description:
    "정부지원금 공고를 알기 쉽게 정리한 글 모음입니다. 지원 대상·금액·신청 방법을 공고별로 확인하세요.",
  alternates: { canonical: "https://www.govmatch.kr/blog" },
  openGraph: {
    title: "지원금 정보 블로그 | 지원금AI",
    description: "정부지원금 공고를 알기 쉽게 정리한 글 모음",
    type: "website",
    url: "https://www.govmatch.kr/blog",
  },
  robots: { index: true, follow: true },
};

export default async function BlogIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page) || 1);
  const { posts, totalPages } = await fetchPosts(page);

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-5xl mx-auto px-4 py-8">
        <header className="mb-6">
          <h1 className="text-xl font-bold text-slate-800 mb-1">지원금 정보 블로그</h1>
          <p className="text-sm text-slate-500">
            정부지원금 공고를 알기 쉽게 정리했습니다. 지원 대상·금액·신청 방법을 공고별로 확인하세요.
          </p>
        </header>

        {posts.length === 0 ? (
          <p className="text-sm text-slate-500 py-12 text-center">
            글을 불러오지 못했습니다.{" "}
            <a
              href="https://blog.govmatch.kr/"
              className="text-indigo-600 hover:underline"
              rel="noopener"
            >
              블로그에서 직접 보기 →
            </a>
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {posts.map((p) => {
              const terms = (p._embedded?.["wp:term"] || []).flat().slice(0, 2);
              return (
                <article
                  key={p.link}
                  className="bg-slate-50 border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-sm transition-all"
                >
                  {terms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {terms.map((t) => (
                        <span
                          key={t.name}
                          className="text-[11px] px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded-full"
                        >
                          {t.name}
                        </span>
                      ))}
                    </div>
                  )}
                  <h2 className="text-sm font-semibold text-slate-800 leading-snug mb-2 line-clamp-2">
                    <a href={p.link} className="hover:text-indigo-600" rel="noopener">
                      {stripHtml(p.title.rendered)}
                    </a>
                  </h2>
                  <p className="text-[12px] text-slate-500 leading-relaxed line-clamp-3 mb-2">
                    {stripHtml(p.excerpt.rendered)}
                  </p>
                  <p className="text-[11px] text-slate-400">{formatDate(p.date)}</p>
                </article>
              );
            })}
          </div>
        )}

        {/* 페이지 링크는 실제 <a>여야 크롤러가 따라간다 */}
        {totalPages > 1 && (
          <nav className="mt-8 flex flex-wrap justify-center gap-2" aria-label="블로그 글 목록 페이지">
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
              <a
                key={n}
                href={n === 1 ? "/blog" : `/blog?page=${n}`}
                aria-current={n === page ? "page" : undefined}
                className={
                  n === page
                    ? "text-xs px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-600 font-semibold border border-indigo-100"
                    : "text-xs px-3 py-1.5 rounded-lg text-slate-500 border border-slate-200 hover:border-indigo-300 hover:text-indigo-600 transition-all"
                }
              >
                {n}
              </a>
            ))}
          </nav>
        )}

        <div className="mt-8 pt-5 border-t border-slate-100 text-center">
          <a href="/" className="text-xs text-indigo-600 hover:underline">
            ← 지원금AI 홈으로
          </a>
        </div>
      </div>
    </div>
  );
}
