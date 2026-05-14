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

# 공공기관 배치 8 (고비즈코리아/신용보증기금)
from . import agency_scrapers8  # noqa: F401

# 광역시도청 11개 (인천/대전/울산/세종/강원/충북/충남/전북/전남/경남/부산)
from . import sido_scrapers  # noqa: F401

# 공공 API — 보조금24(정부24) + 복지로(중앙+지자체)
from . import gov24_scraper  # noqa: F401
from . import bokjiro_scraper  # noqa: F401

# 시군구 기업지원 전담기관 (11개)
from . import local_biz_scrapers  # noqa: F401

# 공공기관 배치 9 (KEITI/TIPA/KIDP/IITP/KOTRA)
from . import agency_scrapers9  # noqa: F401

# 광역시도청·R&D기관 배치 10 (광주/제주/KISTEP/부산/NRF)
from . import agency_scrapers10  # noqa: F401

# 공공기관 배치 11 (KITA/INNOPOLIS/KCCI/KICOX)
from . import agency_scrapers11  # noqa: F401

# 공공기관 배치 12 (HRD Korea/KWBIZ/KOSA)
from . import agency_scrapers12  # noqa: F401
