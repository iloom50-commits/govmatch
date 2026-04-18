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

  // 동적 페이지 — 주요 공고 (마감 안 된 것, 최대 500건)
  let announcementPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API}/api/announcements/public?page=1&size=500&target_type=business`, {
      next: { revalidate: 86400 }, // 24시간 캐시
    });
    const data = await res.json();
    if (data.status === "SUCCESS" && data.data) {
      announcementPages = data.data.map((ann: any) => ({
        url: `${baseUrl}/announcements/${ann.announcement_id}`,
        lastModified: new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.6,
      }));
    }
  } catch {
    // API 실패해도 정적 페이지는 반환
  }

  return [...staticPages, ...announcementPages];
}
