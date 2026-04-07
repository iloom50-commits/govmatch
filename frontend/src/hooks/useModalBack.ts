"use client";

import { useEffect, useCallback } from "react";

/**
 * 모바일 뒤로가기 시 모달만 닫기 (앱 종료 방지)
 * 모달이 열릴 때 history.pushState → 뒤로가기 시 popstate → onClose 호출
 */
export function useModalBack(isOpen: boolean, onClose: () => void) {
  const stableClose = useCallback(onClose, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    window.history.pushState({ modal: true }, "");

    const onPopState = () => {
      stableClose();
    };

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, [isOpen, stableClose]);
}
