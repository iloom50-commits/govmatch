"""scraper_runs 로그 테이블 생성 — 일회성 마이그레이션.
각 스크래퍼 실행 결과 기록용. 오케스트레이터 감시의 데이터 소스.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
from app.main import get_db_connection

SQL = """
CREATE TABLE IF NOT EXISTS scraper_runs (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(80) NOT NULL,
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at TIMESTAMP,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  items_found INT DEFAULT 0,
  items_saved INT DEFAULT 0,
  error_message TEXT,
  elapsed_sec REAL
);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_source_start
  ON scraper_runs(source, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scraper_runs_start
  ON scraper_runs(started_at DESC);
"""

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(SQL)
    conn.commit()
    cur.execute("SELECT COUNT(*) c FROM scraper_runs")
    print(f"scraper_runs 테이블 준비 완료 (기존 rows: {cur.fetchone()['c']})")
    conn.close()

if __name__ == "__main__":
    main()
