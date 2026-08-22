import { Metadata } from "next";

export const metadata: Metadata = {
  title: "환불 정책",
  description: "지원금AI 환불 정책 — 크레딧 충전 및 환불 절차 안내",
  alternates: { canonical: "https://www.govmatch.kr/refund" },
};

export default function RefundPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12 text-slate-800">
      <h1 className="text-2xl font-bold mb-8">환불 정책</h1>
      <p className="text-sm text-slate-500 mb-6">시행일: 2026년 8월 12일 (최초 시행 2026년 3월 27일)</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="text-lg font-bold mb-2">1. 크레딧 이용 방식</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>지원금 매칭(찾기)과 맞춤 공고 알림은 무료로 제공됩니다.</li>
            <li>AI 상담·분석 등 유료 기능은 크레딧을 선불로 충전하여 이용합니다. 충전 금액과 지급 크레딧은 <a href="/pricing" className="text-indigo-600 underline underline-offset-2">이용 요금</a>에서 확인하실 수 있으며, 충전팩에 따라 추가 크레딧이 함께 지급됩니다.</li>
            <li>충전한 크레딧의 유효기간은 충전일로부터 <strong>12개월</strong>이며, 유효기간 내 즉시 이용 가능한 디지털 콘텐츠입니다.</li>
            <li>구독·정기결제·자동결제·무료 체험은 제공하지 않으며, 필요한 만큼만 충전합니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">2. 환불 규정</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>충전한 크레딧을 <strong>한 번도 사용하지 않은 경우</strong>, 해당 충전 건의 <strong>결제 금액 전액</strong>을 환불해 드립니다.</li>
            <li>해당 충전분으로 <strong>크레딧을 한 건이라도 사용하신 경우에는 환불이 불가</strong>합니다. AI 상담·분석은 요청 즉시 제공이 완료되는 디지털 서비스로, 사용 후에는 원상회복이 불가능하기 때문입니다.</li>
            <li>환불 시 PG(결제대행) 결제수수료가 공제될 수 있습니다.</li>
            <li>가입 보너스, 프로모션 등으로 무상 지급된 크레딧은 환불 대상이 아닙니다.</li>
          </ul>
          <p className="mt-2 text-slate-600">
            충전 전에 <a href="/pricing" className="text-indigo-600 underline underline-offset-2">이용 요금</a>에서
            크레딧 사용량을 확인하시고, 가입 시 무료로 드리는 500 크레딧으로 먼저 체험해 보시기를 권해
            드립니다.
          </p>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">3. 환불 신청 방법</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>환불은 고객센터(이메일: iloom50@gmail.com) 문의를 통해 수동으로 처리됩니다.</li>
            <li>서비스 내 자동(셀프) 환불 기능은 제공하지 않습니다.</li>
            <li>환불 신청 시 회원 이메일, 충전 일자, 환불 사유를 기재해 주세요.</li>
            <li>환불은 신청일로부터 영업일 기준 3~5일 이내, 원래 결제 수단으로 처리됩니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">4. 환불 불가 사유</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>해당 충전분의 크레딧을 한 건이라도 사용한 경우</li>
            <li>가입 보너스·프로모션 등 무상으로 지급된 크레딧</li>
            <li>유효기간(충전일로부터 12개월)이 지난 크레딧</li>
            <li>이용약관 위반으로 인한 서비스 이용 제한 또는 계정 정지</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">5. 기타</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>본 환불 정책은 전자상거래 등에서의 소비자보호에 관한 법률에 따릅니다.</li>
            <li>회사는 관련 법령 변경 시 환불 정책을 수정할 수 있으며, 변경 시 서비스 내 공지합니다.</li>
          </ul>
        </div>

        <div className="pt-6 border-t border-slate-200 text-slate-500">
          <p>밸류파인더 | 대표: 권오성</p>
          <p>문의: iloom50@gmail.com</p>
        </div>
      </section>
    </main>
  );
}
