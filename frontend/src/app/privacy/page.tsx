export default function PrivacyPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12 text-slate-800">
      <h1 className="text-2xl font-bold mb-8">개인정보 처리방침</h1>

      <p className="text-sm text-slate-500 mb-6">시행일: 2026년 3월 23일</p>

      <section className="space-y-6 text-sm leading-relaxed">
        <div>
          <h2 className="text-lg font-bold mb-2">1. 개인정보의 수집 및 이용 목적</h2>
          <p>지원금GO(이하 &quot;서비스&quot;)은 다음의 목적을 위해 개인정보를 처리합니다.</p>
          <ul className="list-disc ml-5 mt-2 space-y-1">
            <li>회원 가입 및 관리: 회원제 서비스 이용에 따른 본인 확인, 서비스 부정이용 방지</li>
            <li>서비스 제공: 맞춤형 정부지원금 매칭, AI 상담, 알림 서비스 제공</li>
            <li>고충 처리: 민원인의 신원 확인, 민원사항 확인, 처리결과 통보</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">2. 수집하는 개인정보 항목</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li><strong>이메일 회원가입:</strong> 이메일, 비밀번호, 회사명</li>
            <li><strong>카카오 로그인:</strong> 카카오 고유 ID, 닉네임, 이메일(선택)</li>
            <li><strong>네이버 로그인:</strong> 네이버 고유 ID, 닉네임, 이메일(선택)</li>
            <li><strong>Google 로그인:</strong> Google 고유 ID, 이름, 이메일</li>
            <li><strong>서비스 이용 과정에서 자동 수집:</strong> 접속 IP, 접속 일시, 브라우저 정보</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">3. 개인정보의 보유 및 이용 기간</h2>
          <p>회원 탈퇴 시까지 보유하며, 탈퇴 즉시 파기합니다. 단, 관계 법령에 따라 보존이 필요한 경우 해당 법령에서 정한 기간 동안 보관합니다.</p>
          <ul className="list-disc ml-5 mt-2 space-y-1">
            <li>계약 또는 청약철회 등에 관한 기록: 5년 (전자상거래법)</li>
            <li>대금결제 및 재화 등의 공급에 관한 기록: 5년 (전자상거래법)</li>
            <li>소비자의 불만 또는 분쟁처리에 관한 기록: 3년 (전자상거래법)</li>
            <li>웹사이트 방문기록: 3개월 (통신비밀보호법)</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">4. 개인정보의 제3자 제공</h2>
          <p>서비스는 원칙적으로 이용자의 개인정보를 제3자에게 제공하지 않습니다. 다만, 이용자가 사전에 동의한 경우 또는 법령의 규정에 의한 경우에는 예외로 합니다.</p>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">5. 개인정보의 파기 절차 및 방법</h2>
          <p>이용자의 개인정보는 수집 및 이용 목적이 달성된 후에는 지체 없이 파기합니다. 전자적 파일 형태의 정보는 복구할 수 없는 방법으로 영구 삭제하며, 종이에 출력된 개인정보는 분쇄기로 분쇄하거나 소각합니다.</p>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">6. 개인정보 보호책임자</h2>
          <ul className="list-disc ml-5 space-y-1">
            <li>책임자: 밸류파인더 대표</li>
            <li>이메일: iloom50@gmail.com</li>
          </ul>
        </div>

        <div>
          <h2 className="text-lg font-bold mb-2">7. 개인정보 처리방침 변경</h2>
          <p>이 개인정보 처리방침은 2026년 3월 23일부터 적용됩니다. 변경 시 웹사이트를 통해 공지합니다.</p>
        </div>
      </section>
    </main>
  );
}
