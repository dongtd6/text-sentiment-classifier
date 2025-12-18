#!/usr/bin/env python3
# c2c_ingestion.py
"""
C2C Ingestion Job (Shared image for batch & streaming)

Features:
- fetch_by_mode (unchanged)
- DB UPSERT (optional, controlled by ENV)
- sleep(10s) on DB change (CDC test)

ENV:
- ENABLE_DB_UPSERT=true|false   (default=false)
"""

import os
import time
import logging
import psycopg2
from typing import List

from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from binance_sdk_c2c.rest_api.models import GetC2CTradeHistoryResponseDataInner
from data_ingestion import C2CExtended

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("c2c-ingestion")


# =========================================================
# FETCH DISPATCH (GIỮ NGUYÊN)
# =========================================================
def fetch_by_mode(
    client: C2CExtended,
    fetch_mode: str
) -> List[GetC2CTradeHistoryResponseDataInner]:

    fetch_mode = fetch_mode.lower()

    if fetch_mode == "latest":
        return client.get_latest()
    if fetch_mode == "latest_week":
        return client.get_latest_by_week()
    if fetch_mode == "latest_month":
        return client.get_latest_by_month()
    if fetch_mode == "yesterday":
        return client.get_yesterday()
    if fetch_mode == "prev_week":
        return client.get_prev_week_data()
    if fetch_mode == "prev_month":
        return client.get_prev_month()
    if fetch_mode == "custom":
        start_date = os.getenv("START_DATE")
        end_date = os.getenv("END_DATE")
        if not start_date or not end_date:
            raise ValueError("START_DATE and END_DATE must be set for custom mode")
        return client.get_custom_range(start_date, end_date)

    raise ValueError(f"Unsupported FETCH_MODE: {fetch_mode}")


# =========================================================
# DB UPSERT
# =========================================================
UPSERT_SQL = """
INSERT INTO c2c.trades (
    order_number,
    adv_no,
    trade_type,
    asset,
    fiat,
    fiat_symbol,
    amount,
    total_price,
    unit_price,
    order_status,
    create_time_ms,
    commission,
    counter_part_nick_name,
    advertisement_role
)
VALUES (
    %(order_number)s,
    %(adv_no)s,
    %(trade_type)s,
    %(asset)s,
    %(fiat)s,
    %(fiat_symbol)s,
    %(amount)s,
    %(total_price)s,
    %(unit_price)s,
    %(order_status)s,
    %(create_time_ms)s,
    %(commission)s,
    %(counter_part_nick_name)s,
    %(advertisement_role)s
)
ON CONFLICT (order_number)
DO UPDATE SET
    order_status = EXCLUDED.order_status
WHERE c2c.trades.order_status IS DISTINCT FROM EXCLUDED.order_status;
"""


def upsert_trade(cur, trade: GetC2CTradeHistoryResponseDataInner) -> bool:
    payload = {
        "order_number": trade.order_number,
        "adv_no": trade.adv_no,
        "trade_type": trade.trade_type,
        "asset": trade.asset,
        "fiat": trade.fiat,
        "fiat_symbol": trade.fiat_symbol,
        "amount": float(trade.amount or 0),
        "total_price": float(trade.total_price or 0),
        "unit_price": float(trade.unit_price or 0),
        "order_status": trade.order_status,
        "create_time_ms": getattr(trade, "create_time", None),
        "commission": float(trade.commission or 0),
        "counter_part_nick_name": trade.counter_part_nick_name,
        "advertisement_role": trade.advertisement_role,
    }

    cur.execute(UPSERT_SQL, payload)
    return cur.rowcount > 0


# =========================================================
# MAIN
# =========================================================
def main():
    logger.info("🚀 Starting C2C Ingestion Job")

    # =========================
    # ENV
    # =========================
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    fetch_mode = os.getenv("FETCH_MODE", "latest_month")

    enable_db = os.getenv("ENABLE_DB_UPSERT", "false").lower() == "true"

    logger.info(f"FETCH_MODE={fetch_mode}")
    logger.info(f"ENABLE_DB_UPSERT={enable_db}")

    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET not set")

    # =========================
    # API client
    # =========================
    config = ConfigurationRestAPI(
        api_key=api_key,
        api_secret=api_secret,
        base_path=C2C_REST_API_PROD_URL,
    )
    client = C2CExtended(config)

    # =========================
    # FETCH
    # =========================
    trades = fetch_by_mode(client, fetch_mode)
    logger.info(f"✅ Fetched {len(trades)} trades")

    if not trades:
        logger.warning("⚠️ No trades fetched → exit")
        return

    # =========================
    # BATCH MODE (NO DB)
    # =========================
    if not enable_db:
        logger.info("🟡 DB UPSERT DISABLED → fetch-only mode")
        return

    # =========================
    # DB MODE
    # =========================
    db_host = os.getenv("DB_HOST", "airflow-postgresql.orchestration.svc.cluster.local")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "c2c_trade")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")

    if not db_password:
        raise RuntimeError("DB_PASSWORD not set")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password,
    )
    conn.autocommit = False
    cur = conn.cursor()

    inserted_or_updated = 0
    skipped = 0

    for trade in trades:
        try:
            changed = upsert_trade(cur, trade)

            if changed:
                conn.commit()
                inserted_or_updated += 1

                logger.info(
                    f"📝 DB CHANGED | order={trade.order_number} "
                    f"status={trade.order_status} → sleep 10s"
                )

                time.sleep(10)  # CDC test

            else:
                conn.rollback()
                skipped += 1
                logger.info(
                    f"⏭️ SKIP | order={trade.order_number} "
                    f"status unchanged"
                )

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Error processing {trade.order_number}: {e}")

    cur.close()
    conn.close()

    logger.info("🏁 INGESTION FINISHED")
    logger.info(f"Inserted/Updated: {inserted_or_updated}")
    logger.info(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
