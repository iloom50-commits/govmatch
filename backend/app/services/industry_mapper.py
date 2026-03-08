import json

# KSIC AI Mapping Prompt
INDUSTRY_AI_PROMPT = """
너는 대한민국 표준산업분류(KSIC) 전문가다. 사용자의 업태/종목 정보를 읽고 가장 적합한 5자리 KSIC 코드를 추출해라.

[입력례]
업태: 서비스, 종목: 소프트웨어 개발 및 공급

[출력례]
{"industry_code": "62011", "industry_name": "컴퓨터 프로그래밍 서비스업"}

[주의사항]
1. 반드시 JSON 형식으로만 응답해라.
2. 확실하지 않으면 가장 근접한 분류를 선택해라.
"""

import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def map_industry_with_ai(business_type_text):
    """
    Calls Gemini LLM to map business type to a 5-digit KSIC code.
    """
    if not GEMINI_API_KEY:
        return {"industry_code": "00000", "industry_name": "기타 미분류 (API 키 없음)"}

    # Dynamic model selection
    model = None
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model = genai.GenerativeModel(m.name)
                break
    except Exception as e:
        print(f"Model listing failed: {e}")
        
    if not model:
        try:
            model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"Gemini init failed: {e}")
            return {"industry_code": "00000", "industry_name": "기타 미분류 (AI 초기화 실패)"}

    prompt = f"""
{INDUSTRY_AI_PROMPT}

사용자 정보:
{business_type_text}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[-1].split("```")[0].strip()
            
        return json.loads(text)
    except Exception as e:
        print(f"Industry Mapping Error: {e}")
        return {"industry_code": "00000", "industry_name": "기타 미분류 (코드 직접 입력 필요)"}

def process_company_data_with_ai(api_res):
    """
    Combines API data with AI industry mapping.
    """
    business_type = f"업태: {api_res.get('tax_type', 'NULL')}, 종목: {api_res.get('b_nm', 'NULL')}"
    ai_mapped = map_industry_with_ai(business_type)
    
    return {
        "company_name": api_res.get("b_nm"),
        "establishment_date": api_res.get("establish_date"), # Should be formatted
        "address_city": api_res.get("address", "").split()[0] if api_res.get("address") else "NULL",
        "industry_code": ai_mapped["industry_code"],
        "industry_name": ai_mapped["industry_name"],
        "is_complete": all([api_res.get("b_nm"), api_res.get("establish_date"), api_res.get("address")])
    }
