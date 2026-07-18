import { MetadataRoute } from "next";

const API = process.env.NEXT_PUBLIC_API_URL || "https://govmatch-production.up.railway.app";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = "https://www.govmatch.kr";

  // 정적 페이지
  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${baseUrl}/search`, lastModified: new Date(), changeFrequency: "daily", priority: 0.8 },
    { url: `${baseUrl}/calendar`, lastModified: new Date(), changeFrequency: "daily", priority: 0.7 },
    { url: `${baseUrl}/support`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.6 },
    { url: `${baseUrl}/api-partnership`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.7 },
    { url: `${baseUrl}/privacy`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.3 },
    { url: `${baseUrl}/terms`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.3 },
    { url: `${baseUrl}/refund`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.3 },
    // slug를 URL 인코딩 — 원시 한글 경로는 일부 크롤러가 raw로 요청 시 500. 인코딩 형태(canonical과 동일)로 방출해 항상 200 보장.
    { url: `${baseUrl}/guide/${encodeURIComponent("소상공인-정책자금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("청년창업지원금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("다자녀-지원금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("중소기업-수출지원")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("소상공인-지원금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("중소기업-정책자금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
    { url: `${baseUrl}/guide/${encodeURIComponent("창업지원금")}`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.8 },
  ];

  // 동적 페이지 — 마감 전 + 내용 있는 공고 (최대 500건)
  let annPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API}/api/sitemap/announcements`, { next: { revalidate: 86400 } });
    const data = await res.json();
    if (data.data) {
      annPages = data.data.map((ann: { id: number; updated_at: string }) => ({
        url: `${baseUrl}/announcements/${ann.id}`,
        lastModified: ann.updated_at ? new Date(ann.updated_at) : new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.65,
      }));
    }
  } catch {
    // API 실패해도 정적 페이지는 반환
  }

  return [...staticPages, ...annPages];
}
