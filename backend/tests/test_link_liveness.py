# -*- coding: utf-8 -*-
"""링크 생사 판정 테스트.

여기 담긴 값은 전부 2026-08-24 에 실제 사이트를 열어 잰 것이다. 추측이 아니다.
판정 기준을 누가 손보면 이 테스트가 먼저 깨져야 한다.

실행:  cd backend && python -m unittest tests.test_link_liveness -v
"""
import unittest

from app.services.patrol.link_liveness import (
    visible_text,
    title_match_ratio,
    judge_link,
    judge_source,
    ALIVE_THRESHOLD,
)


class TestVisibleText(unittest.TestCase):
    def test_스크립트와_스타일은_본문에서_빠진다(self):
        html = """<html><head><style>.a{color:red}</style>
                  <script>var x = "공고 제목처럼 보이는 문자열";</script></head>
                  <body><h1>모두의 창업 프로젝트</h1></body></html>"""
        t = visible_text(html)
        self.assertIn("모두의 창업 프로젝트", t)
        self.assertNotIn("공고 제목처럼 보이는 문자열", t)
        self.assertNotIn("color:red", t)

    def test_HTML_엔티티는_풀린다(self):
        self.assertIn("기술개발(R&D)", visible_text("<p>기술개발(R&amp;D)</p>"))


class TestTitleMatch(unittest.TestCase):
    """K-Startup pbancSn=178856 실측 (2026-08-24)

    죽은 주소   bizpbanc-read.do?pbancSn=          → 25%  (포털 메뉴만 반환)
    살아있는 주소 bizpbanc-ongoing.do?schM=view&…   → 100%
    없는 번호    …&pbancSn=999999999               → 12%  (가시텍스트 72자)
    """

    TITLE = "모두의 창업 프로젝트 2기 AI 솔루션 공급기업 모집공고"

    def test_제목이_그대로_있으면_100퍼센트(self):
        page = "K-Startup 사업공고 상세 " + self.TITLE + " 신청기간 2026-08-25"
        self.assertEqual(title_match_ratio(page, self.TITLE), 1.0)

    def test_메뉴만_있는_껍데기는_낮게_나온다(self):
        # 죽은 주소가 실제로 돌려준 본문의 성격 — 포털 공통 헤더·메뉴뿐
        page = ("본문 바로가기 중소벤처기업부 창업진흥원 2026 창업지원사업통합공고 "
                "사업신청관리 자주하는 질문 로그인 회원가입 사업소개 사업화 기술개발")
        self.assertLess(title_match_ratio(page, self.TITLE), ALIVE_THRESHOLD)

    def test_빈_페이지는_0에_가깝다(self):
        self.assertLess(title_match_ratio("K-Startup 창업지원포털", self.TITLE), ALIVE_THRESHOLD)

    def test_제목이_잘려_저장돼도_통과한다(self):
        # announcements.title 은 400자에서 잘린다. 페이지에 더 긴 제목이 있어도 맞아야 한다.
        page = "공고 " + self.TITLE + " 추가 안내 및 붙임 서류"
        self.assertGreaterEqual(title_match_ratio(page, self.TITLE[:20]), ALIVE_THRESHOLD)

    def test_한글자_어절은_세지_않는다(self):
        # "및", "등" 같은 한 글자는 아무 페이지에나 있어 판정을 흐린다
        self.assertEqual(title_match_ratio("가나다", "및 등 를"), 0.0)

    def test_빈_제목은_0(self):
        self.assertEqual(title_match_ratio("아무 내용", ""), 0.0)


class TestJudgeLink(unittest.TestCase):
    def test_임계값_이상이면_alive(self):
        self.assertEqual(judge_link(1.0), "alive")
        self.assertEqual(judge_link(ALIVE_THRESHOLD), "alive")

    def test_임계값_미만이면_dead(self):
        self.assertEqual(judge_link(0.25), "dead")   # 죽은 K-Startup 주소 실측값
        self.assertEqual(judge_link(0.0), "dead")


