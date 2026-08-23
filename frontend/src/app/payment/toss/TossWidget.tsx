"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { loadTossPayments, ANONYMOUS } from "@tosspayments/tosspayments-sdk";

/**
 * 토스페이먼츠 결제위젯 — 크레딧 충전.
 *
 * 왜 따로 두는가:
 *   기존 충전(PaymentModal)은 PortOne 을 쓰고 실사용자가 쓰고 있다. 그 경로를 건드리지 않고
 *   나란히 둔다. 토스 심사 통과 후 이쪽으로 옮긴다.
 *
 * 금액 검증:
 *   결제 전에 서버가 주문(orderId·금액)을 만들어 두고, 승인할 때 저장된 금액과 대조한다.
 *   브라우저가 보낸 값을 믿지 않는다 — 이 프로젝트에는 결제창을 닫았는데 구독이 시작된
 *   사고 이력이 있다.
 *
 * 키:
 *   기본값은 아래 STORE_TEST_KEY(밸류파인더 상점의 테스트 키)다. 환경변수
 *   NEXT_PUBLIC_TOSS_CLIENT_KEY 로 덮을 수 있지만, 위젯용(gck) 형식일 때만 쓴다.
 *
 *   2026-08-23: Vercel 에 있던 NEXT_PUBLIC_TOSS_CLIENT_KEY 를 삭제했다. 값이
 *   test_ck_D5GePWvyJnrK0W0k6q8gLzN97Emo(API 개별 연동 키이자 토스 문서의 공개 샘플)라
 *   라이브에서만 위젯이 뜨지 않았다. 심사 통과 후 라이브 키를 넣을 때 이 변수를 다시 쓴다.
 *
 *   시크릿 키는 여기에 절대 두지 않는다 — 승인 API 는 백엔드(TOSS_SECRET_KEY)에서 호출한다.
 */
const DOCS_SAMPLE_KEY = "test_gck_docs_Ovk5rk1EwkEbP0W43n07xlzm";
// 밸류파인더 상점(계정 1612342)의 테스트 클라이언트 키.
// 클라이언트 키는 브라우저에 노출되는 공개 값이라 코드에 두어도 된다. 테스트 키라 실결제도 되지 않는다.
// 라이브 키는 절대 여기 두지 않는다 — 심사 통과 후 NEXT_PUBLIC_TOSS_CLIENT_KEY 로 주입한다.
const STORE_TEST_KEY = "test_gck_yL0qZ4G1VODo4ZYyDemoroWb2MQY";

// 위젯 SDK 는 "주문서형·결제창형 연동 키"(gck) 만 받는다. "API 개별 연동 키"(ck) 를 주면
//   "결제위젯 연동 키의 클라이언트 키로 SDK를 연동해주세요"
// 로 거부한다. 실제로 Vercel 에 ck 키가 들어 있어 라이브에서만 화면이 안 떴다.
// 그래서 환경변수를 그대로 믿지 않고, 형식이 맞을 때만 쓴다.
const ENV_KEY = (process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY || "").trim();
const ENV_KEY_USABLE = /^(test|live)_gck_/.test(ENV_KEY);
const CLIENT_KEY = ENV_KEY_USABLE ? ENV_KEY : STORE_TEST_KEY;
const ENV_KEY_IGNORED = ENV_KEY.length > 0 && !ENV_KEY_USABLE;
const IS_SAMPLE = CLIENT_KEY === DOCS_SAMPLE_KEY;
const IS_TEST = CLIENT_KEY.startsWith("test_");

const API = process.env.NEXT_PUBLIC_API_URL;

/** backend CREDIT_PACKS 와 같은 값. 바꿀 때 양쪽을 함께 고친다. */
const PACKS = [
  { krw: 1900, credits: 2000 },
  { krw: 5000, credits: 6000 },
  { krw: 10000, credits: 14000 },
];

type Phase = "loading" | "ready" | "paying" | "confirming" | "done" | "failed";

