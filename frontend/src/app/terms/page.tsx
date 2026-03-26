export default function TermsPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12 text-slate-800">
      <h1 className="text-2xl font-bold mb-8">이용약관</h1>
      <p className="text-sm text-slate-500 mb-6">시행일: 2026년 3월 27일</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="text-lg font-bold mb-2">제1조 (목적)</h2>
          <p>이 약관은 밸류파인더(이하 &quot;회사&quot;)가 운영하는 지원금GO(이하 &quot;서비스&quot;)의 이용 조건 및 절차, 회사와 이용자의 권리·의무 및 책임사항을 규정함을 목적으로 합니다.</p>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제2조 (정의)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>&quot;서비스&quot;란 회사가 제공하는 AI 기반 정부지원사업 매칭, 상담, 알림 등의 온라인 서비스를 말합니다.</li>
            <li>&quot;이용자&quot;란 이 약관에 따라 서비스를 이용하는 회원 및 비회원을 말합니다.</li>
            <li>&quot;회원&quot;이란 서비스에 가입하여 이용자 아이디(ID)를 부여받은 자를 말합니다.</li>
            <li>&quot;유료 서비스&quot;란 회사가 유료로 제공하는 각종 서비스 및 콘텐츠를 말합니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제3조 (약관의 효력 및 변경)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>이 약관은 서비스 화면에 게시하거나 기타의 방법으로 이용자에게 공지함으로써 효력이 발생합니다.</li>
            <li>회사는 관련 법령을 위반하지 않는 범위에서 이 약관을 개정할 수 있습니다.</li>
            <li>약관이 변경되는 경우 회사는 변경 내용을 시행일 7일 전부터 서비스 내 공지사항을 통해 고지합니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제4조 (회원가입)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>이용자는 회사가 정한 가입 양식에 따라 회원 정보를 기입한 후 이 약관에 동의한다는 의사표시를 함으로써 회원가입을 신청합니다.</li>
            <li>회사는 제1항과 같이 회원으로 가입할 것을 신청한 이용자 중 다음 각 호에 해당하지 않는 한 회원으로 등록합니다.</li>
            <li>회원가입은 이메일 또는 소셜 로그인(카카오, 네이버, Google)을 통해 가능합니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제5조 (서비스 이용)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>서비스 이용은 회사의 업무상 또는 기술상 특별한 지장이 없는 한 연중무휴, 1일 24시간 운영을 원칙으로 합니다.</li>
            <li>회사는 시스템 점검, 교체 및 고장, 통신 두절 등의 사유가 발생한 경우에는 서비스의 제공을 일시적으로 중단할 수 있습니다.</li>
            <li>AI 상담 서비스는 정보 제공 목적이며, 법률적·행정적 효력을 갖지 않습니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제6조 (유료 서비스)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>유료 서비스의 종류 및 이용 요금은 서비스 내 안내 페이지에 게시합니다.</li>
            <li>유료 서비스는 월 정기결제(구독) 방식으로 제공되며, 결제일로부터 30일간 이용 가능합니다.</li>
            <li>무료 체험 기간이 제공되는 경우, 체험 기간 종료 후 자동으로 유료 결제가 진행됩니다.</li>
            <li>결제는 신용카드, 간편결제(카카오페이 등)를 통해 이루어집니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제7조 (구독 해지 및 환불)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>회원은 언제든지 서비스 내에서 구독을 해지할 수 있습니다.</li>
            <li>구독 해지 시 이미 결제된 기간의 잔여일까지는 서비스를 이용할 수 있습니다.</li>
            <li>환불 정책은 별도의 환불 정책 페이지에 따릅니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제8조 (이용자의 의무)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>이용자는 서비스 이용 시 관계 법령, 이 약관의 규정, 이용 안내 등을 준수하여야 합니다.</li>
            <li>이용자는 타인의 개인정보를 도용하여 회원가입 또는 서비스를 이용하여서는 안 됩니다.</li>
            <li>이용자는 서비스를 이용하여 얻은 정보를 회사의 사전 승낙 없이 영리 목적으로 이용하거나 제3자에게 제공하여서는 안 됩니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제9조 (면책조항)</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>회사는 천재지변, 전쟁 등 불가항력적 사유로 서비스를 제공할 수 없는 경우에는 서비스 제공에 관한 책임이 면제됩니다.</li>
            <li>AI 상담 결과는 참고 정보이며, 실제 지원사업 신청 및 선정은 해당 기관의 심사에 따릅니다.</li>
            <li>회사는 이용자가 서비스를 통해 얻은 정보에 대한 정확성, 신뢰성에 대하여 보증하지 않습니다.</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">제10조 (분쟁 해결)</h2>
          <p>서비스 이용과 관련하여 회사와 이용자 간에 분쟁이 발생한 경우, 쌍방 간 협의에 의해 해결함을 원칙으로 합니다. 협의가 이루어지지 않는 경우 관할 법원은 회사의 소재지를 관할하는 법원으로 합니다.</p>
        </div>

        <div className="pt-6 border-t border-slate-200 text-slate-500">
          <p>밸류파인더 | 대표: 오성근</p>
          <p>문의: iloom50@gmail.com</p>
        </div>
      </section>
    </main>
  );
}
