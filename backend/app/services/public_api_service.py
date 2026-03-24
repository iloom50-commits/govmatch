import os
import requests
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

class GovernmentAPIService:
    """공공데이터포털(data.go.kr) 공식 API를 통한 지원사업 수집 서비스"""
    
    BASE_URL = "https://apis.data.go.kr"

    @staticmethod
    def _normalize_date(raw) -> str | None:
        """다양한 날짜 형식을 YYYY-MM-DD로 정규화"""
        if not raw:
            return None
        s = str(raw).strip().replace("/", "-").replace(".", "-")
        # "~" 포함 시 기간 형식 → 무시
        if "~" in s:
            return None
        # 공백 포함 날짜 정규화 ("2025- 3- 3" → "2025-03-03")
        import re
        m = re.match(r"(\d{4})-\s*(\d{1,2})-\s*(\d{1,2})", s)
        if m:
            day = int(m.group(3))
            month = int(m.group(2))
            if day == 0 or month == 0:
                return None
            return f"{m.group(1)}-{month:02d}-{day:02d}"
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        return None

    @classmethod
    def is_configured(cls):
        # Dynamically check environment to avoid stale class variables
        from dotenv import load_dotenv
        load_dotenv(override=True)
        key = os.getenv("PUBLIC_DATA_PORTAL_KEY")
        return key and key != "YOUR_PUBLIC_DATA_PORTAL_API_KEY"

    def _get_api_key(self):
        from dotenv import load_dotenv
        load_dotenv(override=True)
        return os.getenv("PUBLIC_DATA_PORTAL_KEY")

    async def fetch_mss_programs(self, page=1, per_page=10):
        """중소벤처기업부(MSS) 사업공고 목록 조회"""
        if not self.is_configured():
            return self._get_mock_mss_data()

        endpoint = f"{self.BASE_URL}/1421000/mssBizService_v2/getMssBizList_v2"
        params = {
            "serviceKey": self._get_api_key(),
            "pageNo": page,
            "numOfRows": per_page,
            "_type": "json"
        }

        try:
            response = requests.get(endpoint, params=params, timeout=15)
            response.encoding = 'utf-8' 
            
            if response.status_code != 200:
                print(f"MSS API Error: Status {response.status_code}")
                # print(f"Response: {response.text}")
                return []
                
            try:
                data = response.json()
            except Exception as json_err:
                print(f"MSS JSON Error: {json_err}")
                print(f"First 100 chars of response: {response.text[:100]}")
                return []
                
            body = data.get("response", {}).get("body", {})
            items = body.get("items", [])
            
            # Data.go.kr often returns items directly or wrapped in 'item'
            if isinstance(items, dict) and "item" in items:
                items = items["item"]
            
            if not isinstance(items, list):
                items = [items] if items else []
                
            return self._map_mss_fields(items)
        except Exception as e:
            print(f"MSS API Error: {e}")
            return []

    async def fetch_kised_institutions(self, page=1, per_page=10):
        """창업진흥원(KISED) 주관기관 정보 조회"""
        if not self.is_configured():
            return []

        endpoint = f"{self.BASE_URL}/B552735/kisedPmsService/getInstitutionInformation"
        params = {
            "serviceKey": self._get_api_key(),
            "pageNo": page,
            "numOfRows": per_page,
            "_type": "json"
        }

        try:
            response = requests.get(endpoint, params=params, timeout=10)
            data = response.json()
            return data.get("response", {}).get("body", {}).get("items", [])
        except Exception as e:
            print(f"KISED API Error: {e}")
            return []

    def _map_mss_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pblancNm") or item.get("title") or item.get("사업명")
            url = item.get("detailUrl") or item.get("link") or item.get("상세페이지URL")
            content = item.get("pblancCtnt") or item.get("contents") or item.get("사업개요")
            deadline = item.get("rcritEndDe") or item.get("pblancEndDe") or item.get("rcritEndDt") or item.get("endDt")
            
            if title and url:
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": content or "",
                    "department": "중소벤처기업부",
                    "category": "Small Business/Startup",
                    "origin_source": "mss-api",
                    "deadline_date": self._normalize_date(deadline),
                })
        return mapped

    def _get_mock_mss_data(self):
        """MSS 시뮬레이션 데이터"""
        return [
            {
                "title": "[시뮬레이션] 2026 중소기업 기술혁신 개발사업",
                "url": "https://www.mss.go.kr/site/smba/ex/bbs/View.do?cbIdx=86&bcIdx=1000000",
                "description": "중소기업의 기술경쟁력 제고를 위한 R&D 지원사업입니다.",
                "department": "중소벤처기업부",
                "category": "R&D",
                "origin_source": "mss-api"
            }
        ]

    async def fetch_kised_announcements(self, page=1, per_page=10):
        """창업진흥원(KISED) 창업지원사업 공고 조회 (K-Startup)"""
        if not self.is_configured():
            return []

        endpoint = f"{self.BASE_URL}/B552735/kisedKstartupService01/getAnnouncementInformation01"
        params = {
            "serviceKey": self._get_api_key(),
            "pageNo": page,
            "numOfRows": per_page,
            "_type": "json"
        }

        try:
            print(f"  [API] Calling KISED API: {endpoint}")
            response = requests.get(endpoint, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"    [ERR] KISED API Error: Status {response.status_code}")
                return []

            # Handle XML response (often happens with data.go.kr legacy APIs)
            if "<?xml" in response.text or "<results>" in response.text:
                return self._parse_kised_xml(response.text)

            try:
                data = response.json()
                body = data.get("response", {}).get("body", {})
                items = body.get("items", [])
                if isinstance(items, dict) and "item" in items:
                    items = items["item"]
                if not isinstance(items, list):
                    items = [items] if items else []
                return self._map_kised_fields(items)
            except Exception as e:
                print(f"    [ERR] KISED Parse Error: {e}")
                return []

        except Exception as e:
            print(f"  [ERR] KISED Exception: {e}")
            return []

    def _parse_kised_xml(self, xml_text):
        """Parse KISED's unique 'grid-style' XML response"""
        import xml.etree.ElementTree as ET
        mapped = []
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                cols = {col.get("name"): col.text for col in item.findall("col")}
                
                # Mapping grid columns to internal structure (KISED format)
                title = cols.get("biz_pbanc_nm") or cols.get("pbancNm")
                # Prefer application URL if available, otherwise guidance URL
                url = cols.get("biz_aply_url") or cols.get("biz_gdnc_url") or cols.get("detlUrl")
                
                if title and url:
                    if not url.startswith("http"):
                        url = f"https://{url}"

                    # K-Startup 도메인만 있는 경우 공고 ID로 상세 URL 구성
                    pbanc_sn = cols.get("pbancSn") or cols.get("pbanc_sn")
                    if url.rstrip("/") in ("https://www.k-startup.go.kr", "http://www.k-startup.go.kr") and pbanc_sn:
                        url = f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}"

                    deadline = cols.get("rcrit_end_de") or cols.get("rcritEndDe") or cols.get("pbanc_end_de") or cols.get("pbancEndDe")
                    mapped.append({
                        "title": title,
                        "url": url,
                        "description": cols.get("pbancCn") or cols.get("intg_pbanc_biz_nm") or "",
                        "department": cols.get("pbancDeptNm") or "창업진흥원",
                        "category": "Entrepreneurship",
                        "origin_source": "kised-api",
                        "deadline_date": self._normalize_date(deadline),
                    })
            print(f"    [OK] KISED XML Parsed {len(mapped)} items")
            return mapped
        except Exception as e:
            print(f"    [ERR] KISED XML Parse Error: {e}")
            return []

    def _map_kised_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pbancNm") or item.get("title")
            url = item.get("detlUrl") or item.get("link")
            deadline = item.get("rcritEndDe") or item.get("pbancEndDe") or item.get("rcritEndDt")
            
            if title and url:
                if not url.startswith("http"):
                    url = f"https://{url}"

                pbanc_sn = item.get("pbancSn") or item.get("pbanc_sn")
                if url.rstrip("/") in ("https://www.k-startup.go.kr", "http://www.k-startup.go.kr") and pbanc_sn:
                    url = f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do?schM=view&pbancSn={pbanc_sn}"

                mapped.append({
                    "title": title,
                    "url": url,
                    "description": item.get("pbancCn") or "",
                    "department": item.get("pbancDeptNm") or "창업진흥원",
                    "category": "Entrepreneurship",
                    "origin_source": "kised-api",
                    "deadline_date": self._normalize_date(deadline),
                })
        return mapped

    # Legacy support if needed
    async def fetch_kstartup_programs(self, page=1, per_page=10):
        # K-Startup content can be more comprehensive via KISED announcements
        return await self.fetch_kised_announcements(page, per_page)

    async def fetch_msit_programs(self, page=1, per_page=10):
        """과학기술정보통신부 R&D 사업공고 목록 조회 (data.go.kr 15074634)"""
        if not self.is_configured():
            return self._get_mock_msit_data()

        api_key = self._get_api_key()
        url = (
            f"http://apis.data.go.kr/1721000/msitannouncementinfo/businessAnnouncMentList"
            f"?serviceKey={api_key}&pageNo={page}&numOfRows={per_page}&returnType=json"
        )

        try:
            print(f"  [API] Calling MSIT R&D API (page {page})...")
            response = requests.get(url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    [ERR] MSIT R&D API Error: Status {response.status_code}")
                return [] if page > 1 else self._get_mock_msit_data()

            if "<?xml" in response.text[:100]:
                return self._parse_msit_xml(response.text)

            try:
                data = response.json()
            except Exception:
                print(f"    [ERR] MSIT JSON parse failed, trying XML...")
                return self._parse_msit_xml(response.text)

            resp = data.get("response", [])
            body = {}
            for part in resp if isinstance(resp, list) else [resp]:
                if "body" in part:
                    body = part["body"]
                    break

            raw_items = body.get("items", [])

            # data.go.kr wraps each item: [{"item": {...}}, {"item": {...}}]
            items = []
            if isinstance(raw_items, list):
                for entry in raw_items:
                    if isinstance(entry, dict) and "item" in entry:
                        items.append(entry["item"])
                    elif isinstance(entry, dict):
                        items.append(entry)
            elif isinstance(raw_items, dict) and "item" in raw_items:
                item_val = raw_items["item"]
                items = item_val if isinstance(item_val, list) else [item_val]

            total = body.get("totalCount", 0)
            print(f"    [OK] MSIT R&D API: {len(items)} items (total: {total})")
            return self._map_msit_fields(items)

        except Exception as e:
            print(f"  [ERR] MSIT R&D API Exception: {e}")
            return self._get_mock_msit_data()

    async def fetch_bizinfo_programs(self, page=1, per_page=10):
        """기업마당(Bizinfo) 지원사업 공고 조회 (V4 - data.go.kr)"""
        # 기존 data.go.kr V4 API (실패 가능성 높음)
        if not self.is_configured():
            return self._get_mock_bizinfo_data()
        
        # 만약 직접 포털 API 키가 설정되어 있다면 그것을 우선 사용
        portal_key = os.getenv("BIZINFO_PORTAL_KEY")
        if portal_key:
            return await self.fetch_bizinfo_portal_direct(page, per_page)

        # 원래의 data.go.kr V4 로직 (생략 - 기존 코드 유지 가능하나 여기서는 직접 포털 우선)
        return await self.fetch_bizinfo_portal_direct(page, per_page)

    async def fetch_bizinfo_portal_direct(self, page=1, per_page=10):
        """기업마당(Bizinfo) 포털 직접 연동 API (bizinfoApi.do)"""
        key = os.getenv("BIZINFO_PORTAL_KEY")
        if not key:
            print("  [WARN] BIZINFO_PORTAL_KEY not set. Falling back to mock/scraper.")
            return []

        url = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
        params = {
            "crtfcKey": key,
            "dataType": "json"
        }

        try:
            print(f"  [API] Calling Bizinfo Portal Direct API...")
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"    [ERR] Bizinfo Portal API Error: Status {response.status_code}")
                return []

            data = response.json()
            # Bizinfo portal returns { "jsonArray": [...] }
            items = data.get("jsonArray", [])
            
            return self._map_bizinfo_portal_fields(items)
        except Exception as e:
            print(f"  [ERR] Bizinfo Portal Exception: {e}")
            return []

    @staticmethod
    def _parse_period_end_date(period_str) -> str | None:
        """'2026-03-09 ~ 2026-03-27' 형식에서 종료일 추출"""
        if not period_str or "~" not in str(period_str):
            return None
        parts = str(period_str).split("~")
        if len(parts) == 2:
            end_part = parts[1].strip()
            # YYYY-MM-DD 형식 검증
            if len(end_part) >= 10 and end_part[4] == "-" and end_part[7] == "-":
                return end_part[:10]
        return None

    def _map_bizinfo_portal_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pblancNm")
            rel_url = item.get("pblancUrl")
            # 1) 개별 마감일 필드 시도
            deadline = item.get("rcritEndDe") or item.get("pblancEndDe") or item.get("reqstEndDe")
            # 2) reqstBeginEndDe ("2026-03-09 ~ 2026-03-27") 에서 종료일 추출
            if not deadline:
                deadline = self._parse_period_end_date(item.get("reqstBeginEndDe"))
            
            if title and rel_url:
                # Prevent URL doubling: if rel_url already has full domain, use as-is
                if rel_url.startswith("http"):
                    full_url = rel_url
                elif rel_url.startswith("/"):
                    full_url = f"https://www.bizinfo.go.kr{rel_url}"
                else:
                    full_url = f"https://www.bizinfo.go.kr/{rel_url}"
                mapped.append({
                    "title": title,
                    "url": full_url,
                    "description": item.get("bsnsSumryCn") or "",
                    "department": item.get("jrsdInsttNm") or "기업마당",
                    "category": item.get("pldirSportRealmLclasCodeNm") or "General Business Support",
                    "origin_source": "bizinfo-portal-api",
                    "deadline_date": self._normalize_date(deadline),
                })
        return mapped

    def _map_bizinfo_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pbaNm")
            url = item.get("pbaUrl")
            deadline = item.get("pbaEndDe") or item.get("rcritEndDe")
            
            if title and url:
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": item.get("pbaContents") or "",
                    "department": item.get("pbaInst") or "기업마당",
                    "category": "General Business Support",
                    "origin_source": "bizinfo-api",
                    "region": item.get("pbaArea") or "All",
                    "deadline_date": self._normalize_date(deadline),
                })
        return mapped

    def _get_mock_bizinfo_data(self):
        return [
            {
                "title": "[시뮬레이션] 2026 기업마당 판로개척 지원사업",
                "url": "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=PBLN_000000000000001",
                "description": "전국 소상공인 및 중소기업의 판로 개척을 지원합니다.",
                "department": "중소벤처기업부",
                "category": "Marketing",
                "origin_source": "bizinfo-api",
                "region": "전국"
            }
        ]

    def _map_msit_fields(self, items):
        """과기정통부 R&D 사업공고 API 응답 매핑"""
        mapped = []
        for item in items:
            title = item.get("subject") or item.get("title")
            url = item.get("viewUrl") or item.get("detailUrl") or item.get("link")
            dept = item.get("deptName") or "과학기술정보통신부"
            deadline = item.get("rcritEndDe") or item.get("endDate") or item.get("closingDate")

            if title and url:
                if not url.startswith("http"):
                    url = f"https://www.msit.go.kr{url}"
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": "",
                    "department": dept,
                    "category": "R&D",
                    "origin_source": "msit-rnd-api",
                    "deadline_date": self._normalize_date(deadline),
                })
        return mapped

    def _parse_msit_xml(self, xml_text):
        """과기정통부 API가 XML로 응답할 경우 파싱"""
        import xml.etree.ElementTree as ET
        mapped = []
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item"):
                title = None
                url = None
                dept = "과학기술정보통신부"
                deadline = None

                for child in item:
                    if child.tag == "subject":
                        title = child.text
                    elif child.tag == "viewUrl":
                        url = child.text
                    elif child.tag == "deptName" and child.text:
                        dept = child.text
                    elif child.tag in ("rcritEndDe", "endDate", "closingDate") and child.text:
                        deadline = child.text

                if title and url:
                    if not url.startswith("http"):
                        url = f"https://www.msit.go.kr{url}"
                    mapped.append({
                        "title": title,
                        "url": url,
                        "description": "",
                        "department": dept,
                        "category": "R&D",
                        "origin_source": "msit-rnd-api",
                        "deadline_date": self._normalize_date(deadline),
                    })
            print(f"    [OK] MSIT XML Parsed {len(mapped)} items")
            return mapped
        except Exception as e:
            print(f"    [ERR] MSIT XML Parse Error: {e}")
            return []

    def _get_mock_msit_data(self):
        return [
            {
                "title": "[시뮬레이션] 2026 ICT R&D 혁신 바우처 지원사업",
                "url": "https://www.msit.go.kr/bbs/view.do?sCode=user&mPid=121&mId=311&bbsSeqNo=100&nttSeqNo=1",
                "description": "중소·중견기업의 기술력 확보 및 비즈니스 창출을 지원합니다.",
                "department": "과학기술정보통신부",
                "category": "R&D/Digital",
                "origin_source": "msit-api"
            }
        ]

    # ─── 중소벤처24 공고정보 API (smes.go.kr) ───

    async def fetch_smes24_programs(self, start_date=None, end_date=None):
        """중소벤처24 사업공고 정보 조회 (기정원 발급 토큰 필요)"""
        token = os.getenv("SMES24_API_TOKEN")
        if not token:
            print("  [WARN] SMES24_API_TOKEN not set. Skipping 중소벤처24.")
            return []

        import urllib.parse
        from datetime import datetime, timedelta

        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        url = (
            f"https://www.smes.go.kr/fnct/apiReqst/extPblancInfo"
            f"?token={token}&strDt={start_date}&endDt={end_date}&html=no"
        )

        try:
            print(f"  [API] Calling 중소벤처24 API (period: {start_date}~{end_date})...")
            response = requests.get(url, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    [ERR] SMES24 API Error: Status {response.status_code}")
                return []

            data = response.json()
            result_cd = data.get("resultCd", "99")
            if result_cd != "0":
                print(f"    [ERR] SMES24 API Result: {data.get('resultMsg', 'Unknown error')} (code: {result_cd})")
                return []

            items = data.get("data", [])
            print(f"    [OK] SMES24 API: {len(items)} items fetched")
            return self._map_smes24_fields(items)

        except Exception as e:
            print(f"  [ERR] SMES24 Exception: {e}")
            return []

    def _map_smes24_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pblancNm")
            url = item.get("pblancDtlUrl") or item.get("reqstLinkInfo")

            if not title or not url:
                continue

            eligibility = {}
            if item.get("cmpScale"):
                eligibility["company_size"] = item["cmpScale"]
            if item.get("salsAmt"):
                eligibility["revenue_range"] = item["salsAmt"]
            if item.get("ablbiz"):
                eligibility["years_in_business"] = item["ablbiz"]
            if item.get("emplyCnt"):
                eligibility["employee_count"] = item["emplyCnt"]
            if item.get("needCrtfn"):
                eligibility["required_certifications"] = item["needCrtfn"]
            if item.get("induty"):
                eligibility["industry"] = item["induty"]
            if item.get("minSalsAmt") is not None:
                eligibility["min_revenue"] = item["minSalsAmt"]
            if item.get("maxSalsAmt") is not None:
                eligibility["max_revenue"] = item["maxSalsAmt"]
            if item.get("fntnYn") == "Y":
                eligibility["startup_eligible"] = True
            if item.get("refntnYn") == "Y":
                eligibility["restart_eligible"] = True
            if item.get("fmleRpsntYn") == "Y":
                eligibility["female_ceo_eligible"] = True

            region = item.get("areaNm", "전국")
            category = item.get("sportType") or item.get("bizType") or "General"
            dept = item.get("sportInsttNm") or item.get("cntcInsttNm") or "중소벤처기업부"

            mapped.append({
                "title": title,
                "url": url,
                "description": item.get("policyCnts") or item.get("sportCnts") or "",
                "department": dept,
                "category": category,
                "origin_source": "smes24-api",
                "region": region,
                "deadline_date": self._normalize_date(item.get("pblancEndDt")),
                "eligibility_logic": eligibility
            })
        return mapped

    # ─── 한국식품산업클러스터진흥원 API (foodpolis) ───

    async def fetch_foodpolis_programs(self, page=1, per_page=20):
        """한국식품산업클러스터진흥원 일반사업공고 목록 조회"""
        api_key = os.getenv("FOODPOLIS_API_KEY")
        if not api_key:
            print("  [WARN] FOODPOLIS_API_KEY not set. Skipping 식품산업클러스터.")
            return []

        url = "https://www.foodpolis.kr/fbip/co/io/api/apiData/list.do"
        params = {
            "opapiSn": 5,
            "serviceKey": api_key,
            "pageNo": page,
            "numOfRows": per_page,
            "returnType": "json"
        }

        try:
            print(f"  [API] Calling Foodpolis API...")
            response = requests.get(url, params=params, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    [ERR] Foodpolis API Error: Status {response.status_code}")
                return []

            data = response.json()
            items = data.get("data", data.get("items", data.get("body", {}).get("items", [])))
            if isinstance(items, dict) and "item" in items:
                items = items["item"]
            if not isinstance(items, list):
                items = [items] if items else []

            print(f"    [OK] Foodpolis API: {len(items)} items")
            return self._map_foodpolis_fields(items)

        except Exception as e:
            print(f"  [ERR] Foodpolis Exception: {e}")
            return []

    def _map_foodpolis_fields(self, items):
        mapped = []
        for item in items:
            title = item.get("pblancNm") or item.get("title") or item.get("bbsSj")
            url = item.get("detailUrl") or item.get("link") or item.get("bbsUrl")

            if not title:
                continue
            if not url:
                url = "https://www.foodpolis.kr"

            deadline = item.get("rcritEndDe") or item.get("pblancEndDe") or item.get("endDt")
            mapped.append({
                "title": title,
                "url": url,
                "description": item.get("bbsCn") or item.get("sportCnts") or "",
                "department": "한국식품산업클러스터진흥원",
                "category": "Food Industry",
                "origin_source": "foodpolis-api",
                "region": item.get("areaNm") or "전국",
                "deadline_date": self._normalize_date(deadline),
            })
        return mapped

    # ─── 보조금24 / 정부24 공공서비스 API (api.odcloud.kr) ───

    # 기업/소상공인 관련 서비스 필터 키워드
    _GOV24_BIZ_KEYWORDS = [
        "기업", "소상공인", "창업", "중소", "벤처", "스타트업", "자영업",
        "사업자", "법인", "R&D", "수출", "고용", "일자리", "채용",
        "기술개발", "혁신", "디지털", "제조", "상공", "산업",
    ]

    async def fetch_gov24_services(self, page=1, per_page=100):
        """보조금24 (정부24) 공공서비스 목록 조회 - 기업/소상공인 + 부처별 확장"""
        api_key = os.getenv("GOV24_API_KEY")
        if not api_key:
            print("  [WARN] GOV24_API_KEY not set. Skipping 보조금24.")
            return []

        all_items = []
        url = "https://api.odcloud.kr/api/gov24/v3/serviceList"

        # 1단계: 기업 관련 키워드 검색 (기존)
        search_terms = ["기업", "소상공인", "창업", "중소기업"]
        for term in search_terms:
            for pg in range(1, 4):
                try:
                    params = {
                        "page": pg, "perPage": per_page,
                        "returnType": "JSON", "serviceKey": api_key,
                        "cond[서비스명::LIKE]": term,
                    }
                    resp = requests.get(url, params=params, timeout=15)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    items = data.get("data", [])
                    if not items:
                        break
                    all_items.extend(items)
                    if pg * per_page >= data.get("totalCount", 0):
                        break
                except Exception as e:
                    print(f"    [ERR] 보조금24 keyword({term}): {e}")
                    break

        # 2단계: 부처명으로 추가 검색 (신규 — 구석구석 확장)
        ministry_terms = [
            "고용노동부", "산림청", "해양수산부",
            "국토교통부", "환경부", "여성가족부",
            "농림축산식품부", "문화체육관광부",
        ]
        for dept in ministry_terms:
            for pg in range(1, 3):  # 부처당 최대 2페이지
                try:
                    params = {
                        "page": pg, "perPage": per_page,
                        "returnType": "JSON", "serviceKey": api_key,
                        "cond[소관기관명::LIKE]": dept,
                    }
                    resp = requests.get(url, params=params, timeout=15)
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    items = data.get("data", [])
                    if not items:
                        break
                    all_items.extend(items)
                    if pg * per_page >= data.get("totalCount", 0):
                        break
                except Exception as e:
                    print(f"    [ERR] 보조금24 dept({dept}): {e}")
                    break

        # 중복 제거 (서비스ID 기준)
        seen_ids = set()
        unique = []
        for item in all_items:
            sid = item.get("서비스ID", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                unique.append(item)

        print(f"  [API] 보조금24: {len(unique)} unique services fetched (keyword+ministry)")
        return self._map_gov24_fields(unique)

    def _map_gov24_fields(self, items):
        """보조금24 API 응답 → 내부 형식 매핑"""
        mapped = []
        for item in items:
            title = item.get("서비스명", "")
            detail_url = item.get("상세조회URL", "")
            if not title:
                continue
            if not detail_url:
                sid = item.get("서비스ID", "")
                detail_url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{sid}" if sid else ""
            if not detail_url:
                continue

            # 지원대상에서 기업/사업자 관련 키워드 확인하여 eligibility 구성
            target = item.get("지원대상", "")
            eligibility = {}
            if target:
                eligibility["target_description"] = target[:500]

            support_content = item.get("지원내용", "")
            summary = item.get("서비스목적요약", "") or support_content[:300]

            deadline_raw = item.get("신청기한", "")
            deadline = self._normalize_date(deadline_raw) if deadline_raw else None

            dept = item.get("소관기관명", "")
            category = item.get("서비스분야", "") or "Government Service"
            org_type = item.get("소관기관유형", "")
            region = "전국"
            # 소관기관유형이 지자체면 지역 정보 추출 시도
            if org_type in ("지방자치단체", "시도", "시군구"):
                region = dept[:2] if dept else "전국"  # 서울시→서울, 부산시→부산 등

            mapped.append({
                "title": title,
                "url": detail_url,
                "description": summary[:1000],
                "department": dept,
                "category": category,
                "origin_source": "gov24-api",
                "region": region,
                "deadline_date": deadline,
                "eligibility_logic": eligibility,
            })
        return mapped

    # ─── 지자체 복지서비스 API (data.go.kr / 한국사회보장정보원) ───

    async def fetch_local_gov_welfare(self, page=1, per_page=100):
        """지자체복지서비스 목록 조회 (한국사회보장정보원 API, XML 응답)"""
        api_key = os.getenv("LOCAL_WELFARE_API_KEY") or self._get_api_key()
        if not api_key:
            print("  [WARN] LOCAL_WELFARE_API_KEY not set. Skipping 지자체복지서비스.")
            return []

        import xml.etree.ElementTree as ET

        all_items = []
        for pg in range(1, 47):  # 최대 46페이지 (4,600건 — 총 4,561건 커버)
            try:
                url = (
                    f"https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfarelist"
                    f"?serviceKey={api_key}&pageNo={pg}&numOfRows={per_page}"
                )
                print(f"  [API] 지자체복지서비스 page {pg}...")
                resp = requests.get(url, timeout=15)

                if resp.status_code != 200:
                    print(f"    [ERR] 지자체복지 API Status {resp.status_code}")
                    break

                resp.encoding = "utf-8"
                root = ET.fromstring(resp.text)

                # 에러 체크 (성공: "0" 또는 "00")
                result_code = root.findtext(".//resultCode")
                if result_code and result_code not in ("0", "00"):
                    msg = root.findtext(".//resultMsg", "")
                    print(f"    [ERR] 지자체복지 API: {result_code} - {msg}")
                    break

                items = root.findall(".//servList")
                if not items:
                    # 다른 구조일 수 있음
                    items = root.findall(".//item")
                if not items:
                    break

                for item in items:
                    entry = {}
                    for child in item:
                        entry[child.tag] = child.text or ""
                    all_items.append(entry)

                total = root.findtext(".//totalCount") or root.findtext(".//totalCnt")
                if total and pg * per_page >= int(total):
                    break

            except Exception as e:
                print(f"    [ERR] 지자체복지 Exception: {e}")
                break

        print(f"  [API] 지자체복지서비스: {len(all_items)} items fetched")
        return self._map_local_welfare_fields(all_items)

    def _map_local_welfare_fields(self, items):
        """지자체복지서비스 XML 응답 매핑 → target_type='individual'"""
        mapped = []
        for item in items:
            title = item.get("servNm") or item.get("wlfareInfoNm") or ""
            if not title:
                continue

            # 상세 URL 구성
            serv_id = item.get("servId") or item.get("wlfareInfoId") or ""
            detail_url = item.get("servDtlLink") or item.get("detailUrl") or ""
            if not detail_url and serv_id:
                detail_url = f"https://www.bokjiro.go.kr/ssis-teu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={serv_id}"
            if not detail_url:
                continue

            target = item.get("trgterIndvdlNm") or item.get("sprtTrgtCn") or ""
            support = item.get("servDgst") or item.get("alwServCn") or ""
            dept = item.get("bizChrDeptNm") or item.get("inqplCtadrList") or item.get("jurMnofNm") or item.get("jurOrgNm") or ""
            field = item.get("servDgst") or ""

            # 지역 추출 (ctpvNm 우선, 없으면 관할기관명에서)
            region = item.get("ctpvNm") or ""
            if not region:
                org = item.get("jurOrgNm") or item.get("jurMnofNm") or ""
                region = org[:2] if org and len(org) >= 2 else "전국"

            category = self._map_individual_category(item.get("intrsThemaNmArray") or field)

            eligibility = {}
            if target:
                eligibility["target_description"] = target[:500]
            life_stage = item.get("lifeNmArray") or ""
            if life_stage:
                eligibility["life_stage"] = life_stage
            theme = item.get("intrsThemaNmArray") or ""
            if theme:
                eligibility["theme"] = theme
            sel = item.get("slctCritCn") or ""
            if sel:
                eligibility["selection_criteria"] = sel[:500]

            mapped.append({
                "title": title,
                "url": detail_url,
                "description": (support or target)[:1000],
                "department": dept or org,
                "category": category,
                "origin_source": "local-welfare-api",
                "region": region,
                "deadline_date": None,
                "eligibility_logic": eligibility,
                "target_type": "individual",
            })
        return mapped

    async def enrich_local_welfare_details(self, batch_size=100):
        """지자체복지서비스 상세 API 호출하여 마감일·지원내용 보강 (배치)

        보강 완료 표시: summary_text 앞에 '[상세보강]' 마커 추가.
        다음 배치에서 미보강 건만 선택하여 중복 호출 방지.
        """
        import xml.etree.ElementTree as ET
        import re
        import time
        api_key = os.getenv("LOCAL_WELFARE_API_KEY") or self._get_api_key()
        if not api_key:
            return {"updated": 0, "skipped": 0, "errors": 0}

        import psycopg2, psycopg2.extras
        from app.config import DATABASE_URL
        db_url = DATABASE_URL.replace(":6543/", ":5432/")
        conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = True
        cur = conn.cursor()

        # 아직 보강 안 된 건만 대상 (summary_text에 '[상세보강]' 마커 없는 건)
        cur.execute("""
            SELECT announcement_id, origin_url FROM announcements
            WHERE origin_source = 'local-welfare-api'
              AND (summary_text IS NULL OR summary_text NOT LIKE '%%[상세보강]%%')
            ORDER BY announcement_id
            LIMIT %s
        """, (batch_size,))
        rows = cur.fetchall()
        if not rows:
            print("  [Enrich] 모든 지자체복지 항목이 이미 보강 완료됨")
            conn.close()
            return {"updated": 0, "skipped": 0, "errors": 0}
        print(f"  [Enrich] {len(rows)} local-welfare items to enrich")

        updated, skipped, errors = 0, 0, 0
        for i, row in enumerate(rows):
            try:
                url = row["origin_url"]
                m = re.search(r"wlfareInfoId=([A-Z0-9]+)", url)
                if not m:
                    # servId 없으면 마커만 추가하여 다음에 건너뜀
                    cur.execute(
                        "UPDATE announcements SET summary_text = '[상세보강]' || COALESCE(summary_text,'') WHERE announcement_id = %s",
                        (row["announcement_id"],),
                    )
                    skipped += 1
                    continue
                serv_id = m.group(1)

                resp = requests.get(
                    f"https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"
                    f"?serviceKey={api_key}&servId={serv_id}",
                    timeout=10,
                )
                resp.encoding = "utf-8"

                # API 한도 초과 시 즉시 중단
                if resp.status_code == 429:
                    print(f"  [Enrich] API quota exceeded after {i} calls. Stopping batch.")
                    break
                if resp.status_code != 200:
                    errors += 1
                    continue

                root = ET.fromstring(resp.text)

                enfc_end = root.findtext("enfcEndYmd", "")
                deadline = None
                if enfc_end and enfc_end != "99991231" and len(enfc_end) == 8:
                    deadline = self._normalize_date(enfc_end)

                # 지원내용 보강
                support = root.findtext("alwServCn", "") or ""
                target_desc = root.findtext("sprtTrgtCn", "") or ""
                method = root.findtext("aplyMtdCn", "") or ""
                sel_crit = root.findtext("slctCritCn", "") or ""

                # 풍부한 summary 구성
                parts = []
                if support:
                    parts.append(support)
                if target_desc:
                    parts.append(f"[대상] {target_desc}")
                if method:
                    parts.append(f"[신청] {method}")
                enriched_summary = "\n".join(parts)[:1000] if parts else ""
                # 마커 추가
                enriched_summary = "[상세보강]" + (enriched_summary or row.get("summary_text", "") or "")

                update_parts = ["summary_text = %s"]
                params = [enriched_summary[:1000]]

                if deadline:
                    update_parts.append("deadline_date = %s")
                    params.append(deadline)

                # eligibility 보강 (선정기준)
                if sel_crit and len(sel_crit) > 20:
                    import json as _json
                    cur.execute("SELECT eligibility_logic FROM announcements WHERE announcement_id = %s", (row["announcement_id"],))
                    elig_row = cur.fetchone()
                    elig = {}
                    if elig_row and elig_row.get("eligibility_logic"):
                        try:
                            elig = _json.loads(elig_row["eligibility_logic"]) if isinstance(elig_row["eligibility_logic"], str) else elig_row["eligibility_logic"]
                        except Exception:
                            pass
                    if not isinstance(elig, dict):
                        elig = {}
                    elig["selection_criteria"] = sel_crit[:500]
                    update_parts.append("eligibility_logic = %s")
                    params.append(_json.dumps(elig, ensure_ascii=False))

                params.append(row["announcement_id"])
                cur.execute(f"UPDATE announcements SET {', '.join(update_parts)} WHERE announcement_id = %s", params)
                updated += 1

                if (i + 1) % 50 == 0:
                    print(f"    ... {i+1}/{len(rows)} processed ({updated} updated)")
                    time.sleep(0.3)

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    [ERR] Enrich {row.get('announcement_id')}: {e}")
                # XML 파싱 에러 등은 마커만 추가하여 다음에 건너뜀
                try:
                    cur.execute(
                        "UPDATE announcements SET summary_text = '[상세보강]' || COALESCE(summary_text,'') WHERE announcement_id = %s",
                        (row["announcement_id"],),
                    )
                except Exception:
                    pass

        conn.close()
        result = {"updated": updated, "skipped": skipped, "errors": errors}
        print(f"  [Enrich] Done: {result}")
        return result

    # ─── 보조금24 / 정부24 개인 복지서비스 API ───

    # 개인 복지 관련 서비스 분야 키워드
    _GOV24_INDIVIDUAL_SEARCH_TERMS = [
        "복지", "생활안정", "의료", "교육", "장학", "주거", "주택",
        "고용", "취업", "출산", "육아", "보육", "금융", "세제",
        "청년", "노인", "장애인", "한부모", "기초생활",
    ]

    async def fetch_gov24_individual_services(self, per_page=100):
        """정부24 공공서비스 전체 수집 (10,918건 페이지네이션)

        기존: 19개 키워드 검색 → 2,380건만 수집
        변경: 전체 페이지네이션으로 10,918건 전부 수집, 사용자구분=개인/가구 필터
        """
        api_key = os.getenv("GOV24_API_KEY")
        if not api_key:
            print("  [WARN] GOV24_API_KEY not set. Skipping 개인 복지서비스.")
            return []

        all_items = []
        url = "https://api.odcloud.kr/api/gov24/v3/serviceList"

        # 전체 건수 확인
        try:
            resp = requests.get(url, params={
                "page": 1, "perPage": 1, "returnType": "JSON", "serviceKey": api_key,
            }, timeout=15)
            total_count = resp.json().get("totalCount", 0)
            total_pages = (total_count + per_page - 1) // per_page
            print(f"  [API] GOV24 전체 서비스: {total_count}건 ({total_pages}페이지)")
        except Exception as e:
            print(f"    [ERR] GOV24 total count: {e}")
            total_pages = 110  # fallback

        for pg in range(1, total_pages + 1):
            try:
                resp = requests.get(url, params={
                    "page": pg, "perPage": per_page, "returnType": "JSON", "serviceKey": api_key,
                }, timeout=15)
                if resp.status_code == 429:
                    print(f"    [WARN] GOV24 API quota exceeded at page {pg}. Stopping.")
                    break
                if resp.status_code != 200:
                    print(f"    [ERR] GOV24 API Status {resp.status_code} at page {pg}")
                    break

                data = resp.json()
                items = data.get("data", [])
                if not items:
                    break
                all_items.extend(items)

                if pg % 20 == 0:
                    print(f"    ... page {pg}/{total_pages} ({len(all_items)} items)")

            except Exception as e:
                print(f"    [ERR] GOV24 page {pg}: {e}")
                break

        # 중복 제거 + 개인 서비스 필터 + 현재 신청 가능한 것만
        import re as _re
        from datetime import date as _date
        today_str = _date.today().strftime("%Y%m%d")

        seen_ids = set()
        individual = []
        expired_count = 0
        business_kw = ("기업", "법인", "사업자", "중소기업", "소상공인", "벤처")
        # 상시접수 키워드
        always_open_kw = ("상시", "수시", "연중", "해당시", "매월", "매년", "사유발생", "기간없음")

        for item in all_items:
            sid = item.get("서비스ID", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)

                # 1) 신청기한 체크 — 명확히 만료된 건 제외
                deadline_text = item.get("신청기한", "") or ""
                if deadline_text:
                    # 상시접수 키워드면 통과
                    if not any(k in deadline_text for k in always_open_kw):
                        # 날짜 패턴 추출하여 만료 체크 (YYYY.M.D 또는 YYYY-MM-DD)
                        dates = _re.findall(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", deadline_text)
                        if dates:
                            # 마지막 날짜(종료일)가 오늘 이전이면 만료
                            last = dates[-1]
                            end_str = f"{last[0]}{int(last[1]):02d}{int(last[2]):02d}"
                            if end_str < today_str:
                                expired_count += 1
                                continue

                # 2) 기업 전용 서비스 제외
                user_type = item.get("사용자구분코드", "") or item.get("사용자구분", "") or ""
                target = item.get("지원대상", "") or ""
                if any(k in str(user_type) for k in ("기업", "법인")):
                    if not any(k in str(user_type) for k in ("개인", "가구")):
                        continue
                if target and all(k in target for k in ("기업",)) and not any(k in target for k in ("개인", "국민", "주민")):
                    if any(k in target[:30] for k in business_kw):
                        continue

                individual.append(item)

        print(f"  [API] GOV24 개인복지: {len(all_items)}건 수집 → {len(individual)}건 (만료 {expired_count}건 제외)")
        return self._map_gov24_individual_fields(individual)

    def _map_gov24_individual_fields(self, items):
        """개인 복지서비스 API 응답 → 내부 형식 매핑 (target_type='individual')"""
        mapped = []
        for item in items:
            title = item.get("서비스명", "")
            detail_url = item.get("상세조회URL", "")
            if not title:
                continue
            if not detail_url:
                sid = item.get("서비스ID", "")
                detail_url = f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{sid}" if sid else ""
            if not detail_url:
                continue

            target = item.get("지원대상", "")
            selection = item.get("선정기준", "")
            support_content = item.get("지원내용", "")
            summary = item.get("서비스목적요약", "") or support_content[:300]

            eligibility = {}
            if target:
                eligibility["target_description"] = target[:500]
            if selection:
                eligibility["selection_criteria"] = selection[:500]

            deadline_raw = item.get("신청기한", "")
            deadline = self._normalize_date(deadline_raw) if deadline_raw else None

            dept = item.get("소관기관명", "")
            field = item.get("서비스분야", "")

            # 서비스분야 → 카테고리 매핑
            category = self._map_individual_category(field)

            org_type = item.get("소관기관유형", "")
            region = "전국"
            if org_type in ("지방자치단체", "시도", "시군구"):
                region = dept[:2] if dept else "전국"

            mapped.append({
                "title": title,
                "url": detail_url,
                "description": summary[:1000],
                "department": dept,
                "category": category,
                "origin_source": "gov24-individual-api",
                "region": region,
                "deadline_date": deadline,
                "eligibility_logic": eligibility,
                "target_type": "individual",
            })
        return mapped

    @staticmethod
    def _map_individual_category(field: str) -> str:
        """서비스분야 텍스트 → 개인 카테고리 매핑"""
        if not field:
            return "복지"
        field_lower = field.lower()
        mapping = {
            "복지": "복지", "생활안정": "복지", "보건": "의료", "의료": "의료",
            "교육": "교육", "장학": "교육", "훈련": "교육",
            "주거": "주거", "주택": "주거", "임대": "주거",
            "고용": "고용", "취업": "고용", "일자리": "고용",
            "출산": "출산", "육아": "출산", "보육": "출산", "양육": "출산", "임신": "출산",
            "금융": "금융", "세제": "금융", "감면": "금융", "대출": "금융", "서민금융": "금융",
            "소상공인": "금융", "창업": "금융", "자영업": "금융",
            "안전": "복지", "재난": "복지", "긴급": "복지",
        }
        for keyword, cat in mapping.items():
            if keyword in field_lower:
                return cat
        return "복지"

    # ─── 판판대로 (fanfandaero.kr) 스크래핑 ───

    _SCRAPE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    async def fetch_fanfandaero_programs(self):
        """판판대로 판로지원 사업공고 스크래핑"""
        url = "https://fanfandaero.kr/portal/preSprtBizPbanc.do"
        try:
            print("  [SCRAPE] Calling 판판대로...")
            resp = requests.get(url, headers=self._SCRAPE_HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"    [ERR] 판판대로 Status {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            items = []

            # 공고 목록 링크 탐색 (a 태그에서 sprtBizCd 파라미터 포함된 것)
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                if "sprtBizCd" not in href and "preSprtBizPbancDetail" not in href:
                    continue

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    # 부모 요소에서 제목 탐색
                    parent = a_tag.find_parent(["li", "tr", "div"])
                    if parent:
                        title = parent.get_text(strip=True)[:200]
                if not title or len(title) < 5:
                    continue

                detail_url = href
                if not detail_url.startswith("http"):
                    detail_url = f"https://fanfandaero.kr{detail_url}"

                items.append({
                    "title": title,
                    "url": detail_url,
                    "description": "",
                    "department": "중소벤처기업진흥공단",
                    "category": "Sales Channel Support",
                    "origin_source": "fanfandaero-scrape",
                    "region": "전국",
                    "deadline_date": None,
                })

            # 중복 URL 제거
            seen = set()
            unique = []
            for item in items:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)

            print(f"    [OK] 판판대로: {len(unique)} items scraped")
            return unique

        except Exception as e:
            print(f"  [ERR] 판판대로 Exception: {e}")
            return []

    async def fetch_exportvoucher_programs(self):
        """수출바우처 (수출지원기반활용사업) 사업공고 스크래핑"""
        url = "https://www.exportvoucher.com/portal/board/boardList"
        params = {
            "bbs_id": "1",
            "active_menu_cd": "EZ005004000",
            "pageUnit": "20",
            "pageNo": "1",
        }
        try:
            print("  [SCRAPE] Calling 수출바우처 포털...")
            resp = requests.get(url, params=params, headers=self._SCRAPE_HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                print(f"    [ERR] 수출바우처 Status {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            items = []

            # 게시판 목록에서 공고 추출
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                if "boardView" not in href and "ntt_id" not in href:
                    continue

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 5:
                    parent = a_tag.find_parent(["li", "tr", "td", "div"])
                    if parent:
                        title = parent.get_text(strip=True)[:200]
                if not title or len(title) < 5:
                    continue

                detail_url = href
                if not detail_url.startswith("http"):
                    detail_url = f"https://www.exportvoucher.com{detail_url}"

                items.append({
                    "title": title,
                    "url": detail_url,
                    "description": "",
                    "department": "중소벤처기업진흥공단",
                    "category": "Export Support",
                    "origin_source": "exportvoucher-scrape",
                    "region": "전국",
                    "deadline_date": None,
                })

            seen = set()
            unique = []
            for item in items:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)

            print(f"    [OK] 수출바우처: {len(unique)} items scraped")
            return unique

        except Exception as e:
            print(f"  [ERR] 수출바우처 Exception: {e}")
            return []

    # ─── 고용노동부 (Employment & Labor) — 농림부 고시공고 통합 ───

    async def fetch_moel_programs(self):
        """고용노동부 고용정책 + 농림축산식품부 고시공고 수집 (HTML 스크래핑)"""
        all_items = []
        try:
            # 농림축산식품부 고시/공고 (artclView 링크 추출)
            print("  [SCRAPE] Calling 농림축산식품부 고시공고...")
            mafra_url = "https://www.mafra.go.kr/bbs/mafra/68/artclList.do"
            resp = requests.get(mafra_url, headers=self._SCRAPE_HEADERS, timeout=15, verify=False)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag.get("href", "")
                    if "artclView" not in href:
                        continue
                    title = a_tag.get_text(strip=True)
                    if not title or len(title) < 8:
                        continue
                    detail_url = href if href.startswith("http") else f"https://www.mafra.go.kr{href}"
                    all_items.append({
                        "title": title,
                        "url": detail_url,
                        "description": "",
                        "department": "농림축산식품부",
                        "category": "Agriculture Support",
                        "origin_source": "mafra-scrape",
                        "region": "전국",
                        "deadline_date": None,
                    })

        except Exception as e:
            print(f"  [ERR] 고용/농림 scrape: {e}")

        # javascript: URL 필터링, 중복 제거
        seen = set()
        unique = []
        for item in all_items:
            url = item["url"]
            if "javascript:" in url or url in seen:
                continue
            seen.add(url)
            unique.append(item)
        print(f"    [OK] 고용/농림: {len(unique)} items")
        return unique

    # ─── 농림부/보증기금은 SPA → admin_scraper(Playwright)에 위임 ───
    # seed_regional_urls.py에 등록됨: 신용보증기금, 기술보증기금, 농촌진흥청 등

    async def fetch_mafra_programs(self):
        """농림축산식품부 — moel에 통합됨, 빈 리스트 반환"""
        return []

    async def fetch_guarantee_programs(self):
        """신보/기보 — SPA 사이트라 admin_scraper(Playwright)에 위임, 빈 리스트 반환"""
        print("  [INFO] 신보/기보는 admin_scraper(Playwright)에서 처리")
        return []


# Global Instance
gov_api_service = GovernmentAPIService()
