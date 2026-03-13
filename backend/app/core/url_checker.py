import psycopg2
import psycopg2.extras
from app.config import DATABASE_URL

def check_duplicate_url(input_url, database_url=DATABASE_URL):
    """
    Check if the input URL already exists in the announcements table.
    """
    try:
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        cursor = conn.cursor()

        # SQL query to check existence
        query = "SELECT announcement_id FROM announcements WHERE origin_url = %s"
        cursor.execute(query, (input_url,))
        result = cursor.fetchone()

        conn.close()

        if result:
            return {
                "status": "ALREADY_EXISTS",
                "message": "이미 분석된 공고입니다.",
                "data": {"announcement_id": result["announcement_id"]}
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
