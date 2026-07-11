/**
 * 상담 보고서 HTML 생성 — 프론트엔드 템플릿 (AI 호출 없음).
 * 공고 정보 + 기업 정보 + 판정 + 대화 전문을 구조화된 보고서 형식으로 렌더링.
 */

interface ReportInput {
  announcement: {
    title?: string;
    department?: string;
    category?: string;
    region?: string;
    deadline_date?: string;
    support_amount?: string;
  };
  profile: {
    company_name?: string;
    industry_code?: string;
    address_city?: string;
    establishment_date?: string;
    revenue_bracket?: string;
    employee_count_bracket?: string;
    certifications?: string;
  };
  messages: Array<{ role: "user" | "assistant"; text: string; done?: boolean }>;
  conclusion?: string;
  created_at?: string;
}

const CONC_DATA: Record<string, { label: string; color: string; bg: string; emoji: string }> = {
  eligible: { label: "신청 가능", color: "#059669", bg: "#d1fae5", emoji: "✅" },
  conditional: { label: "조건부 가능", color: "#d97706", bg: "#fef3c7", emoji: "⚠️" },
  ineligible: { label: "대상 아님", color: "#64748b", bg: "#f1f5f9", emoji: "❌" },
};

// AI 메시지에서 제출 서류 목록을 키워드 기반으로 추출
function extractDocuments(messages: Array<{ role: string; text: string }>): string[] {
  const aiText = messages.filter(m => m.role === "assistant").map(m => m.text).join("\n");
  const docs = new Set<string>();
  const patterns = [
    /(?:제출|필요|준비)\s*서류[:：\s]*([^\n]+)/g,
    /[-•·*]\s*([^-•·*\n]{3,40})(?:\s*증빙|\s*확인서|\s*서|등록증|계약서|사업계획서)/g,
  ];
  // 표준 서류 키워드 매칭
  const standardDocs = [
    "사업자등록증", "중소기업확인서", "재무제표", "사업계획서",
    "법인등기부등본", "주민등록등본", "통장사본", "4대보험 납부확인서",
    "세금계산서", "거래내역서", "특허증", "기술인증서",
    "매출증빙", "고용증빙", "자기자본확인서", "재직증명서",
  ];
  for (const doc of standardDocs) {
    if (aiText.includes(doc)) docs.add(doc);
  }
  return Array.from(docs).slice(0, 10);
}