class TestJudgeSource(unittest.TestCase):
    """수집처 단위 판정.

    개별 공고가 내려가는 것은 정상이다. 표본이 전멸해야 코드 문제로 본다.
    2026-08-24 상위 20개 수집처 실측: 정상 16곳은 83~100%, 죽은 3곳은 전부 0%.
    """

    def test_전부_살아있으면_ok(self):
        self.assertEqual(judge_source([1.0, 1.0, 0.83, 1.0]), "ok")

    def test_전멸해야_suspect(self):
        self.assertEqual(judge_source([0.0, 0.0, 0.0, 0.0]), "suspect")

    def test_일부만_죽으면_ok_이다(self):
        # gov.kr 실측 — 4건 중 1건만 0%. 그 공고가 내려간 것이지 수집처 문제가 아니다.
        self.assertEqual(judge_source([0.0, 1.0, 1.0, 1.0]), "ok")

    def test_표본이_모자라면_판정하지_않는다(self):
        # 1~2건으로 수집처 전체를 단정하지 않는다
        self.assertEqual(judge_source([0.0]), "unknown")
        self.assertEqual(judge_source([0.0, 0.0]), "unknown")

    def test_표본이_없으면_판정하지_않는다(self):
        self.assertEqual(judge_source([]), "unknown")


class TestBlockedIsNotDead(unittest.TestCase):
    """「우리 서버에서 안 열린다」와 「링크가 죽었다」는 다르다.

    2026-08-24 프로덕션 실측 사고 —
      www.jeju.go.kr 106건이 죽음으로 보고됐으나, 같은 주소를 다른 곳에서 재니
      제목 일치 100% 였다. Railway 서버가 차단당한 것이지 링크는 멀쩡했다.
      사용자 브라우저에서는 열린다.

    죽은 링크는 HTTP 200 에 껍데기를 준다. 차단은 연결 실패·403·429 로 나타난다.
    이 둘을 섞으면 멀쩡한 수집처를 죽었다고 보고한다.
    """

    def test_차단_표본은_판정에서_빠진다(self):
        from app.services.patrol.link_liveness import judge_source_probes, Probe
        probes = [Probe(0.0, "blocked"), Probe(0.0, "blocked"),
                  Probe(0.0, "error"), Probe(0.0, "blocked")]
        self.assertEqual(judge_source_probes(probes), "unknown")

    def test_열린_표본이_전멸해야_suspect(self):
        from app.services.patrol.link_liveness import judge_source_probes, Probe
        probes = [Probe(0.0, "ok"), Probe(0.0, "ok"), Probe(0.0, "ok"), Probe(0.1, "ok")]
        self.assertEqual(judge_source_probes(probes), "suspect")

    def test_차단이_섞여도_열린것이_살아있으면_ok(self):
        # jeju 실측 — 1건 연결실패, 3건 100%
        from app.services.patrol.link_liveness import judge_source_probes, Probe
        probes = [Probe(0.0, "error"), Probe(1.0, "ok"), Probe(1.0, "ok"), Probe(1.0, "ok")]
        self.assertEqual(judge_source_probes(probes), "ok")

    def test_열린_표본이_모자라면_판정하지_않는다(self):
        from app.services.patrol.link_liveness import judge_source_probes, Probe
        probes = [Probe(0.0, "ok"), Probe(0.0, "ok"), Probe(0.0, "blocked"), Probe(0.0, "error")]
        self.assertEqual(judge_source_probes(probes), "unknown")

    def test_상태코드로_분류한다(self):
        from app.services.patrol.link_liveness import classify_status
        self.assertEqual(classify_status(200), "ok")
        self.assertEqual(classify_status(404), "ok")     # 404 는 진짜 없는 것 — 판정 대상
        self.assertEqual(classify_status(403), "blocked")
        self.assertEqual(classify_status(429), "blocked")
        self.assertEqual(classify_status(503), "blocked")
        self.assertEqual(classify_status(500), "blocked")
        self.assertEqual(classify_status(None), "error")  # 연결 자체가 안 됨


class TestOverDetectionGuard(unittest.TestCase):
    """오탐 방지 — 이 테스트가 깨지면 멀쩡한 공고를 망가뜨릴 수 있다.

    2026-08-24 실측: HTML 만 보고 판정했다면 아래 두 수집처의 4,752건을
    「죽음」으로 잘못 몰 뻔했다. 브라우저로 열면 제목이 100% 나온다.
      · www.bokjiro.go.kr   4,386건  HTML 0%  →  브라우저 100%
      · biz.asancef.or.kr     366건  HTML 0%  →  브라우저 100%
    그래서 HTML 1차 결과만으로는 절대 수리하지 않는다.
    """

    def test_1차_전멸은_확정이_아니라_후보다(self):
        from app.services.patrol.link_liveness import needs_browser_recheck
        self.assertTrue(needs_browser_recheck(judge_source([0.0, 0.0, 0.0, 0.0])))
        self.assertFalse(needs_browser_recheck(judge_source([1.0, 1.0, 1.0, 1.0])))
        self.assertFalse(needs_browser_recheck(judge_source([0.0])))  # unknown


if __name__ == "__main__":
    unittest.main()
