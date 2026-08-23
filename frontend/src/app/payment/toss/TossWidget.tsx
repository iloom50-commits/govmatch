"use client";

import { useEffect, useRef, useState } from "react";
import { loadTossPayments, ANONYMOUS } from "@tosspayments/tosspayments-sdk";

/**
 * 토스페이먼츠 결제위젯 — PG 심사용 결제경로 확인 페이지.
 *
 * 왜 따로 두는가:
 *   기존 충전(PaymentModal)은 PortOne 을 쓰고 실사용자가 쓰고 있다. 그 경로를 건드리지 않고
 *   토스 결제창만 띄워 심사 자료(결제경로)를 만들기 위해 분리했다.
 *
 * 키:
 *   NEXT_PUBLIC_TOSS_CLIENT_KEY 로 주입한다. 없으면 토스 공식 문서의 공개 샘플 키로 뜨는데,
 *   그건 우리 상점과 연결돼 있지 않으므로 심사 자료로 쓰면 안 된다. 화면에 그 사실을 표시한다.
 *   시크릿 키는 여기에 절대 두지 않는다 — 승인 API 는 백엔드에서 호출한다.
 */
const DOCS_SAMPLE_KEY = "test_gck_docs_Ovk5rk1EwkEbP0W43n07xlzm";
// 밸류파인더 상점(계정 1612342)의 테스트 클라이언트 키.
// 클라이언트 키는 브라우저에 노출되는 공개 값이라 코드에 두어도 된다. 테스트 키라 실결제도 되지 않는다.
// 라이브 키는 절대 여기 두지 않는다 — 심사 통과 후 NEXT_PUBLIC_TOSS_CLIENT_KEY 로 주입한다.
const STORE_TEST_KEY = "test_gck_yL0qZ4G1VODo4ZYyDemoroWb2MQY";
const CLIENT_KEY = process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY || STORE_TEST_KEY;
const IS_SAMPLE = CLIENT_KEY === DOCS_SAMPLE_KEY;
const IS_TEST = CLIENT_KEY.startsWith("test_");

/** backend CREDIT_PACKS 와 같은 값. 바꿀 때 양쪽을 함께 고친다. */
const PACKS = [
  { krw: 1900, credits: 2000 },
  { krw: 5000, credits: 6000 },
  { krw: 10000, credits: 14000 },
];

export default function TossWidget() {
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [picked, setPicked] = useState(1);
  const [paying, setPaying] = useState(false);
  // 위젯 인스턴스는 리렌더와 무관하게 유지해야 한다
  const widgetsRef = useRef<any>(null);

  // 위젯 로드 — 마운트 시 한 번
  useEffect(() => {
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
        if (alive) setReady(true);
      } catch (e: any) {
        if (alive) setErr(e?.message || e?.code || String(e));
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 팩을 바꾸면 위젯 금액도 따라 바뀌어야 한다 — 안 그러면 표시가와 결제가가 어긋난다
  useEffect(() => {
    if (!ready || !widgetsRef.current) return;
    widgetsRef.current.setAmount({ currency: "KRW", value: PACKS[picked].krw }).catch(() => {});
  }, [picked, ready]);

  const pay = async () => {
    if (!widgetsRef.current) return;
    setPaying(true);
    try {
      const pack = PACKS[picked];
      await widgetsRef.current.requestPayment({
        orderId: "gm" + crypto.randomUUID().replace(/-/g, "").slice(0, 24),
        orderName: `지원금AI 크레딧 ${pack.credits.toLocaleString()}`,
        successUrl: `${window.location.origin}/payment/toss?result=success`,
        failUrl: `${window.location.origin}/payment/toss?result=fail`,
      });
    } catch (e: any) {
      setErr(e?.message || e?.code || String(e));
      setPaying(false);
    }
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-10 text-slate-800">
      <h1 className="text-xl font-bold mb-1">크레딧 충전</h1>
      <p className="text-sm text-slate-600 mb-6">
        결제 금액은 부가세(VAT)가 포함된 최종 금액입니다.
      </p>

      {IS_TEST && (
        <div className="mb-6 rounded-lg border-2 border-amber-400 bg-amber-50 px-4 py-3 text-[13px] text-amber-900">
          <strong>테스트 결제 화면입니다.</strong> 실제로 돈이 빠져나가지 않습니다.
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
              i === picked ? "border-indigo-500 bg-indigo-50/50 ring-1 ring-indigo-300" : "border-slate-200 hover:border-slate-300"
            }`}
          >
            <div className="text-lg font-bold">{p.krw.toLocaleString()}<span className="text-sm font-semibold text-slate-600">원</span></div>
            <div className="text-[13px] font-semibold text-indigo-700 mt-0.5">{p.credits.toLocaleString()} 크레딧</div>
          </button>
        ))}
      </div>

      {err && (
        <div className="mb-5 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-[13px] text-red-800">
          결제 화면을 불러오지 못했습니다 — {err}
        </div>
      )}

      <div id="toss-methods" />
      <div id="toss-agreement" className="mt-3" />

      <button
        onClick={pay}
        disabled={!ready || paying}
        className="mt-6 w-full rounded-xl bg-indigo-600 py-3.5 text-white font-bold disabled:bg-slate-300 disabled:cursor-not-allowed hover:bg-indigo-700 transition"
      >
        {!ready ? "결제 수단을 불러오는 중…" : paying ? "결제창을 여는 중…" : `${PACKS[picked].krw.toLocaleString()}원 결제하기`}
      </button>

      <p className="mt-4 text-xs text-slate-500 leading-relaxed">
        충전한 크레딧의 유효기간은 충전일로부터 12개월입니다. 한 번도 사용하지 않은 경우 결제 금액
        전액을 환불해 드립니다. 자세한 내용은{" "}
        <a href="/refund" className="text-indigo-600 underline underline-offset-2">환불 정책</a>과{" "}
        <a href="/pricing" className="text-indigo-600 underline underline-offset-2">이용 요금</a>을
        확인하십시오.
      </p>

      <div className="mt-8 pt-5 border-t border-slate-200 text-[11px] text-slate-500 leading-relaxed">
        밸류파인더 | 대표 권오성 | 사업자등록번호 141-17-02215 |
        부산광역시 해운대구 센텀중앙로 145, 109동 3405호 | Tel 010-5565-2299 | osung94@naver.com
      </div>
    </main>
  );
}
