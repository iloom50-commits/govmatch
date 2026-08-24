# -*- coding: utf-8 -*-
"""확인 도구 — 짐작으로 답하지 않기 위한 것.

왜 만들었나 (2026-08-25)
  하루 동안 확인 없이 단정한 것이 일곱 건 나왔다. 전부 30초면 확인할 수 있는
  것이었는데, 그럴듯한 답이 먼저 나와서 확인을 건너뛰었다.
    · 「링크 검사 장치가 없다」   → url_health.py 가 있었다 (파일명만 봤다)
    · 「이 데이터는 안 쓰인다」   → 쿼리를 실행해 보지 않았다
    · 「POST 전용이라 안 된다」   → 파라미터 하나를 빼고 시험했다
    · 「임베딩이 꺼져 있다」      → 로컬 .env 만 봤다
    · 「통계가 달라진다」        → 실행하니 숫자가 그대로였다
  CLAUDE.md 에 규칙을 써 두었으나 그 뒤에도 어겼다. 규칙으로는 안 된다.
  ruff 훅이 작동한 이유는 기계가 강제하고 0.5초에 끝나기 때문이다.
  이 도구도 같은 성질을 노린다 — **확인 비용을 0으로 만들어 안 할 이유를 없앤다.**

쓰는 법 (backend 에서)
  python scripts/verify.py symbol   _safe_exec              이름이 어디 정의돼 있나
  python scripts/verify.py grep     "링크 헬스"              기능이 이미 있나
  python scripts/verify.py endpoint /api/ai/consultant/match 라우트가 실제로 있나
  python scripts/verify.py table    knowledge_base           누가 읽나 + 고아가 결과에 섞이나
  python scripts/verify.py url      "https://..."            GET/POST 조합을 실제로 던져본다
  python scripts/verify.py live     ols.semas.or.kr          그 수집처 링크가 열리나(프로덕션 기준)
  python scripts/verify.py env      USE_EMBEDDING_MATCHING   프로덕션 설정값

원칙
  · 모르면 「미확인」이라고 출력한다. 그럴듯한 추정을 내놓지 않는다.
  · DB 를 건드리지 않는다(읽기 전용). url 만 외부에 요청한다.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
ROOT = Path(__file__).resolve().parent.parent


def _out(label: str, value: str = "") -> None:
    print(f"  {label:<26} {value}")


def _db():
    """읽기 전용 연결. .env 의 DATABASE_URL 을 쓴다."""
    import psycopg2
    import psycopg2.extras
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=str(ROOT / ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("  DATABASE_URL 미설정 — 확인 불가")
        sys.exit(2)
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


# 결과 한 줄에서 파일경로·행번호·내용을 뗀다.
# Windows 는 경로가 "C:\..." 라 단순 split(":") 이 드라이브 문자에서 잘린다(실제로 겪었다).
_LINE_RE = re.compile(r"^(?P<path>(?:[A-Za-z]:)?[^:]*):(?P<line>\d+):(?P<code>.*)$")


def _split(line: str) -> tuple[str, str, str]:
    m = _LINE_RE.match(line)
    if not m:
        return ("", "", line)
    return (m.group("path"), m.group("line"), m.group("code"))


def _rg(pattern: str, *extra: str) -> list[str]:
    """app/ 아래 .py 를 직접 훑는다.

    처음에는 ripgrep/grep 을 subprocess 로 불렀는데 Windows 에서 FileNotFoundError 가
    났다(셸에서는 되지만 subprocess 는 PATH 를 다르게 본다). 조용히 빈 결과를 돌려줘
    「읽는 곳 0곳」이라는 거짓 결론이 나왔다 — 확인 도구가 확인을 틀리면 최악이다.
    그래서 외부 명령에 의존하지 않는다.
    """
    flags = re.IGNORECASE if "-i" in extra else 0
    rx = re.compile(pattern, flags)
    out: list[str] = []
    for p in APP.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if rx.search(text) is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                out.append(f"{p}:{i}:{line}")
    return out


# ── 명령들 ────────────────────────────────────────────────

def cmd_symbol(name: str) -> None:
    """이 이름이 정의돼 있나. 없으면 NameError 로 터진다."""
    print(f"■ '{name}' 정의 위치")
    defs = _rg(rf"^\s*(def|class)\s+{re.escape(name)}\b")
    imports = _rg(rf"(import\s+{re.escape(name)}\b|import\s+\w+\s+as\s+{re.escape(name)}\b|from\s+\S+\s+import\s+.*\b{re.escape(name)}\b)")
    if not defs and not imports:
        print("  ★ 정의도 import 도 없다 — 이 이름을 쓰면 NameError 가 난다")
    for l in defs[:8]:
        f, ln, code = _split(l)
        _out("정의", f"{Path(f).name}:{ln}  {code.strip()[:80]}")
    for l in imports[:6]:
        f, ln, code = _split(l)
        _out("import", f"{Path(f).name}:{ln}  {code.strip()[:80]}")
    uses = _rg(rf"\b{re.escape(name)}\s*\(")
    print(f"  사용처 {len(uses)}곳")
    print("\n  ※ 지역 import 인 경우 그 함수 안에서만 유효하다. 쓰는 자리의 스코프를 볼 것.")


def cmd_grep(keyword: str) -> None:
    """이 기능이 이미 있나 — 새로 만들기 전에."""
    print(f"■ '{keyword}' 관련 코드")
    hits = _rg(keyword, "-i")
    if not hits:
        print("  없음 — 다만 이름이 다를 수 있다. 동의어로 한 번 더 볼 것")
        return
    files: dict[str, int] = {}
    for l in hits:
        f, _, _c = _split(l)
        files[f] = files.get(f, 0) + 1
    for f, n in sorted(files.items(), key=lambda x: -x[1])[:12]:
        try:
            rel = str(Path(f).relative_to(APP.parent))
        except Exception:
            rel = f
        _out(Path(f).name, f"{n}곳  ({rel})")


def cmd_endpoint(path: str) -> None:
    """이 라우트가 실제로 있나 + 인증 방식."""
    # Git Bash 는 /api/... 인자를 C:/Program Files/Git/api/... 로 바꿔 넘긴다(MSYS 경로 변환).
    m = re.search(r"(/api/.*)$", path.replace("\\", "/"))
    if m:
        path = m.group(1)
    print(f"■ 라우트 '{path}'")
    base = path.split("?")[0]
    hits = _rg(rf'@app\.(get|post|put|delete)\("{re.escape(base)}"')
    if not hits:
        print("  ★ 그런 라우트 없음")
        near = _rg(rf'@app\.(get|post)\("[^"]*{re.escape(base.strip("/").split("/")[-1])}[^"]*"')
        for l in near[:8]:
            _out("비슷한 것", _split(l)[2].strip()[:96])
        return
    for l in hits:
        f, ln, code = _split(l)
        _out("정의", f"{Path(f).name}:{ln}  {code.strip()[:80]}")
        auth = ("_verify_admin" in l and "관리자 토큰(_verify_admin)") or \
               ("_get_current_user" in l and "로그인 필요") or "본문에서 확인 필요"
        _out("인증", str(auth))


def cmd_table(name: str) -> None:
    """이 테이블을 누가 읽나 + 고아가 실제 결과에 섞이나.

    「안 쓰이니 지워도 된다」를 짐작으로 말하지 않기 위한 것이다.
    """
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        print("  테이블 이름 형식이 아니다"); return
    print(f"■ 테이블 '{name}'")

    reads = [l for l in _rg(rf"(FROM|JOIN)\s+{re.escape(name)}\b")
             if not re.search(r"(INSERT INTO|DELETE FROM|UPDATE)\s+" + re.escape(name), l)]
    writes = _rg(rf"(INSERT INTO|UPDATE|DELETE FROM)\s+{re.escape(name)}\b")
    print(f"\n  읽는 곳 {len(reads)}곳 / 쓰는 곳 {len(writes)}곳")
    for l in reads[:10]:
        f, ln, code = _split(l)
        _out(f"{Path(f).name}:{ln}", code.strip()[:92])
    inner = sum(1 for l in reads if re.search(r"\bJOIN\s+announcements\b", l))
    if inner:
        print(f"    · announcements 와 JOIN 하는 곳 {inner}곳 — INNER JOIN 이면 고아는 결과에 못 나온다")

    conn = _db()
    try:
        cur = conn.cursor()
        cur.execute("""SELECT column_name FROM information_schema.columns
                       WHERE table_name=%s AND table_schema='public'""", (name,))
        cols = [r["column_name"] for r in cur.fetchall()]
        if not cols:
            print("\n  ★ 그런 테이블 없음"); return
        cur.execute(f"SELECT COUNT(*) AS n FROM {name}")
        total = cur.fetchone()["n"]
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size(%s)) AS s", (name,))
        size = cur.fetchone()["s"]
        print(f"\n  행 {total:,}건 · {size}")

        if "announcement_id" in cols:
            cur.execute(f"""SELECT COUNT(*) AS n FROM {name} t
                            WHERE NOT EXISTS (SELECT 1 FROM announcements a
                                              WHERE a.announcement_id = t.announcement_id)""")
            orphan = cur.fetchone()["n"]
            _out("공고 없는 고아", f"{orphan:,}건" + (f" ({orphan/total*100:.0f}%)" if total else ""))
            cur.execute("""SELECT tc.constraint_name, rc.delete_rule, c.convalidated
                           FROM information_schema.table_constraints tc
                           LEFT JOIN information_schema.referential_constraints rc
                                ON rc.constraint_name = tc.constraint_name
                           LEFT JOIN pg_constraint c ON c.conname = tc.constraint_name
                           WHERE tc.table_name=%s AND tc.constraint_type='FOREIGN KEY'""", (name,))
            fks = cur.fetchall()
            _out("FK", ", ".join(f"ON DELETE {r['delete_rule']}"
                                 + ("" if r["convalidated"] else " (NOT VALID)") for r in fks) or "없음")
            if orphan:
                print("\n  ※ 고아가 실제 결과에 섞이는지는 위 「읽는 곳」의 쿼리를 그대로 실행해 볼 것.")
                print("     WHERE 에 announcement 조건이 없으면 섞인다. 짐작하지 말 것.")

        cur.execute("""SELECT seq_scan, idx_scan, seq_tup_read, idx_tup_fetch
                       FROM pg_stat_user_tables WHERE relname=%s""", (name,))
        st = cur.fetchone()
        if st:
            read = (st["seq_tup_read"] or 0) + (st["idx_tup_fetch"] or 0)
            _out("누적 읽기", f"순차 {st['seq_scan'] or 0:,}회 · 인덱스 {st['idx_scan'] or 0:,}회 · {read:,}행")
    finally:
        conn.close()


def cmd_url(url: str) -> None:
    """실제로 열어 본다. 「이 주소는 안 된다」를 폼 속성만 보고 말하지 않기 위한 것."""
    import requests
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    print(f"■ {url}")

    def vis(t: str) -> str:
        t = re.sub(r"<(script|style|noscript)\b.*?</\1>", " ", t, flags=re.S | re.I)
        t = re.sub(r"<[^>]+>", " ", t)
        import html as _h
        return re.sub(r"\s+", " ", _h.unescape(t)).strip()

    base, _, qs = url.partition("?")
    params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p) if qs else {}
    tries = [("GET  그대로", "get", params)]
    if params:
        tries.append(("POST 같은 값", "post", params))
    for label, method, p in tries:
        try:
            r = (requests.get(base, headers={"User-Agent": UA}, params=p, timeout=20)
                 if method == "get" else
                 requests.post(base, headers={"User-Agent": UA}, data=p, timeout=20))
            t = vis(r.text or "")
            _out(label, f"HTTP {r.status_code} · 가시텍스트 {len(t):,}자")
            print(f"    앞부분: {t[:120]}")
        except Exception as e:
            _out(label, f"실패 {type(e).__name__}: {str(e)[:60]}")
    print("\n  ※ 상태코드는 판정 근거가 못 된다 — 죽은 페이지도 200 을 준다.")
    print("     찾는 내용(제목 등)이 가시텍스트에 있는지로 판단할 것.")


def cmd_live(host: str) -> None:
    """프로덕션 서버 기준으로 그 수집처 링크가 열리나 (내 회선이 아니라)."""
    import requests
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=str(ROOT / ".env"))
    pw = os.environ.get("ADMIN_PASSWORD")
    if not pw:
        print("  ADMIN_PASSWORD 미설정 — 확인 불가"); return
    api = os.environ.get("VERIFY_API_BASE", "https://govmatch-production.up.railway.app")
    print(f"■ {host} (프로덕션 서버 기준)")
    try:
        r = requests.post(f"{api}/api/admin/link-liveness/probe",
                          json={"password": pw, "host": host}, timeout=120)
        d = r.json()
    except Exception as e:
        print(f"  요청 실패: {e}"); return
    if d.get("status") != "SUCCESS":
        print(f"  {d}"); return
    probes = " ".join(f"{p['ratio']:.0%}/{p['status']}" for p in d["html"])
    _out("마감 전 공고", f"{d['total_live_announcements']:,}건")
    _out("표본 4건", probes)
    _out("판정", d["html_verdict"])
    print("\n  ※ error/blocked 는 「우리 서버가 막힌 것」이지 링크가 죽은 게 아니다.")


def cmd_env(name: str) -> None:
    """프로덕션 설정값. 로컬 .env 로 프로덕션을 말하지 않기 위한 것."""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=str(ROOT / ".env"))
    local = os.environ.get(name)
    print(f"■ 환경변수 '{name}'")
    _out("로컬 .env", ("설정됨" if local else "미설정") + "  ← 프로덕션과 다를 수 있다")
    known = {
        "USE_EMBEDDING_MATCHING": "POST /api/admin/embeddings/debug-match → env_flag",
        "EMBEDDING_MATCHING_MODE": "POST /api/admin/embeddings/debug-match → env_flag",
    }
    if name in known:
        _out("프로덕션 확인", known[name])
    else:
        print("  프로덕션 값을 확인할 엔드포인트가 없다 — ★미확인★ 으로 다룰 것")
        print("  (Railway 대시보드에서 대표에게 확인 요청)")


COMMANDS = {
    "symbol": cmd_symbol, "grep": cmd_grep, "endpoint": cmd_endpoint,
    "table": cmd_table, "url": cmd_url, "live": cmd_live, "env": cmd_env,
}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](" ".join(sys.argv[2:]))
