import SearchRedirect from "./SearchRedirect";

const POPULAR_KEYWORDS = [
  "소상공인 정책자금", "창업지원금", "청년 지원금", "R&D 지원사업",
  "수출바우처", "고용장려금", "주거지원", "출산지원금",
  "스마트공장", "디지털전환 지원", "여성기업 지원", "장학금",
];

export default function SearchPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-4 py-8">

        <SearchRedirect />

        <main>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">지원금 공고 검색</h1>
          <p className="text-slate-600 text-sm mb-8">
            17,000건 이상의 정부 지원금·보조금·정책자금 공고를 검색하세요.
            AI가 내 조건에 맞는 지원사업을 자동으로 찾아드립니다.
          </p>

          <section className="mb-10">
            <h2 className="text-base font-semibold text-slate-800 mb-4">인기 검색어</h2>
            <div className="flex flex-wrap gap-2">
              {POPULAR_KEYWORDS.map((kw) => (
                <a
                  key={kw}
                  href={`/?q=${encodeURIComponent(kw)}`}
                  className="px-4 py-2 bg-white border border-slate-200 rounded-full text-sm text-slate-700 hover:border-indigo-400 hover:text-indigo-600 hover:shadow-sm transition-all"
                >
                  {kw}
                </a>
              ))}
            </div>
          </section>

          <section className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
            <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm">
              <h2 className="text-base font-bold text-slate-800 mb-3">🏢 기업·소상공인 지원사업</h2>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="/?q=소상공인+정책자금" className="hover:text-indigo-600">소상공인 정책자금·융자·보증</a></li>
                <li><a href="/?q=중소기업+R%26D" className="hover:text-indigo-600">중소기업 R&amp;D·기술개발 과제</a></li>
                <li><a href="/?q=창업패키지" className="hover:text-indigo-600">예비창업·초기창업 패키지</a></li>
                <li><a href="/?q=수출바우처" className="hover:text-indigo-600">수출·해외마케팅 바우처</a></li>
                <li><a href="/?q=스마트공장" className="hover:text-indigo-600">스마트공장·디지털전환 지원</a></li>
                <li><a href="/?q=고용지원금" className="hover:text-indigo-600">고용·인력 지원사업</a></li>
              </ul>
            </div>
            <div className="bg-white rounded-2xl border border-slate-100 p-6 shadow-sm">
              <h2 className="text-base font-bold text-slate-800 mb-3">👤 개인·청년 지원사업</h2>
              <ul className="space-y-2 text-sm text-slate-600">
                <li><a href="/?q=청년지원금" className="hover:text-indigo-600">청년 취업·창업 지원금</a></li>
                <li><a href="/?q=주거지원+전세" className="hover:text-indigo-600">청년·신혼 주거지원·전세대출</a></li>
                <li><a href="/?q=출산지원" className="hover:text-indigo-600">출산·육아 지원금</a></li>
                <li><a href="/?q=복지바우처" className="hover:text-indigo-600">복지바우처·생활안정지원</a></li>
                <li><a href="/?q=국가장학금" className="hover:text-indigo-600">국가장학금·학자금 대출</a></li>
                <li><a href="/?q=에너지지원" className="hover:text-indigo-600">에너지·농어업인 지원금</a></li>
              </ul>
            </div>
          </section>

          <section className="bg-indigo-50 rounded-2xl p-6 text-center">
            <h2 className="text-lg font-bold text-indigo-900 mb-2">AI 맞춤 매칭으로 더 빠르게 찾으세요</h2>
            <p className="text-sm text-indigo-700 mb-4">
              업종·지역·매출 정보를 입력하면 AI가 내 조건에 딱 맞는 지원금만 골라드립니다.
            </p>
            <a href="/" className="inline-block px-6 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-full hover:bg-indigo-700 transition-colors">
              무료로 시작하기 →
            </a>
          </section>
        </main>

        <footer className="mt-12 pt-6 border-t border-slate-100 text-xs text-slate-400">
          <p>지원금AI(govmatch.kr)는 기업마당, K-Startup, 정부24 등 공식 출처의 공고를 실시간 수집·분석합니다.</p>
        </footer>
      </div>
    </div>
  );
}
