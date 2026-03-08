import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import time

def scrape_kstartup_announcements():
    """
    Scrapes the first page of K-Startup announcements and saves them to the DB.
    """
    url = "https://www.k-startup.go.kr/ks/announcement/announcList.do"
    
    # In a real scenario, we might need headers to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # response = requests.get(url, headers=headers)
        # soup = BeautifulSoup(response.text, "html.parser")
        
        # Simulated Scraping Result for Demonstration
        # In Phase 2, we simulate the 'extraction' logic but populate the DB with more realistic data.
        mock_scraped_data = [
            {
                "title": "2026 글로벌 스타트업 해외 진출 패키지",
                "origin_url": "https://www.k-startup.go.kr/ks/announcement/101",
                "region": "전국",
                "industry": "전업종",
                "age_limit": 7,
                "amount": "최대 1억원 사업화 자금",
                "deadline": "2026-06-30",
                "summary": "우수 스타트업의 해외 현지화 및 판로 개척 지원"
            },
            {
                "title": "부울경 지역 특화 AI 바우처 지원사업",
                "origin_url": "https://www.k-startup.go.kr/ks/announcement/102",
                "region": "부산, 울산, 경남",
                "industry": "IT, 제조",
                "age_limit": 5,
                "amount": "컴퓨팅 자원 및 컨설팅 지원 (5,000만원 상당)",
                "deadline": "2026-05-15",
                "summary": "AI 솔루션 도입을 희망하는 중소기업 대상 바우처 지급"
            }
        ]
        
        save_scraped_to_db(mock_scraped_data)
        return {"status": "SUCCESS", "count": len(mock_scraped_data)}
        
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

def save_scraped_to_db(data_list):
    conn = sqlite3.connect("gov_matching.db")
    cursor = conn.cursor()
    
    for item in data_list:
        try:
            cursor.execute("""
                INSERT INTO announcements (title, origin_url, region, target_industry_codes, established_years_limit, support_amount, deadline_date, summary_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(origin_url) DO NOTHING
            """, (
                item["title"], item["origin_url"], item["region"], 
                item["industry"], item["age_limit"], item["amount"], 
                item["deadline"], item["summary"]
            ))
        except Exception as e:
            print(f"Error saving {item['title']}: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Starting K-Startup Scraping...")
    result = scrape_kstartup_announcements()
    print(result)
