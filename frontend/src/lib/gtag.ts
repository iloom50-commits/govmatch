/** GA4 이벤트 추적 유틸리티 */

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export const GA_ID = process.env.NEXT_PUBLIC_GA_ID || '';

export function trackEvent(action: string, params?: Record<string, string | number | boolean>) {
  if (typeof window !== 'undefined' && window.gtag && GA_ID) {
    window.gtag('event', action, params);
  }
}

// 주요 이벤트 헬퍼
export const ga = {
  /** 회원가입 완료 */
  signup: (method: string) => trackEvent('sign_up', { method }),
  /** 로그인 */
  login: (method: string) => trackEvent('login', { method }),
  /** AI 매칭 실행 */
  match: () => trackEvent('ai_match'),
  /** AI 채팅 */
  chat: () => trackEvent('ai_chat'),
  /** 공고 저장 */
  save: (announcementId: number) => trackEvent('save_announcement', { announcement_id: announcementId }),
  /** PWA 설치 */
  pwaInstall: () => trackEvent('pwa_install'),
  /** 플랜 선택 */
  selectPlan: (plan: string) => trackEvent('select_plan', { plan }),
  /** 페이지 뷰 (SPA 전환 시) */
  pageView: (path: string) => trackEvent('page_view', { page_path: path }),
};
