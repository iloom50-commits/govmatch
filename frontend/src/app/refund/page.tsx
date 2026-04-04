import { Metadata } from "next";

export const metadata: Metadata = {
  title: "환불 정책",
  description: "지원금AI 환불 정책 — 유료 플랜 결제 취소 및 환불 절차 안내",
  alternates: { canonical: "https://govmatch.kr/refund" },
};

export default function RefundPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12 text-slate-800">
      <h1 className="text-2xl font-bold mb-8">환불 정책</h1>
      <p className="text-sm text-slate-500 mb-6">시행일: 2026년 3월 27일</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="text-lg font-bold mb-2">1. 무료 체험 기간</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>LITE 플랜: 카드 등록 후 1개월(30일) 무료 체험이 제공됩니다.</li>
            <li>PRO 플랜: 카드 등록 후 1주일(7일) 무료 체험이 제공됩니다.</li>
            <li>무료 체험 기간 내 구독을 해지하면 요금이 청구되지 않습니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">2. 구독 해지</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>회원은 서비스 내 &quot;구독 해지&quot; 버튼을 통해 언제든지 구독을 해지할 수 있습니다.</li>
            <li>구독 해지 시 이미 결제된 기간의 잔여일까지 서비스를 이용할 수 있습니다.</li>
            <li>해지 후 다음 결제일에 자동결제가 중단됩니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">3. 환불 규정</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>결제일로부터 7일 이내, 서비스를 이용하지 않은 경우: 전액 환불</li>
            <li>결제일로부터 7일 이내, 서비스를 이용한 경우: 이용일수에 해당하는 금액을 공제 후 환불</li>
            <li>결제일로부터 7일 경과: 환불 불가 (잔여 기간까지 서비스 이용 가능)</li>
            <li>환불 금액 산정: 월 이용료 / 30일 x 잔여일수</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">4. 환불 신청 방법</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>이메일: iloom50@gmail.com</li>
            <li>환불 신청 시 회원 이메일, 결제일, 환불 사유를 기재해 주세요.</li>
            <li>환불은 신청일로부터 영업일 기준 3~5일 이내 처리됩니다.</li>
            <li>환불은 원래 결제 수단으로 진행됩니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">5. 환불 불가 사유</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>이용약관 위반으로 인한 서비스 이용 제한 또는 계정 정지</li>
            <li>회원의 귀책사유로 서비스를 이용하지 못한 경우</li>
            <li>무료 체험 기간 중 해지하지 않아 자동결제된 경우 (단, 결제 후 7일 이내 미이용 시 환불 가능)</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">6. 기타</h2>
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
