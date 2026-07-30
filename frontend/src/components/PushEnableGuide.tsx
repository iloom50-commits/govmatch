"use client";

// 푸시 켜기 실패 시(권한 차단·iOS 미설치·미지원) 기종별 켜는 방법 안내 모달.
// 웹은 OS 설정으로 직접 이동 불가 → 어디를 눌러 허용하는지 단계로 안내.

type Reason = "ios-install" | "denied" | "default" | "unsupported";

function detectReason(): Reason {
  if (typeof window === "undefined") return "default";
  const ua = navigator.userAgent || "";
  const isIos = /iPad|iPhone|iPod/.test(ua)
    || (navigator.platform === "MacIntel" && (navigator as any).maxTouchPoints > 1);
  const isStandalone = window.matchMedia?.("(display-mode: standalone)").matches
    || (navigator as any).standalone === true;
  const supported = "serviceWorker" in navigator && "PushManager" in window && typeof Notification !== "undefined";
  if (isIos && !isStandalone) return "ios-install";
  if (!supported) return "unsupported";
  if (typeof Notification !== "undefined" && Notification.permission === "denied") return "denied";
  return "default";
}

const CONTENT: Record<Reason, { title: string; desc: string; steps: string[] }> = {
  "ios-install": {
    title: "아이폰은 홈 화면에 추가 후 켤 수 있어요",
    desc: "아이폰 사파리 탭에서는 알림을 받을 수 없어요. 홈 화면 앱으로 추가하면 알림을 켤 수 있습니다.",
    steps: [
      "사파리 아래쪽 공유 버튼(↑) 누르기",
      "'홈 화면에 추가' 선택 → 추가",
      "홈 화면에 생긴 '지원금AI' 아이콘으로 열기",
      "그 앱에서 이 화면의 알림 토글 다시 켜기",
    ],
  },
  denied: {
    title: "알림이 차단돼 있어요",
    desc: "브라우저에서 이 사이트 알림이 '차단'으로 설정돼 있어요. 아래처럼 '허용'으로 바꾼 뒤 다시 켜 주세요.",
    steps: [
      "주소창 왼쪽의 자물쇠(또는 ⓘ) 아이콘 누르기",
      "'알림' 또는 '권한' 항목 찾기",
      "'차단' → '허용'으로 변경",
      "페이지 새로고침 후 알림 토글 다시 켜기",
    ],
  },
  default: {
    title: "알림 허용이 필요해요",
    desc: "토글을 누르면 브라우저가 '알림을 허용하시겠어요?' 팝업을 띄웁니다. 거기서 '허용'을 눌러 주세요.",
    steps: [
      "알림 토글을 다시 누르기",
      "브라우저 팝업에서 '허용' 선택",
      "팝업이 안 뜨면 주소창 자물쇠 → 알림 → 허용",
    ],
  },
  unsupported: {
    title: "이 브라우저는 웹 알림을 지원하지 않아요",
    desc: "크롬·엣지·삼성 인터넷 등 최신 브라우저에서 열면 알림을 받을 수 있어요. (완료된 상담은 '상담 이력'에서도 확인 가능)",
    steps: [
      "크롬 등 최신 브라우저로 www.govmatch.kr 접속",
      "이 화면에서 알림 토글 켜기",
    ],
  },
};

export default function PushEnableGuide({ onClose }: { onClose: () => void }) {
  const reason = detectReason();
  const c = CONTENT[reason];
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-sm bg-white rounded-2xl shadow-2xl p-6 animate-in zoom-in-95 duration-300">
        <div className="text-3xl mb-2">🔔</div>
        <h3 className="text-lg font-bold text-slate-900 mb-1.5">{c.title}</h3>
        <p className="text-[13px] text-slate-600 mb-4 leading-relaxed">{c.desc}</p>
        <ol className="space-y-2 mb-5">
          {c.steps.map((s, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <span className="flex-shrink-0 w-5 h-5 mt-px bg-blue-100 text-blue-600 rounded-full text-[11px] font-bold flex items-center justify-center">{i + 1}</span>
              <span className="text-[13px] text-slate-700 leading-snug">{s}</span>
            </li>
          ))}
        </ol>
        <button
          onClick={onClose}
          className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold text-[15px] hover:bg-blue-700 transition-all active:scale-[0.98]"
        >
          알겠어요
        </button>
      </div>
    </div>
  );
}
