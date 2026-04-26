/**
 * 공용 마크다운 렌더러 — 테이블/헤딩/리스트/체크박스/URL 지원.
 * AiConsultModal, ProSecretary 등에서 공통 사용.
 * 반환값은 DOMPurify.sanitize()로 감싸서 dangerouslySetInnerHTML에 넣을 것.
 */
export function renderMarkdown(text: string): string {
  if (!text) return "";
  // 0) (None) 링크 패턴 제거
  text = text.replace(/\(\[.*?\]\(None\)\)/g, "").replace(/\[.*?\]\(None\)/g, "");

  // 1) 이스케이프
  let html = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 2) 인라인: bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-slate-900 font-semibold">$1</strong>');

  // 2b) URL → 바로가기 링크 버튼
  html = html.replace(
    /(https?:\/\/[^\s<)"]+)/g,
    '<a href="$1" target="_blank" rel="noopener" class="inline-flex items-center gap-1 px-2 py-0.5 bg-indigo-50 text-indigo-600 text-[11px] font-bold rounded-md border border-indigo-200 hover:bg-indigo-100 transition-all no-underline break-all">'
    + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
    + '바로가기</a>'
  );

  const lines = html.split("\n");
  const result: string[] = [];
  let listType: "ul" | "ol" | null = null;

  let tableRows: string[][] = [];
  let tableInBlock = false;

  const closeList = () => {
    if (listType) { result.push(listType === "ol" ? "</ol>" : "</ul>"); listType = null; }
  };
  const closeTable = () => {
    if (!tableInBlock) return;
    if (tableRows.length === 0) { tableInBlock = false; return; }
    const [headerRow, ...bodyRows] = tableRows;
    const headerHtml = headerRow.map((c, i) =>
      `<th class="px-3 py-2 text-left font-bold text-indigo-700 border-b-2 border-indigo-200${i === 0 ? " whitespace-nowrap" : ""}">${c}</th>`
    ).join("");
    const bodyHtml = bodyRows.map(row =>
      `<tr class="border-b border-slate-100 hover:bg-indigo-50/30">${row.map((c, i) =>
        `<td class="px-3 py-2 align-top text-slate-700${i === 0 ? " whitespace-nowrap font-medium" : ""}">${c}</td>`
      ).join("")}</tr>`
    ).join("");
    result.push(
      `<div class="my-3 overflow-x-auto rounded-lg border border-indigo-100 bg-white shadow-sm">`
      + `<table class="w-full text-[12px] leading-relaxed">`
      + `<thead class="bg-indigo-50/70"><tr>${headerHtml}</tr></thead>`
      + `<tbody>${bodyHtml}</tbody>`
      + `</table></div>`
    );
    tableRows = [];
    tableInBlock = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();

    // 표 감지
    if (trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.length > 2) {
      closeList();
      if (/^\|[\s\-:|]+\|$/.test(trimmed)) {
        tableInBlock = true;
        continue;
      }
      const cells = trimmed.slice(1, -1).split("|").map(c => c.trim());
      tableRows.push(cells);
      tableInBlock = true;
      continue;
    } else if (tableInBlock) {
      closeTable();
    }

    // 체크리스트
    const checkMatch = trimmed.match(/^[-*]\s+\[([ xX])\]\s+(.*)/);
    if (checkMatch) {
      closeList();
      const checked = checkMatch[1].toLowerCase() === "x";
      const checkIcon = checked
        ? '<span class="inline-flex items-center justify-center w-4 h-4 bg-indigo-600 text-white rounded text-[10px] mr-1.5 flex-shrink-0">✓</span>'
        : '<span class="inline-block w-4 h-4 border-2 border-slate-300 rounded mr-1.5 flex-shrink-0"></span>';
      result.push(`<div class="flex items-start py-1"><span class="mt-0.5">${checkIcon}</span><span class="text-slate-700 leading-relaxed">${checkMatch[2]}</span></div>`);
      continue;
    }

    const olMatch = trimmed.match(/^(\d+)[.\)]\s+(.*)/);
    const ulMatch = !olMatch && trimmed.match(/^[*\-•]\s+(.*)/);

    if (olMatch) {
      if (listType !== "ol") { closeList(); result.push('<ol class="ml-4 mt-2 mb-2 space-y-1.5 list-decimal list-outside">'); listType = "ol"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${olMatch[2]}</li>`);
    } else if (ulMatch) {
      if (listType !== "ul") { closeList(); result.push('<ul class="ml-4 mt-1 mb-1 space-y-1 list-disc list-outside">'); listType = "ul"; }
      result.push(`<li class="text-slate-700 leading-relaxed">${ulMatch[1]}</li>`);
    } else {
      closeList();
      if (/^##\s/.test(trimmed)) {
        const title = trimmed.replace(/^##\s+/, "");
        result.push(`<h2 class="mt-5 mb-2 pb-1.5 border-b-2 border-indigo-200 text-[15px] font-black text-indigo-700 tracking-tight">${title}</h2>`);
      } else if (/^###\s/.test(trimmed)) {
        const title = trimmed.replace(/^###\s+/, "");
        result.push(`<h3 class="mt-3 mb-1 text-[13px] font-bold text-slate-800">${title}</h3>`);
      } else if (/^#\s/.test(trimmed)) {
        const title = trimmed.replace(/^#\s+/, "");
        result.push(`<h1 class="mt-5 mb-2 text-[17px] font-black text-slate-900">${title}</h1>`);
      } else if (/^<strong.*<\/strong>[:\s]*$/.test(trimmed)) {
        result.push(`<div class="mt-3 mb-1 text-[13px] font-bold text-slate-800">${trimmed}</div>`);
      } else if (trimmed === "") {
        result.push('<div class="h-1.5"></div>');
      } else {
        result.push(`<p class="text-slate-700 leading-relaxed mb-1">${trimmed}</p>`);
      }
    }
  }
  closeList();
  closeTable();
  return result.join("");
}
