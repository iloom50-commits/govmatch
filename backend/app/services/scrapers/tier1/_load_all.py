"""모든 Tier 1 스크래퍼를 import해서 @register를 트리거.

신규 스크래퍼 추가 시 여기에 import 추가:
  from . import my_new_scraper  # noqa: F401
"""
# 창조경제혁신센터 통합 (18개 센터 공통 CMS)
from . import ccei_scraper  # noqa: F401

# 경남테크노파크
from . import gntp_scraper  # noqa: F401

# 테크노파크 6개 (부산/광주/전남/전북/충남/울산)
from . import tp_scrapers  # noqa: F401

# 공공기관 배치 1 (기업마당/KOCCA/SEMAS)
from . import gov_agency_scrapers  # noqa: F401

# 공공기관 배치 2 (NIPA/KEIT/KIBO/GBSA)
from . import more_agency_scrapers  # noqa: F401

# 공공기관 배치 3 (KETEP/aT/K-SURE/KIPA)
from . import agency_scrapers3  # noqa: F401

# 공공기관 배치 4 (KOSEA/KOVWA)
from . import agency_scrapers4  # noqa: F401

# 공공기관 배치 5 (KCA/KOFIC/KBIZ/KVIC)
from . import agency_scrapers5  # noqa: F401

# 공공기관 배치 6 (KHIDI/MSS/K-Startup)
from . import agency_scrapers6  # noqa: F401

# 공공기관 배치 7 (KICET/KIMS/ETRI/KITECH/KRISS/KIMM — 출연연)
from . import agency_scrapers7  # noqa: F401

# 지역 테크노파크 (경기/경북/충북/강원)
from . import regional_tp_scrapers  # noqa: F401
