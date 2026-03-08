import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

class GovernmentAPIService:
    """공공데이터포털(data.go.kr) 공식 API를 통한 지원사업 수집 서비스"""
    
    BASE_URL = "https://apis.data.go.kr"

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
            # Actual field names from data.go.kr MSS API include:
            # - pblancId (Notice ID)
            # - pblancNm (Notice Name)
            # - pblancCtnt (Notice Content)
            # - detailUrl (Detail URL)
            title = item.get("pblancNm") or item.get("title") or item.get("사업명")
            url = item.get("detailUrl") or item.get("link") or item.get("상세페이지URL")
            content = item.get("pblancCtnt") or item.get("contents") or item.get("사업개요")
            
            if title and url:
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": content or "",
                    "department": "중소벤처기업부",
                    "category": "Small Business/Startup",
                    "origin_source": "mss-api"
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
            print(f"  📡 Calling KISED API: {endpoint}")
            response = requests.get(endpoint, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"    ❌ KISED API Error: Status {response.status_code}")
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
                print(f"    ❌ KISED Parse Error: {e}")
                return []

        except Exception as e:
            print(f"  ❌ KISED Exception: {e}")
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
                    # Handle domain-only URLs
                    if not url.startswith("http"):
                        if "k-startup.go.kr" in url:
                            url = "https://www.k-startup.go.kr"
                        else:
                            url = f"https://{url}"
                    
                    mapped.append({
                        "title": title,
                        "url": url,
                        "description": cols.get("pbancCn") or cols.get("intg_pbanc_biz_nm") or "",
                        "department": cols.get("pbancDeptNm") or "창업진흥원",
                        "category": "Entrepreneurship",
                        "origin_source": "kised-api"
                    })
            print(f"    ✅ KISED XML Parsed {len(mapped)} items")
            return mapped
        except Exception as e:
            print(f"    ❌ KISED XML Parse Error: {e}")
            return []

    def _map_kised_fields(self, items):
        mapped = []
        for item in items:
            # Field names as per data.go.kr 'getAnnouncementInformation01':
            # pbancNm: 공고명
            # detlUrl: 상세페이지 URL
            # pbancCn: 공고내용
            # pbancDeptNm: 부서명/기관명
            title = item.get("pbancNm") or item.get("title")
            url = item.get("detlUrl") or item.get("link")
            
            if title and url:
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": item.get("pbancCn") or "",
                    "department": item.get("pbancDeptNm") or "창업진흥원",
                    "category": "Entrepreneurship",
                    "origin_source": "kised-api"
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
            print(f"  📡 Calling MSIT R&D API (page {page})...")
            response = requests.get(url, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    ❌ MSIT R&D API Error: Status {response.status_code}")
                return [] if page > 1 else self._get_mock_msit_data()

            if "<?xml" in response.text[:100]:
                return self._parse_msit_xml(response.text)

            try:
                data = response.json()
            except Exception:
                print(f"    ❌ MSIT JSON parse failed, trying XML...")
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
            print(f"    ✅ MSIT R&D API: {len(items)} items (total: {total})")
            return self._map_msit_fields(items)

        except Exception as e:
            print(f"  ❌ MSIT R&D API Exception: {e}")
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
            print("  ⚠️ BIZINFO_PORTAL_KEY not set. Falling back to mock/scraper.")
            return []

        url = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
        params = {
            "crtfcKey": key,
            "dataType": "json"
        }

        try:
            print(f"  📡 Calling Bizinfo Portal Direct API...")
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"    ❌ Bizinfo Portal API Error: Status {response.status_code}")
                return []

            data = response.json()
            # Bizinfo portal returns { "jsonArray": [...] }
            items = data.get("jsonArray", [])
            
            return self._map_bizinfo_portal_fields(items)
        except Exception as e:
            print(f"  ❌ Bizinfo Portal Exception: {e}")
            return []

    def _map_bizinfo_portal_fields(self, items):
        mapped = []
        for item in items:
            # Bizinfo Portal fields:
            # - pblancNm: 공고명
            # - pblancUrl: 상세페이지 경로 (Relative)
            # - bsnsSumryCn: 사업구약
            # - jrsdInsttNm: 소관기관
            # - pldirSportRealmLclasCodeNm: 분야
            title = item.get("pblancNm")
            rel_url = item.get("pblancUrl")
            
            if title and rel_url:
                full_url = f"https://www.bizinfo.go.kr{rel_url}"
                mapped.append({
                    "title": title,
                    "url": full_url,
                    "description": item.get("bsnsSumryCn") or "",
                    "department": item.get("jrsdInsttNm") or "기업마당",
                    "category": item.get("pldirSportRealmLclasCodeNm") or "General Business Support",
                    "origin_source": "bizinfo-portal-api"
                })
        return mapped

    def _map_bizinfo_fields(self, items):
        mapped = []
        for item in items:
            # Bizinfo V4 fields:
            # - pbaNm: 공고명
            # - pbaUrl: 상세페이지 URL
            # - pbaContents: 공고내용/요약
            # - pbaInst: 소관기관
            # - pbaArea: 지역
            title = item.get("pbaNm")
            url = item.get("pbaUrl")
            
            if title and url:
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": item.get("pbaContents") or "",
                    "department": item.get("pbaInst") or "기업마당",
                    "category": "General Business Support",
                    "origin_source": "bizinfo-api",
                    "region": item.get("pbaArea") or "All"
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

            if title and url:
                if not url.startswith("http"):
                    url = f"https://www.msit.go.kr{url}"
                mapped.append({
                    "title": title,
                    "url": url,
                    "description": "",
                    "department": dept,
                    "category": "R&D",
                    "origin_source": "msit-rnd-api"
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

                for child in item:
                    if child.tag == "subject":
                        title = child.text
                    elif child.tag == "viewUrl":
                        url = child.text
                    elif child.tag == "deptName" and child.text:
                        dept = child.text

                if title and url:
                    if not url.startswith("http"):
                        url = f"https://www.msit.go.kr{url}"
                    mapped.append({
                        "title": title,
                        "url": url,
                        "description": "",
                        "department": dept,
                        "category": "R&D",
                        "origin_source": "msit-rnd-api"
                    })
            print(f"    ✅ MSIT XML Parsed {len(mapped)} items")
            return mapped
        except Exception as e:
            print(f"    ❌ MSIT XML Parse Error: {e}")
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
            print("  ⚠️ SMES24_API_TOKEN not set. Skipping 중소벤처24.")
            return []

        import urllib.parse
        from datetime import datetime, timedelta

        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")

        encoded_token = urllib.parse.quote_plus(token)
        url = (
            f"https://www.smes.go.kr/fnct/apiReqst/extPblancInfo"
            f"?token={encoded_token}&strDt={start_date}&endDt={end_date}&html=no"
        )

        try:
            print(f"  📡 Calling 중소벤처24 API (period: {start_date}~{end_date})...")
            response = requests.get(url, timeout=30)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    ❌ SMES24 API Error: Status {response.status_code}")
                return []

            data = response.json()
            result_cd = data.get("resultCd", "99")
            if result_cd != "0":
                print(f"    ❌ SMES24 API Result: {data.get('resultMsg', 'Unknown error')} (code: {result_cd})")
                return []

            items = data.get("data", [])
            print(f"    ✅ SMES24 API: {len(items)} items fetched")
            return self._map_smes24_fields(items)

        except Exception as e:
            print(f"  ❌ SMES24 Exception: {e}")
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
                "deadline_date": item.get("pblancEndDt"),
                "eligibility_logic": eligibility
            })
        return mapped

    # ─── 한국식품산업클러스터진흥원 API (foodpolis) ───

    async def fetch_foodpolis_programs(self, page=1, per_page=20):
        """한국식품산업클러스터진흥원 일반사업공고 목록 조회"""
        api_key = os.getenv("FOODPOLIS_API_KEY")
        if not api_key:
            print("  ⚠️ FOODPOLIS_API_KEY not set. Skipping 식품산업클러스터.")
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
            print(f"  📡 Calling Foodpolis API...")
            response = requests.get(url, params=params, timeout=15)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"    ❌ Foodpolis API Error: Status {response.status_code}")
                return []

            data = response.json()
            items = data.get("data", data.get("items", data.get("body", {}).get("items", [])))
            if isinstance(items, dict) and "item" in items:
                items = items["item"]
            if not isinstance(items, list):
                items = [items] if items else []

            print(f"    ✅ Foodpolis API: {len(items)} items")
            return self._map_foodpolis_fields(items)

        except Exception as e:
            print(f"  ❌ Foodpolis Exception: {e}")
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

            mapped.append({
                "title": title,
                "url": url,
                "description": item.get("bbsCn") or item.get("sportCnts") or "",
                "department": "한국식품산업클러스터진흥원",
                "category": "Food Industry",
                "origin_source": "foodpolis-api",
                "region": item.get("areaNm") or "전국"
            })
        return mapped

# Global Instance
gov_api_service = GovernmentAPIService()
