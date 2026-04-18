"use client";

export default function AnnouncementDetail({ announcement }: { announcement: any }) {
  const handleConsult = () => {
    // 메인 페이지로 이동 + AI 상담 열기
    if (typeof window !== "undefined") {
      localStorage.setItem("pending_consult_aid", String(announcement.announcement_id));
      window.location.href = "/";
    }
  };

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      <button
        onClick={handleConsult}
        className="flex-1 py-3 bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl font-bold text-sm hover:from-indigo-700 hover:to-violet-700 transition-all active:scale-[0.98]"
      >
        ✨ AI로 자격 확인하기
      </button>
      <a
        href="/"
        className="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl font-bold text-sm text-center hover:bg-slate-200 transition-all"
      >
        다른 지원사업 보기
      </a>
    </div>
  );
}
