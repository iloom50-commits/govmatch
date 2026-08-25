// pointer-events 함정 검사 — 버튼이 보이는데 눌리지 않는 사고를 막는다.
//
// 왜 만들었나 (2026-08-25)
//   AiConsultModal 의 「상담을 저장하시겠습니까?」 창에서 버튼이 눌리지 않았다.
//   모달 루트가 `lg:pointer-events-none` 이고(사이드 패널 뒤 화면을 조작하게 하려는 의도)
//   그 안의 다이얼로그가 `pointer-events-auto` 로 되돌리지 않아, 데스크톱에서만
//   클릭이 통과해 버렸다. 모바일에서는 멀쩡해서 더 늦게 발견됐다.
//   같은 결함이 AiChatBot 에도 2개 있었다 — 눈으로는 못 찾는다.
//
// 검사 규칙
//   파일 안에 pointer-events-none 이 있으면,
//   그 파일의 `fixed inset-0 z-[...]` 오버레이는 모두 pointer-events-auto 를 가져야 한다.
//
// 실행:  node scripts/check_pointer_events.mjs
// 종료코드 1 = 위반 있음
import { readdirSync, readFileSync, statSync } from "fs";
import { join } from "path";

const ROOT = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

const OVERLAY = /className="[^"]*\bfixed\b[^"]*\binset-0\b[^"]*\bz-\[[^\]]+\][^"]*"/g;
let bad = 0;

for (const file of walk(ROOT)) {
  const src = readFileSync(file, "utf-8");
  // 이 파일이 pointer-events-none 을 쓰는가 (배경 장식용 absolute 는 제외)
  const hasNone = /\bpointer-events-none\b/.test(src) &&
                  /(fixed[^"]*\bpointer-events-none|lg:pointer-events-none)/.test(src);
  if (!hasNone) continue;

  const lines = src.split(/\r?\n/);
  lines.forEach((line, i) => {
    OVERLAY.lastIndex = 0;
    if (!OVERLAY.test(line)) return;
    if (/\bpointer-events-auto\b/.test(line)) return;
    bad += 1;
    const rel = file.slice(file.indexOf("src"));
    console.error(`✗ ${rel}:${i + 1}`);
    console.error(`   ${line.trim().slice(0, 100)}`);
    console.error("   → pointer-events-auto 가 없다. 데스크톱에서 버튼이 눌리지 않는다.\n");
  });
}

if (bad) {
  console.error(`pointer-events 위반 ${bad}건.`);
  console.error("이 파일은 pointer-events-none 을 쓰므로, 그 안의 오버레이는");
  console.error("className 에 pointer-events-auto 를 넣어 클릭을 되살려야 한다.");
  process.exit(1);
}
console.log("pointer-events 검사 통과");
