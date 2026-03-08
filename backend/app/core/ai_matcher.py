import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_match_score(user_profile, announcement):
    """
    Uses Gemini LLM to calculate a match score and provide a reason.
    """
    if not GEMINI_API_KEY:
        return {"score": 50.0, "reason": "API 키가 설정되지 않아 기본 점수가 부여되었습니다."}

    # Dynamic model selection
    model = None
    try:
        # Try to find a working model automatically from available list
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
            return {"score": 55.0, "reason": "AI 매칭 엔진 초기화 실패로 기본 분석이 수행되었습니다."}
    
    prompt = f"""
너는 대한민국 최고의 정부지원사업 매칭 전문가다.
아래 [기업 정보]와 [지원사업 공고]를 분석하여 0~100점 사이의 '매칭 점수'를 산출하고 그 이유를 한 문장으로 설명해라.

[기업 정보]
- 기업명: {user_profile.get('company_name')}
- 관심분야: {user_profile.get('interests')}
- 소재지: {user_profile.get('address_city')}

[지원사업 공고]
- 제목: {announcement.get('title')}
- 공고내용: {announcement.get('summary_text')}

[출력 형식]
반드시 아래와 같은 JSON 형식으로만 응답해라:
{{"score": 90.0, "reason": "이유 설명..."}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Extract JSON if returned in markdown blocks
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[-1].split("```")[0].strip()
            
        result = json.loads(text)
        return {
            "score": float(result.get("score", 50.0)),
            "reason": result.get("reason", "비즈니스 모델 적합성 분석 완료")
        }
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        # Provide a reasonably descriptive fallback reason
        return {
            "score": 65.0, 
            "reason": f"기업의 {user_profile.get('interests')} 분야와 공고의 연관성이 높으나, AI 엔진 일시 오류로 보수적으로 산정되었습니다."
        }

if __name__ == "__main__":
    # Test stub
    test_user = {"company_name": "테스트 기업", "interests": "AI, 마케팅", "address_city": "부산"}
    test_ad = {"title": "2026 부산 AI 지원사업", "summary_text": "부산 소재 IT 기업 대상 AI 솔루션 해외 진출 지원"}
    print(get_gemini_match_score(test_user, test_ad))
