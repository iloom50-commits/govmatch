import sqlite3  # Using sqlite3 for mock/initial local testing, can be swapped for psycopg2

def check_duplicate_url(input_url, db_path="gov_matching.db"):
    """
    Check if the input URL already exists in the announcements table.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # SQL query to check existence
        query = "SELECT announcement_id FROM announcements WHERE origin_url = ?"
        cursor.execute(query, (input_url,))
        result = cursor.fetchone()
        
        conn.close()
        
        if result:
            return {
                "status": "ALREADY_EXISTS",
                "message": "이미 분석된 공고입니다.",
                "data": {"announcement_id": result[0]}
            }
        else:
            return {
                "status": "NEW_URL",
                "message": "새로운 공고입니다. AI 분석을 시작합니다."
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"DB 조회 중 오류 발생: {str(e)}"
        }

if __name__ == "__main__":
    # Example usage
    test_url = "https://www.bizinfo.go.kr/example-notice-123"
    print(check_duplicate_url(test_url))
