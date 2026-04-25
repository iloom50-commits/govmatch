"use client";

import { useEffect, useRef } from "react";

/**
 * 모바일 뒤로가기 시 모달만 닫기 (앱 종료 방지)
 * 모달이 열릴 때 history.pushState → 뒤로가기 시 popstate → onClose 호출
 * useRef로 콜백을 보관해 isOpen 변경 시에만 pushState가 한 번 실행됨
 */
export function useModalBack(isOpen: boolean, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    window.history.pushState({ modal: true }, "");

    const onPopState = () => onCloseRef.current();
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [isOpen]); // isOpen 변경 시에만 실행 — 콜백 변경으로 재실행 없음
}
