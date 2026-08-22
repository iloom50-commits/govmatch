import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "이용 요금 — 크레딧 충전 안내",
  description:
    "지원금AI 이용 요금 안내. 지원금 찾기와 맞춤 알림은 무료, AI 상담·분석은 크레딧으로 이용합니다. 구독·정기결제 없이 필요한 만큼만 충전합니다.",
  alternates: { canonical: "https://www.govmatch.kr/pricing" },
};

/**
 * 충전팩 — backend/app/main.py 의 CREDIT_PACKS 와 같은 값이어야 한다.
 * 값을 바꿀 때는 반드시 양쪽을 함께 고친다.
 */
const PACKS = [
  { krw: 1900, credits: 2000, label: "가볍게 시작" },
  { krw: 5000, credits: 6000, label: "가장 많이 선택", best: true },
  { krw: 10000, credits: 14000, label: "넉넉하게" },
];

/** 크레딧 소모 — main.py 의 CREDIT_COST_ANALYZE / CREDIT_COST_CONSULT */
const USES = [
  { name: "AI 자금 상담", cost: 100, note: "상담 한 건당. 이어지는 질문은 추가 차감 없음" },
  { name: "공고 상세 분석", cost: 50, note: "공고 하나를 조건에 맞춰 분석" },
  { name: "공고 심화 상담", cost: 50, note: "특정 공고를 놓고 이어가는 상담" },
];

const FREE = [
  "지원사업 찾기 · 조건 매칭",
  "맞춤 공고 알림",
  "공고 목록 · 기본 정보 열람",
];

export default function PricingPage() {
  return (
    <main className="max-w-4xl mx-auto px-4 py-12 text-slate-800">
      <h1 className="text-2xl font-bold mb-3">이용 요금</h1>
      <p className="text-sm text-slate-600 leading-relaxed mb-10">
        지원사업을 <strong>찾는 것은 무료</strong>입니다. AI가 상담하고 분석하는 기능만
        크레딧으로 이용합니다. <strong>구독도 정기결제도 없습니다</strong> — 필요할 때 필요한 만큼만
        충전합니다.
      </p>

      {/* 무료 범위 */}
      <section className="mb-12">
        <h2 className="text-lg font-bold mb-3">무료로 쓰는 기능</h2>
        <ul className="text-sm space-y-1.5">
          {FREE.map((f) => (
            <li key={f} className="flex gap-2">
              <span className="text-emerald-600 font-bold">✓</span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
        <p className="text-sm text-slate-600 mt-3">
          가입하면 <strong className="text-indigo-600">500 크레딧</strong>을 드립니다. 결제 없이
          <strong> AI 상담 5회</strong> 또는 <strong>공고 분석 10건</strong>을 써 보실 수 있습니다.
        </p>
      </section>

      {/* 충전팩 */}
      <section className="mb-12">
        <h2 className="text-lg font-bold mb-1">크레딧 충전</h2>
        <p className="text-sm text-slate-500 mb-5">표시 금액은 부가세(VAT)가 포함된 최종 결제 금액입니다.</p>

        <div className="grid gap-4 sm:grid-cols-3">
          {PACKS.map((p) => (
            <div
              key={p.krw}
              className={`rounded-xl border p-5 ${
                p.best ? "border-indigo-400 bg-indigo-50/40" : "border-slate-200 bg-white"
              }`}
            >
              <div className="text-xs font-semibold text-slate-500 mb-2">{p.label}</div>
              <div className="text-2xl font-bold text-slate-900">
                {p.krw.toLocaleString()}
                <span className="text-base font-semibold text-slate-600">원</span>
              </div>
              <div className="mt-2 text-sm font-semibold text-indigo-700">
                {p.credits.toLocaleString()} 크레딧
              </div>
              <div className="mt-3 pt-3 border-t border-slate-200 text-xs text-slate-500 leading-relaxed">
                AI 상담 {Math.floor(p.credits / 100)}회
                <br />
                또는 공고 분석 {Math.floor(p.credits / 50)}건
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-500 mt-4 leading-relaxed">
          충전한 크레딧은 사용 기한이 없습니다. 결제는 카드·간편결제로 진행되며, 충전 즉시 잔액에
          반영됩니다.
        </p>
      </section>

      {/* 크레딧 사용처 */}
      <section className="mb-12">
        <h2 className="text-lg font-bold mb-4">크레딧을 쓰는 곳</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b-2 border-slate-300 text-left">
                <th className="py-2.5 pr-4 font-semibold">기능</th>
                <th className="py-2.5 pr-4 font-semibold whitespace-nowrap">크레딧</th>
                <th className="py-2.5 font-semibold">설명</th>
              </tr>
            </thead>
            <tbody>
              {USES.map((u) => (
                <tr key={u.name} className="border-b border-slate-200">
                  <td className="py-3 pr-4 font-semibold whitespace-nowrap">{u.name}</td>
                  <td className="py-3 pr-4 text-indigo-700 font-bold whitespace-nowrap">{u.cost}</td>
                  <td className="py-3 text-slate-600">{u.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          크레딧은 <strong>기능이 정상적으로 끝난 뒤에만</strong> 차감됩니다. 오류로 결과를 받지
          못하면 차감되지 않습니다.
        </p>
      </section>

      {/* 판매자 정보 */}
      <section className="mb-10 rounded-lg bg-slate-50 border border-slate-200 p-5">
        <h2 className="text-sm font-bold mb-3">판매자 정보</h2>
        <dl className="text-xs text-slate-600 space-y-1.5">
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-slate-500">상호</dt>
            <dd>밸류파인더</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-slate-500">대표자</dt>
            <dd>권오성</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-slate-500">사업자등록번호</dt>
            <dd>141-17-02215</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-slate-500">사업장 주소</dt>
            <dd>부산광역시 해운대구 센텀중앙로 145, 109동 3405호</dd>
          </div>
          <div className="flex gap-2">
            <dt className="w-24 shrink-0 text-slate-500">연락처</dt>
            <dd>010-5565-2299 · osung94@naver.com</dd>
          </div>
        </dl>
      </section>

      <section className="text-sm text-slate-600 leading-relaxed">
        <h2 className="text-lg font-bold mb-3 text-slate-800">환불</h2>
        <p>
          충전한 크레딧 중 <strong>사용하지 않은 분</strong>은 환불받으실 수 있습니다. 자세한 조건과
          신청 방법은{" "}
          <Link href="/refund" className="text-indigo-600 underline underline-offset-2">
            환불 정책
          </Link>
          에서 확인하십시오. 문의는{" "}
          <Link href="/support" className="text-indigo-600 underline underline-offset-2">
            고객상담
          </Link>
          으로 받습니다.
        </p>
      </section>
    </main>
  );
}
