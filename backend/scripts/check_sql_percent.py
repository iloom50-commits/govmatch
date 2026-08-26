# -*- coding: utf-8 -*-
"""SQL 문자열 안의 홀로 쓰인 퍼센트 기호를 잡는다.

왜 필요한가 (2026-08-26)
  psycopg2 는 쿼리를 `query % params` 로 처리한다. 그래서 SQL 문자열에 퍼센트 기호가
  있으면 **주석이든 문자열이든** 포맷 지정자로 해석되고, 파라미터가 모자라면
  `IndexError: tuple index out of range` 가 난다.

  실제 사고: 주석에 「54건(14%)이」 라고 쓴 한 글자 때문에 일일 파이프라인 ④단계가
  이틀간(08-25·08-26) 통째로 죽었다. 공고 분석·죽은 링크 검사가 그동안 돌지 않았다.
  구문 오류가 아니라 실행 시점 오류라 ruff 도 py_compile 도 잡지 못한다.

규칙
  cur.execute(...) 에 파라미터를 넘기는 호출에서, 쿼리 문자열의 퍼센트 기호가
  `%s` · `%(name)s` · `%%` 중 어느 것도 아니면 위반.

실행:  cd backend && python scripts/check_sql_percent.py
종료코드 1 = 위반 있음
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

# 허용되는 형태: %s  %(name)s  %%  %d 등 표준 포맷 지정자
_OK = re.compile(r"%(?:%|s|d|f|\([A-Za-z_][A-Za-z0-9_]*\)s)")


def offending(sql: str) -> list[str]:
    """허용 형태를 지운 뒤에도 남는 퍼센트 기호가 있으면 그 주변을 돌려준다."""
    stripped = _OK.sub("", sql)
    out = []
    for m in re.finditer("%", stripped):
        i = m.start()
        out.append(stripped[max(0, i - 34):i + 14].replace("\n", " ").strip())
    return out


def literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):          # f-string — 상수 조각만 본다
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def main() -> int:
    bad = 0
    for path in sorted(APP.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "execute"):
                continue
            # 파라미터를 넘기는 호출만 위험하다(psycopg2 가 % 처리를 한다)
            if len(node.args) < 2:
                continue
            sql = literal(node.args[0])
            if not sql:
                continue
            for around in offending(sql):
                bad += 1
                rel = str(path).split("backend" + chr(92), 1)[-1]
                print(f"✗ {rel}:{node.lineno}")
                print(f"   …{around}…")
                print("   → SQL 안의 퍼센트 기호는 포맷 지정자로 해석된다. "
                      "%% 로 이스케이프하거나 문구에서 빼라.\n")
    if bad:
        print(f"SQL 퍼센트 위반 {bad}건.")
        print("psycopg2 는 query % params 로 처리한다 — 주석이라도 IndexError 가 난다.")
        return 1
    print("SQL 퍼센트 검사 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
