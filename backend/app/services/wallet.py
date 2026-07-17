# -*- coding: utf-8 -*-
"""크레딧 지갑 코어 (G1-2: 구독→크레딧 전환 인프라).

호출부(FastAPI 핸들러 등)가 커넥션/트랜잭션을 소유한다 — 이 모듈의 함수는
전달받은 cursor로만 동작하며 commit/rollback을 하지 않는다.

돈 경로 원칙:
- 차감(wallet_deduct)은 조건부 원자 UPDATE(credits >= amount)로 수행한다 —
  음수 잔액·이중차감이 구조적으로 불가능하다.
- 충전(wallet_record_charge)은 payments.portone_id UNIQUE 제약 +
  INSERT ... ON CONFLICT DO NOTHING으로 멱등 처리한다 — 중복 호출해도
  두 번째부터는 None을 반환하고 크레딧을 다시 적립하지 않는다.
"""


def wallet_balance(cur, user_id):
    """현재 크레딧 잔액을 반환한다. 사용자가 없으면 0."""
    cur.execute("SELECT credits FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row is None:
        return 0
    return row["credits"]


def wallet_add(cur, user_id, amount, tx_type, ref=None):
    """크레딧을 적립하고 원장에 기록한다. 새 잔액을 반환한다."""
    cur.execute(
        "UPDATE users SET credits = credits + %s WHERE user_id = %s RETURNING credits",
        (amount, user_id),
    )
    if cur.rowcount != 1:
        raise ValueError(f"wallet_add: user_id={user_id} 사용자를 찾을 수 없습니다")
    new_balance = cur.fetchone()["credits"]
    cur.execute(
        """
        INSERT INTO credit_transactions (user_id, type, amount, balance_after, ref)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, tx_type, amount, new_balance, ref),
    )
    return new_balance


def wallet_deduct(cur, user_id, amount, tx_type, ref=None):
    """크레딧을 조건부 원자 UPDATE로 차감한다.

    잔액이 부족하면 아무것도 바뀌지 않고(원장도 미기록) False를 반환한다.
    성공하면 원장에 음수 amount로 기록하고 True를 반환한다.
    """
    cur.execute(
        "UPDATE users SET credits = credits - %s WHERE user_id = %s AND credits >= %s RETURNING credits",
        (amount, user_id, amount),
    )
    if cur.rowcount != 1:
        return False
    new_balance = cur.fetchone()["credits"]
    cur.execute(
        """
        INSERT INTO credit_transactions (user_id, type, amount, balance_after, ref)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, tx_type, -amount, new_balance, ref),
    )
    return True


def wallet_record_charge(cur, user_id, amount_krw, credits, portone_id):
    """결제를 기록(멱등)하고 크레딧을 적립한다.

    같은 portone_id로 이미 처리된 결제면 payments에 행이 추가되지 않고
    None을 반환한다(크레딧 재적립 없음). 최초 처리 시 새 잔액을 반환한다.
    """
    cur.execute(
        """
        INSERT INTO payments (user_id, portone_id, amount_krw, credits, status)
        VALUES (%s, %s, %s, %s, 'paid')
        ON CONFLICT (portone_id) DO NOTHING
        RETURNING id
        """,
        (user_id, portone_id, amount_krw, credits),
    )
    if cur.fetchone() is None:
        return None
    return wallet_add(cur, user_id, credits, "charge", ref=portone_id)