export default function TossWidget() {
  const params = useSearchParams();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("loading");
  const [err, setErr] = useState<string | null>(null);
  const [picked, setPicked] = useState(1);
  const [balance, setBalance] = useState<number | null>(null);
  // 위젯 인스턴스는 리렌더와 무관하게 유지해야 한다
  const widgetsRef = useRef<any>(null);
  // StrictMode 는 effect 를 두 번 실행한다. 승인을 두 번 보내지 않기 위한 잠금.
  const confirmedRef = useRef(false);

  // 결제창에서 돌아온 화면인지 — 이때는 위젯을 띄우지 않고 결과만 보여준다
  const isReturn = !!(params.get("paymentKey") || params.get("code"));

  const token = () =>
    typeof window === "undefined" ? "" : localStorage.getItem("auth_token") || "";

  // ── 결제창에서 돌아왔을 때: 승인 ───────────────────────
  useEffect(() => {
    const paymentKey = params.get("paymentKey");
    const orderId = params.get("orderId");
    const amount = params.get("amount");
    const code = params.get("code");

    if (confirmedRef.current) return;

    // 실패로 돌아온 경우 — 토스가 code·message 를 붙여 보낸다
    if (code) {
      confirmedRef.current = true;
      setErr(params.get("message") || "결제가 취소되었습니다.");
      setPhase("failed");
      return;
    }
    if (!paymentKey || !orderId || !amount) return;
    confirmedRef.current = true;

    (async () => {
      setPhase("confirming");
      try {
        const res = await fetch(`${API}/api/toss/confirm`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token()}`,
          },
          body: JSON.stringify({
            order_id: orderId,
            payment_key: paymentKey,
            amount: Number(amount),
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.ok) {
          setErr(data.detail || "결제 승인에 실패했습니다.");
          setPhase("failed");
          return;
        }
        setBalance(typeof data.credits === "number" ? data.credits : null);
        setPhase("done");
      } catch {
        setErr("결제 승인 중 통신 오류가 발생했습니다. 고객상담으로 알려주십시오.");
        setPhase("failed");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 결제 화면일 때: 위젯 로드 ──────────────────────────
  useEffect(() => {
    if (isReturn) return;
    let alive = true;
    (async () => {
      try {
        const sdk = await loadTossPayments(CLIENT_KEY);
        if (!alive) return;
        const widgets = sdk.widgets({ customerKey: ANONYMOUS });
        widgetsRef.current = widgets;
        await widgets.setAmount({ currency: "KRW", value: PACKS[picked].krw });
        await Promise.all([
          widgets.renderPaymentMethods({ selector: "#toss-methods", variantKey: "DEFAULT" }),
          widgets.renderAgreement({ selector: "#toss-agreement", variantKey: "AGREEMENT" }),
        ]);
        if (alive) setPhase("ready");
      } catch (e: any) {
        if (alive) {
          setErr(e?.message || e?.code || String(e));
          setPhase("failed");
        }
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 팩을 바꾸면 위젯 금액도 따라 바뀌어야 한다 — 안 그러면 표시가와 결제가가 어긋난다
  useEffect(() => {
    if (phase !== "ready" || !widgetsRef.current) return;
    widgetsRef.current.setAmount({ currency: "KRW", value: PACKS[picked].krw }).catch(() => {});
  }, [picked, phase]);

  const pay = async () => {
    if (!widgetsRef.current) return;
    if (!token()) {
      alert("충전하려면 먼저 로그인해 주십시오.");
      router.push("/");
      return;
    }
    setPhase("paying");
    setErr(null);
    try {
      // 서버가 주문번호와 금액을 저장한다. 승인할 때 이 금액과 대조하므로
      // 브라우저에서 금액을 바꿔 보내도 통과하지 않는다.
      const res = await fetch(`${API}/api/toss/order`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token()}`,
        },
        body: JSON.stringify({ amount_krw: PACKS[picked].krw }),
      });
      const order = await res.json().catch(() => ({}));
      if (!res.ok || !order.ok) throw new Error(order.detail || "주문을 만들지 못했습니다.");

      await widgetsRef.current.requestPayment({
        orderId: order.order_id,
        orderName: `지원금AI 크레딧 ${PACKS[picked].credits.toLocaleString()}`,
        successUrl: `${window.location.origin}/payment/toss`,
        failUrl: `${window.location.origin}/payment/toss`,
      });
    } catch (e: any) {
      setErr(e?.message || e?.code || String(e));
      setPhase("ready");
    }
  };

  // ── 결제창에서 돌아온 결과 화면 ───────────────────────
  if (isReturn) {
    return (
      <main className="max-w-lg mx-auto px-4 py-20 text-slate-800 text-center">
        {phase === "confirming" && (
          <>
            <div className="text-2xl mb-3">⏳</div>
            <h1 className="text-lg font-bold mb-2">결제를 확인하고 있습니다</h1>
            <p className="text-sm text-slate-600">잠시만 기다려 주십시오. 창을 닫지 마십시오.</p>
          </>
        )}

        {phase === "done" && (
          <>
            <div className="text-3xl mb-3">✅</div>
            <h1 className="text-xl font-bold mb-2">충전이 완료되었습니다</h1>
            {balance !== null && (
              <p className="text-sm text-slate-600 mb-6">
                현재 잔액{" "}
                <strong className="text-indigo-600">{balance.toLocaleString()} 크레딧</strong>
              </p>
            )}
            <a
              href="/"
              className="inline-block rounded-xl bg-indigo-600 px-6 py-3 text-white text-sm font-bold hover:bg-indigo-700 transition"
            >
              서비스로 돌아가기
            </a>
          </>
        )}

        {phase === "failed" && (
          <>
            <div className="text-3xl mb-3">⚠️</div>
            <h1 className="text-xl font-bold mb-2">결제가 완료되지 않았습니다</h1>
            <p className="text-sm text-slate-600 mb-6">{err}</p>
            <a
              href="/payment/toss"
              className="inline-block rounded-xl bg-slate-800 px-6 py-3 text-white text-sm font-bold hover:bg-slate-900 transition"
            >
              다시 시도하기
            </a>
            <p className="text-xs text-slate-500 mt-6 leading-relaxed">
              결제 금액이 빠져나갔는데 크레딧이 들어오지 않았다면{" "}
              <a href="/support" className="text-indigo-600 underline underline-offset-2">
                고객상담
              </a>
              으로 알려주십시오. 결제 내역을 확인해 처리해 드립니다.
            </p>
          </>
        )}
      </main>
    );
  }

  // ── 결제 화면 ─────────────────────────────────────────
  return (
    <main className="max-w-2xl mx-auto px-4 py-10 text-slate-800">
      <h1 className="text-xl font-bold mb-1">크레딧 충전</h1>
      <p className="text-sm text-slate-600 mb-6">
        결제 금액은 부가세(VAT)가 포함된 최종 금액입니다.
      </p>

      {IS_TEST && (
        <div className="mb-6 rounded-lg border-2 border-amber-400 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <strong>테스트 결제 화면입니다.</strong> 실제로 돈이 빠져나가지 않습니다.
          {ENV_KEY_IGNORED && (
            <div className="mt-1 text-amber-800">
              환경변수 <code>NEXT_PUBLIC_TOSS_CLIENT_KEY</code> 가 위젯용 키(<code>gck</code>)가
              아니어서 무시했습니다. 「주문서형·결제창형 연동 키」의 클라이언트 키로 바꿔 주십시오.
            </div>
          )}
          {IS_SAMPLE && (
            <div className="mt-1 text-amber-800">
              지금은 <strong>토스 공식 문서의 공개 샘플 키</strong>로 떠 있습니다. 우리 상점과
              연결돼 있지 않으므로 <strong>심사 자료로 쓰면 안 됩니다.</strong>
            </div>
          )}
        </div>
      )}

      {/* 상품 선택 */}
      <div className="grid grid-cols-3 gap-3 mb-7">
        {PACKS.map((p, i) => (
          <button
            key={p.krw}
            onClick={() => setPicked(i)}
            className={`rounded-xl border p-4 text-left transition ${
              i === picked
                ? "border-indigo-500 bg-indigo-50/50 ring-1 ring-indigo-300"
                : "border-slate-200 hover:border-slate-300"
            }`}
          >
            <div className="text-lg font-bold">
              {p.krw.toLocaleString()}
              <span className="text-sm font-semibold text-slate-600">원</span>
            </div>
            <div className="text-[13px] font-semibold text-indigo-700 mt-0.5">
              {p.credits.toLocaleString()} 크레딧
            </div>
          </button>
        ))}
      </div>

      {err && (
        <div className="mb-5 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-[13px] text-red-800">
          {err}
        </div>
      )}

      <div id="toss-methods" />
      <div id="toss-agreement" className="mt-3" />

      <button
        onClick={pay}
        disabled={phase !== "ready"}
        className="mt-6 w-full rounded-xl bg-indigo-600 py-3.5 text-white font-bold disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-indigo-700 transition"
      >
        {phase === "loading"
          ? "결제 수단을 불러오는 중…"
          : phase === "paying"
          ? "결제창을 여는 중…"
          : `${PACKS[picked].krw.toLocaleString()}원 결제하기`}
      </button>

      <p className="mt-4 text-xs text-slate-500 leading-relaxed">
        충전한 크레딧의 유효기간은 충전일로부터 12개월입니다. 한 번도 사용하지 않은 경우 결제 금액
        전액을 환불해 드립니다. 자세한 내용은{" "}
        <a href="/refund" className="text-indigo-600 underline underline-offset-2">
          환불 정책
        </a>
        과{" "}
        <a href="/pricing" className="text-indigo-600 underline underline-offset-2">
          이용 요금
        </a>
        을 확인하십시오.
      </p>

      <div className="mt-8 pt-5 border-t border-slate-200 text-[11px] text-slate-500 leading-relaxed">
        밸류파인더 | 대표 권오성 | 사업자등록번호 141-17-02215 | 부산광역시 해운대구 센텀중앙로 145,
        109동 3405호 | Tel 010-5565-2299 | osung94@naver.com
      </div>
    </main>
  );
}
