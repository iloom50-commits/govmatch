"""모든 Tier 1 스크래퍼를 import해서 @register를 트리거.

신규 스크래퍼 추가 시 여기에 import 추가:
  from . import my_new_scraper  # noqa: F401
"""
# 창조경제혁신센터 통합 (18개 센터 공통 CMS)
from . import ccei_scraper  # noqa: F401

# 추후 추가될 스크래퍼들:
# from . import keit_scraper  # 한국산업기술평가관리원
# from . import kiat_scraper  # 한국산업기술진흥원
# from . import sba_scraper   # 서울산업진흥원
# from . import kto_scraper   # 한국관광공사
# from . import seoul_tp_scraper / gyeonggi_tp_scraper / busan_tp_scraper 등
