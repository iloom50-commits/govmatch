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
      <p className="text-sm text-slate-500 mb-6">시행일: 2026년 3월 27일</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="text-lg font-bold mb-2">1. 크레딧 이용 방식</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>지원금 매칭(찾기)과 맞춤 공고 알림은 무료로 제공됩니다.</li>
            <li>AI 상담·분석 등 유료 기능은 크레딧(1크레딧 = 1원)을 선불로 충전하여 이용합니다.</li>
            <li>구독·정기결제·자동결제·무료 체험은 제공하지 않으며, 필요한 만큼만 충전합니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">2. 환불 규정</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>유료로 충전한 크레딧 중 <strong>미사용분</strong>에 한하여 환불이 가능합니다.</li>
            <li>이미 사용(차감)된 크레딧은 환불 대상이 아닙니다.</li>
            <li>환불 시 PG(결제대행) 결제수수료가 공제될 수 있습니다.</li>
            <li>가입 보너스, 프로모션 등으로 무상 지급된 크레딧은 환불되지 않습니다.</li>
          </ul>
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
            <li>이미 사용(차감)된 크레딧</li>
            <li>가입 보너스·프로모션 등 무상으로 지급된 크레딧</li>
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
          <p>밸류파인더 | 대표: 오성근</p>
          <p>문의: iloom50@gmail.com</p>
        </div>
      </section>
    </main>
  );
}