// AI 메시지에서 핵심 조언/확인사항 추출
function extractAdvice(messages: Array<{ role: string; text: string }>): string[] {
  const tips: string[] = [];
  for (const m of messages) {
    if (m.role !== "assistant") continue;
    // 불릿·번호 항목 파싱
    const lines = m.text.split("\n");
    for (const line of lines) {
      const cleaned = line.trim().replace(/^[-•·*]\s*|^\d+[.)]\s*/, "");
      if (cleaned.length < 10 || cleaned.length > 120) continue;
      if (/확인|필요|주의|권장|강화|준비|점검|체크/.test(cleaned)) {
        tips.push(cleaned.replace(/\*+/g, "").trim());
      }
    }
  }
  // 중복 제거
  return Array.from(new Set(tips)).slice(0, 5);
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(text: string): string {
  let out = escapeHtml(text);
  out = out.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/^###\s+(.+)$/gm, "<h4>$1</h4>");
  out = out.replace(/^##\s+(.+)$/gm, "<h3>$1</h3>");
  out = out.replace(/^[-•]\s+(.+)$/gm, "<li>$1</li>");
  out = out.replace(/(<li>[\s\S]*?<\/li>(?:[\s\S]*?<li>[\s\S]*?<\/li>)*)/, "<ul>$1</ul>");
  out = out.replace(/\n\n+/g, "<br/><br/>");
  out = out.replace(/\n/g, "<br/>");
  return out;
}

function calcCompanyAge(estDate?: string): string {
  if (!estDate) return "-";
  try {
    const d = new Date(estDate);
    const y = new Date().getFullYear() - d.getFullYear();
    return `${estDate.slice(0, 10)} (${y}년차)`;
  } catch {
    return estDate;
  }
}

export function generateConsultReportHTML(input: ReportInput): string {
  const { announcement: a, profile: p, messages, conclusion, created_at } = input;
  const concData = conclusion && CONC_DATA[conclusion] ? CONC_DATA[conclusion] : null;
  const now = created_at ? new Date(created_at).toLocaleString("ko-KR") : new Date().toLocaleString("ko-KR");
  const docs = extractDocuments(messages);
  const advice = extractAdvice(messages);

  const verdictSection = concData ? `
    <div class="verdict" style="background:${concData.bg};border:2px solid ${concData.color};">
      <div class="verdict-emoji">${concData.emoji}</div>
      <div>
        <div class="verdict-label" style="color:${concData.color};">자격 판정</div>
        <div class="verdict-value" style="color:${concData.color};">${concData.label}</div>
      </div>
    </div>
  ` : "";

  const docsSection = docs.length > 0 ? `
    <div class="section">
      <h2>📎 제출 서류 체크리스트</h2>
      <div class="doc-list">
        ${docs.map(d => `<div class="doc-item">☐ ${escapeHtml(d)}</div>`).join("")}
      </div>
    </div>
  ` : "";

  const adviceSection = advice.length > 0 ? `
    <div class="section">
      <h2>💡 핵심 확인사항 & 조언</h2>
      <ol class="advice-list">
        ${advice.map(t => `<li>${escapeHtml(t)}</li>`).join("")}
      </ol>
    </div>
  ` : "";

  const conversationSection = `
    <div class="section">
      <h2>💬 상담 대화 전문</h2>
      ${messages.filter(m => !m.done).map(m => `
        <div class="msg ${m.role}">
          <div class="msg-role">${m.role === "user" ? "🙋 질문" : "🤖 AI 상담사"}</div>
          <div class="msg-text">${m.role === "user" ? escapeHtml(m.text) : renderMarkdown(m.text)}</div>
        </div>
      `).join("")}
    </div>
  `;

  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>상담 보고서 — ${escapeHtml(a.title || "")}</title>
<style>
  @page { margin: 18mm 15mm; size: A4; }
  * { box-sizing: border-box; }
  body {
    font-family: 'Pretendard', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
    color: #1e293b;
    line-height: 1.6;
    font-size: 12px;
    margin: 0;
    padding: 0;
  }
  .header {
    border-bottom: 3px solid #4f46e5;
    padding-bottom: 12px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .header-title {
    font-size: 22px;
    font-weight: 900;
    color: #4f46e5;
    margin: 0;
  }
  .header-sub {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
  }
  .header-logo {
    font-size: 10px;
    color: #94a3b8;
    text-align: right;
  }
  .section {
    margin-bottom: 22px;
    page-break-inside: avoid;
  }
  .section h2 {
    font-size: 14px;
    color: #1e293b;
    background: linear-gradient(to right, #eef2ff 0%, transparent 100%);
    padding: 8px 12px;
    border-left: 4px solid #4f46e5;
    margin: 0 0 10px 0;
    border-radius: 0 6px 6px 0;
  }
  .info-grid {
    display: grid;
    grid-template-columns: 120px 1fr 120px 1fr;
    gap: 8px 12px;
    background: #f8fafc;
    padding: 14px 16px;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
  }
  .info-label {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
  }
  .info-value {
    font-size: 12px;
    color: #1e293b;
    font-weight: 500;
  }
  .amount { color: #059669; font-weight: 700; }
  .deadline { color: #dc2626; font-weight: 700; }
  .verdict {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 18px 22px;
    border-radius: 12px;
    margin-bottom: 22px;
  }
  .verdict-emoji { font-size: 36px; }
  .verdict-label { font-size: 11px; font-weight: 700; margin-bottom: 2px; }
  .verdict-value { font-size: 20px; font-weight: 900; }
  .doc-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px 14px;
    padding: 12px 16px;
    background: #f0fdf4;
    border-radius: 8px;
    border: 1px solid #bbf7d0;
  }
  .doc-item { font-size: 12px; color: #166534; }
  .advice-list {
    padding-left: 20px;
    margin: 0;
    background: #fffbeb;
    padding: 12px 20px 12px 36px;
    border-radius: 8px;
    border: 1px solid #fde68a;
  }
  .advice-list li { font-size: 12px; color: #78350f; margin-bottom: 6px; line-height: 1.6; }
  .msg {
    margin-bottom: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    border-left: 3px solid transparent;
    page-break-inside: avoid;
  }
  .msg.user { background: #eef2ff; border-left-color: #6366f1; }
  .msg.assistant { background: #f8fafc; border-left-color: #10b981; }
  .msg-role { font-size: 10px; font-weight: 700; color: #64748b; margin-bottom: 4px; }
  .msg-text { font-size: 12px; color: #1e293b; line-height: 1.65; }
  .msg-text strong { color: #4f46e5; }
  .msg-text ul { padding-left: 18px; margin: 4px 0; }
  .msg-text li { margin-bottom: 3px; }
  .msg-text h3, .msg-text h4 { margin: 8px 0 4px 0; color: #334155; font-size: 12px; }
  .footer {
    margin-top: 32px;
    padding-top: 14px;
    border-top: 2px solid #e2e8f0;
    text-align: center;
    font-size: 10px;
    color: #94a3b8;
    line-height: 1.6;
  }
  .footer strong { color: #4f46e5; }
  .no-print { display: none; }
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header-title">AI 상담 보고서</div>
    <div class="header-sub">정부 지원금 자격 상담 결과</div>
  </div>
  <div class="header-logo">
    <strong style="color:#4f46e5;">지원금AI</strong><br/>
    govmatch.kr
  </div>
</div>

<div class="section">
  <h2>📋 공고 기본 정보</h2>
  <div class="info-grid">
    <div class="info-label">공고명</div>
    <div class="info-value" style="grid-column: span 3;"><strong>${escapeHtml(a.title || "-")}</strong></div>

    <div class="info-label">주관 기관</div>
    <div class="info-value">${escapeHtml(a.department || "-")}</div>
    <div class="info-label">카테고리</div>
    <div class="info-value">${escapeHtml(a.category || "-")}</div>

    <div class="info-label">지원 금액</div>
    <div class="info-value amount">${escapeHtml(a.support_amount || "공고 참조")}</div>
    <div class="info-label">마감일</div>
    <div class="info-value deadline">${a.deadline_date && a.deadline_date !== "None" ? escapeHtml(a.deadline_date.slice(0, 10)) : "상시"}</div>

    <div class="info-label">지역</div>
    <div class="info-value" style="grid-column: span 3;">${escapeHtml(a.region || "전국")}</div>
  </div>
</div>

<div class="section">
  <h2>🏢 신청 기업 정보</h2>
  <div class="info-grid">
    <div class="info-label">기업명</div>
    <div class="info-value">${escapeHtml(p.company_name || "-")}</div>
    <div class="info-label">업종 코드</div>
    <div class="info-value">${escapeHtml(p.industry_code || "-")}</div>

    <div class="info-label">설립일·업력</div>
    <div class="info-value">${calcCompanyAge(p.establishment_date)}</div>
    <div class="info-label">소재지</div>
    <div class="info-value">${escapeHtml(p.address_city || "-")}</div>

    <div class="info-label">매출 규모</div>
    <div class="info-value">${escapeHtml(p.revenue_bracket || "-")}</div>
    <div class="info-label">직원 수</div>
    <div class="info-value">${escapeHtml(p.employee_count_bracket || "-")}</div>

    ${p.certifications ? `
    <div class="info-label">보유 인증</div>
    <div class="info-value" style="grid-column: span 3;">${escapeHtml(p.certifications)}</div>
    ` : ""}
  </div>
</div>

${verdictSection}
${adviceSection}
${docsSection}
${conversationSection}

<div class="footer">
  <div>본 보고서는 <strong>지원금AI</strong>가 AI 기반으로 생성한 참고 자료입니다.</div>
  <div>최종 선정 결과는 주관 기관의 심사에 따르며, 본 자료는 법적 효력이 없습니다.</div>
  <div style="margin-top:6px;">발행일시: ${now} · govmatch.kr</div>
</div>

</body>
</html>`;
}
