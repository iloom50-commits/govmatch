import os
import json
import requests
from dotenv import load_dotenv
from app.services.industry_mapper import process_company_data_with_ai

load_dotenv()

# API configuration from environment
API_KEY = os.getenv("PUBLIC_DATA_PORTAL_KEY")
API_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"

def format_date(date_str):
    """Converts 8-digit date string to YYYY-MM-DD"""
    if not date_str or len(date_str) != 8:
        return "" # Return empty if not provided
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

def extract_city(address):
    """Extracts city/province from address string"""
    if not address:
        return "전국"
    return address.split()[0]

def get_company_profile(business_number):
    """
    Returns a basic company profile structure without mandatory NTS verification.
    Simplified as per user request to streamline onboarding.
    """
    try:
        # NTS API call is now bypassed. 
        # We provide a clean initial structure for any 10-digit number.
        
        final_data = {
            "business_number": business_number,
            "company_name": "", # User provides in Step 2
            "establishment_date": "", # User provides in Step 2
            "address_city": "전국", # Initial default
            "industry_code": "", 
            "industry_name": "",
            "revenue": "", 
            "employees": "",
            "status": "VALID" # Always valid to allow onboarding
        }
        
        return {
            "status": "SUCCESS",
            "data": final_data
        }
        
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"프로필 초기화 중 오류 발생: {str(e)}"
        }

if __name__ == "__main__":
    # Example usage
    test_bn = "1234567890"
    print(json.dumps(get_company_profile(test_bn), indent=2, ensure_ascii=False))
