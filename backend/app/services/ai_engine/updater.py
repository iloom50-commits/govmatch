"""DB 저장 헬퍼 — COALESCE로 기존 값 보존.

원칙: 대화 중 얻은 정보는 즉시 저장. 단, 기존 값이 있으면 덮어쓰지 않음.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# extractor가 생성하는 필드 중 users 테이블에 저장할 것들
USERS_UPDATABLE_FIELDS = {
    "address_city": "address_city",
    "establishment_date": "establishment_date",
    "revenue_bracket": "revenue_bracket",
    "employee_count_bracket": "employee_count_bracket",
    "age_range": "age_range",
    "income_level": "income_level",
    "family_type": "family_type",
    "employment_status": "employment_status",
    "housing_status": "housing_status",
    "industry_code": "industry_code",
    "company_name": "company_name",
    # interests는 array → 콤마 문자열로 변환 후 저장
}

CLIENT_PROFILES_UPDATABLE_FIELDS = {
    "address_city": "address_city",
    "establishment_date": "establishment_date",
    "revenue_bracket": "revenue_bracket",
    "employee_count_bracket": "employee_count_bracket",
    "industry_code": "industry_code",
    "client_name": "client_name",
}


def save_extracted_to_users(business_number: str, extracted: Dict, db_conn) -> int:
    """대화에서 얻은 정보를 users 테이블에 저장 (COALESCE).

    Returns:
        업데이트된 필드 수
    """
    if not extracted or not business_number:
        return 0

    set_clauses = []
    params = []

    for field, column in USERS_UPDATABLE_FIELDS.items():
        value = extracted.get(field)
        if value is None or value == "":
            continue
        # 기존 값이 있으면 보존 (COALESCE 사용)
        set_clauses.append(f"{column} = COALESCE({column}, %s)")
        params.append(value)

    # interests는 배열 → 콤마 문자열
    interests = extracted.get("interests")
    if isinstance(interests, list) and interests:
        set_clauses.append("interests = COALESCE(NULLIF(interests, ''), %s)")
        params.append(",".join(interests))

    if not set_clauses:
        return 0

    params.append(business_number)
    sql = f"""
        UPDATE users
        SET {', '.join(set_clauses)}
        WHERE business_number = %s
    """

    try:
        cur = db_conn.cursor()
        cur.execute(sql, params)
        db_conn.commit()
        return cur.rowcount or 0
    except Exception as e:
        logger.warning(f"[profile_updater.users] save error: {e}")
        try: db_conn.rollback()
        except Exception: pass
        return 0


def save_extracted_to_client(client_profile_id: int, extracted: Dict, db_conn) -> int:
    """PRO 고객 프로필 저장 (COALESCE)."""
    if not extracted or not client_profile_id:
        return 0

    set_clauses = []
    params = []

    for field, column in CLIENT_PROFILES_UPDATABLE_FIELDS.items():
        value = extracted.get(field)
        if value is None or value == "":
            continue
        set_clauses.append(f"{column} = COALESCE({column}, %s)")
        params.append(value)

    interests = extracted.get("interests")
    if isinstance(interests, list) and interests:
        set_clauses.append("interests = COALESCE(NULLIF(interests, ''), %s)")
        params.append(",".join(interests))

    if not set_clauses:
        return 0

    # updated_at도 갱신
    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

    params.append(client_profile_id)
    sql = f"UPDATE client_profiles SET {', '.join(set_clauses)} WHERE id = %s"

    try:
        cur = db_conn.cursor()
        cur.execute(sql, params)
        db_conn.commit()
        return cur.rowcount or 0
    except Exception as e:
        logger.warning(f"[profile_updater.client] save error: {e}")
        try: db_conn.rollback()
        except Exception: pass
        return 0


def calculate_profile_completeness(user: dict) -> float:
    """프로필 완성도 0.0~1.0"""
    is_biz = (user or {}).get("user_type") in ("business", "both")
    required = (
        ["industry_code", "address_city", "revenue_bracket", "interests"]
        if is_biz else
        ["age_range", "address_city", "interests", "family_type"]
    )
    filled = sum(1 for f in required if (user or {}).get(f))
    return round(filled / len(required), 2) if required else 0.0
