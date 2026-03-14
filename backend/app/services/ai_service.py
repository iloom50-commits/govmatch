import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class AIService:
    """정부지원사업 분석을 위한 AI 서비스 (Gemini 기반)"""
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("[WARN] GEMINI_API_KEY not found in environment variables")
            self.model = None
            return
            
        genai.configure(api_key=api_key)
        # Use a stable model name
        self.model = genai.GenerativeModel('models/gemini-2.0-flash')
        self.embedding_model = 'models/text-embedding-004'

    async def extract_program_details(self, text: str) -> Dict[str, Any]:
        """
        공고문 텍스트에서 전체 상세 정보(제목, 부서, 자격요건 등)를 구조화하여 추출
        """
        if not self.model:
            return {}
            
        prompt = f"""
        당신은 대한민국 정부 지원사업 분석 전문가입니다. 
        아래 공고문 텍스트를 분석하여 시스템에 저장할 수 있게 JSON 형식으로 구조화하세요.
        
        [공고문 텍스트]
        {text[:12000]}
        
        [추출할 JSON 구조]
        {{
            "title": "공고 제목",
            "department": "소관 부처 또는 기관 (예: '중소벤처기업부', '부산광역시')",
            "category": "분류 (예: 'Entrepreneurship', 'Tech', 'Global', 'Loan')",
            "description": "공고에 대한 핵심 요약 설명 (200자 이내, 순수 텍스트)",
            "business_type": ["소상공인", "중소기업", "스타트업", "예비창업자", "수출기업" 등 대상 기업 유형 — 공고에 명시된 것만],
            "target_keywords": ["공고 핵심 키워드 3~5개, 예: 소상공인, 시설개선, 정책자금, R&D, 수출"],
            "eligibility_logic": {{
                "min_founding_years": "숫자 (없으면 null)",
                "max_founding_years": "숫자 (없으면 null)",
                "min_employee_count": "숫자 (없으면 null)",
                "max_employee_count": "숫자 (없으면 null)",
                "max_revenue": "숫자 (단위: 원, 없으면 null)",
                "region_restriction": "지역명 (예: '부산', 없으면 '전국')",
                "target_industries": ["업종명1", "업종명2"],
                "required_certifications": ["벤처기업", "여성기업" 등]
            }},
            "deadline_date": "YYYY-MM-DD 형식 (공고문에 마감일이 명시된 경우만, 없거나 상시면 null)",
            "key_benefits": ["지원금액", "멘토링 등 핵심 혜택"],
            "summary_noun": "공고에 대한 아주 간략한 요약 (명사형)"
        }}
        
        반드시 순수 JSON 데이터만 반환하세요.
        """
        
        try:
            response = self.model.generate_content(prompt)
            clean_json = response.text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[-1].split("```")[0].strip()
                
            return json.loads(clean_json)
        except Exception as e:
            print(f"Error in extract_program_details: {e}")
            return {}

    async def extract_structured_eligibility(self, text: str) -> Dict[str, Any]:
        """
        공고 텍스트에서 지원 자격 요건을 구조화된 데이터로 추출 (90% 이상 정확도 목표)
        스크래퍼에서 호출하며 결과는 announcements.eligibility_logic 컬럼에 JSON 저장됨.
        """
        if not self.model:
            return {}

        prompt = f"""
        당신은 대한민국 정부 지원사업 공고 분석 전문가입니다.
        아래 공고문 텍스트를 분석하여 **지원 자격 요건**만 추출해 주세요.

        [공고문 텍스트]
        {text[:10000]}

        [추출할 JSON 구조 - 반드시 이 형식을 따르세요]
        {{
            "max_founding_years": null 또는 숫자,
            "min_founding_years": null 또는 숫자,
            "max_employee_count": null 또는 숫자,
            "min_employee_count": null 또는 숫자,
            "max_revenue": null 또는 숫자(단위: 원),
            "min_revenue": null 또는 숫자(단위: 원),
            "min_employees": null 또는 숫자,
            "region_restriction": "지역명" 또는 "전국",
            "target_industries": ["대상 업종명1", "대상 업종명2"],
            "required_certifications": ["벤처기업", "이노비즈" 등 필수 인증],
            "business_type": ["소상공인", "중소기업", "스타트업", "예비창업자", "수출기업" 등 대상 기업 유형 — 공고에 명시된 것만],
            "target_keywords": ["공고 핵심 키워드 3~5개, 예: 소상공인, 시설개선, 정책자금, R&D, 수출"],
            "summary_text": "공고 핵심 내용을 100자 이내 순수 텍스트로 요약 (HTML 없이)",
            "summary_noun": "공고 핵심 내용을 8자 이내 명사형으로 요약"
        }}

        [중요 지침]
        - 공고문에 명시되지 않은 조건은 반드시 null로 설정
        - 매출액은 원(KRW) 단위로 변환 (예: 5억 = 500000000)
        - 업력 조건은 "년" 단위 숫자만 추출 (예: "창업 7년 이내" → max_founding_years: 7)
        - 반드시 순수 JSON 데이터만 반환하세요. 설명 텍스트 없이.
        """

        try:
            response = self.model.generate_content(prompt)
            clean_json = response.text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            return json.loads(clean_json)
        except Exception as e:
            print(f"Error in extract_structured_eligibility: {e}")
            return {}

    async def get_embedding(self, text: str) -> List[float]:
        """텍스트의 벡터 임베딩 생성"""
        if not self.model: return []
        try:
            result = genai.embed_content(
                model=self.embedding_model,
                content=text[:2000],
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"Error in get_embedding: {e}")
            return []

    async def generate_match_explanation(self, company_profile: Dict, program_info: Dict) -> str:
        """매칭 사유를 명사형으로 간략히 생성"""
        if not self.model: return "조건 부합"
        
        prompt = f"""
        기업 프로필과 지원사업 정보를 바탕으로 매칭 사유를 명사형으로 간략히 생성하세요.
        
        [기업] {json.dumps(company_profile, ensure_ascii=False)}
        [사업] {json.dumps(program_info, ensure_ascii=False)}
        
        [출력 가이드]
        - 반드시 명사형으로 종결 (예: '업종 일치', '가점 대상')
        - 결과만 출력하세요.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return "매칭 조건 부합"

    async def recommend_industry(self, company_name: str, business_content: str = "") -> Dict[str, Any]:
        """기업명과 사업 내용을 기반으로 KSIC 업종 코드 후보 추천"""
        if not self.model: 
            return {
                "candidates": [
                    {"code": "62011", "name": "소프트웨어 개발 및 공급업", "description": "컴퓨터 소프트웨어 설계 및 개발", "reason": "기업명 기반 기본 추천"}
                ]
            }
        
        prompt = f"""
        기업명 '{company_name}'과 사업 내용 '{business_content}'을 바탕으로 가장 적합한 한국표준산업분류(KSIC) 5자리 코드 후보 3가지를 추천하세요.
        
        [출력 형식]
        {{
            "candidates": [
                {{
                    "code": "5자리숫자",
                    "name": "업종명",
                    "description": "업종에 대한 상세 설명 (무엇을 하는 업종인지)",
                    "reason": "이 기업에 추천하는 사유"
                }}
            ]
        }}
        
        반드시 JSON 형식으로만 응답하세요.
        """
        
        try:
            response = self.model.generate_content(prompt)
            clean_json = response.text.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
            return json.loads(clean_json)
        except Exception as e:
            print(f"Error in recommend_industry: {e}")
            return {
                "candidates": [
                    {"code": "62011", "name": "소프트웨어 개발 및 공급업", "description": "소프트웨어 개발 전반", "reason": "분석 오류로 인한 기본값"}
                ]
            }

    async def search_industry_hybrid(self, query: str) -> Dict[str, Any]:
        """DB 검색 + AI 보완 하이브리드 업종 추천"""
        candidates = []

        # 1. DB 검색 (보다 유연한 키워드 분리 검색)
        try:
            import psycopg2
            import psycopg2.extras
            from app.config import DATABASE_URL
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            cursor = conn.cursor()

            # 검색어를 공백으로 분리 (예: "화장품 판매" -> ["화장품", "판매"])
            keywords = [k.strip() for k in query.split() if len(k.strip()) > 1]
            if not keywords:
                keywords = [query]

            # 모든 키워드에 대해 검색 수행
            results_map = {}
            for kw in keywords[:3]:  # 상위 3개 키워드만
                search_term = f"%{kw}%"
                cursor.execute("""
                    SELECT code, name, description FROM ksic_classification
                    WHERE name LIKE %s OR description LIKE %s
                    LIMIT 3
                """, (search_term, search_term))
                for row in cursor.fetchall():
                    if row['code'] not in results_map:
                        results_map[row['code']] = {
                            "code": row['code'],
                            "name": row['name'],
                            "description": row['description'],
                            "reason": f"'{kw}' 키워드 검색 결과"
                        }

            candidates = list(results_map.values())[:5]
            conn.close()
        except Exception as e:
            print(f"DB Search Error: {e}")

        # 2. 결과가 부족하거나 의미 기반 추천이 필요한 경우 AI 호출 (정확도)
        if len(candidates) < 2 and len(query) >= 3:
            ai_res = await self.recommend_industry("기업", query)
            if "candidates" in ai_res:
                existing_codes = {c["code"] for c in candidates}
                for ai_cand in ai_res["candidates"]:
                    if ai_cand["code"] not in existing_codes:
                        candidates.append(ai_cand)
        
        # 3. 최후의 수단: 검색 결과가 아예 없는 경우
        if not candidates:
            candidates.append({
                "code": "00000",
                "name": "직접 선택 필요",
                "description": "정확한 매칭을 위해 업종 코드를 직접 입력하거나 더 구체적으로 검색해 주세요.",
                "reason": "검색 결과 없음"
            })
            
        return {"candidates": candidates[:5]}

ai_service = AIService()
