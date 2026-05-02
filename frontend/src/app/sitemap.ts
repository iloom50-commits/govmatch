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
  ];

  // 동적 페이지 — 기업 공고 (최대 500건)
  let bizPages: MetadataRoute.Sitemap = [];
  let indivPages: MetadataRoute.Sitemap = [];
  try {
    const [bizRes, indivRes] = await Promise.all([
      fetch(`${API}/api/announcements/public?page=1&size=400&target_type=business`, { next: { revalidate: 86400 } }),
      fetch(`${API}/api/announcements/public?page=1&size=200&target_type=individual`, { next: { revalidate: 86400 } }),
    ]);
    const [bizData, indivData] = await Promise.all([bizRes.json(), indivRes.json()]);
    if (bizData.status === "SUCCESS" && bizData.data) {
      bizPages = bizData.data.map((ann: any) => ({
        url: `${baseUrl}/announcements/${ann.announcement_id}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.65,
      }));
    }
    if (indivData.status === "SUCCESS" && indivData.data) {
      indivPages = indivData.data.map((ann: any) => ({
        url: `${baseUrl}/announcements/${ann.announcement_id}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.6,
      }));
    }
  } catch {
    // API 실패해도 정적 페이지는 반환
  }

  const seen = new Set<string>();
  const allAnnPages = [...bizPages, ...indivPages].filter(p => {
    if (seen.has(p.url)) return false;
    seen.add(p.url);
    return true;
  });

  return [...staticPages, ...allAnnPages];
}
