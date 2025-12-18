#!/usr/bin/env python3
"""
C2C Ingestion Job (Fetch-only)
- Fetch data from Binance C2C API
- Support dynamic FETCH_MODE
- Optional export (csv | json | parquet)
- NO DB insert
- NO Telegram (for now)
"""

import os
import logging
from typing import List
from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from binance_sdk_c2c.rest_api.models import GetC2CTradeHistoryResponseDataInner
from data_ingestion import C2CExtended  # adjust import if needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("c2c-ingestion")


def fetch_by_mode(
    client: C2CExtended,
    fetch_mode: str
) -> List[GetC2CTradeHistoryResponseDataInner]:
    """
    Dispatch fetch based on FETCH_MODE
    """
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


def main():
    logger.info("🚀 Starting C2C Ingestion Job")

    # =========================
    # ENV
    # =========================
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    fetch_mode = os.getenv("FETCH_MODE", "latest_month")
    export_format = os.getenv("EXPORT_FORMAT")  # csv | json | parquet | None

    if not api_key or not api_secret:
        raise RuntimeError("BINANCE_API_KEY and BINANCE_API_SECRET must be set")

    logger.info(f"FETCH_MODE={fetch_mode}")
    logger.info(f"EXPORT_FORMAT={export_format}")

    # =========================
    # API client
    # =========================
    config = ConfigurationRestAPI(
        api_key=api_key,
        api_secret=api_secret,
        base_path=C2C_REST_API_PROD_URL
    )
    client = C2CExtended(config)

    # =========================
    # Fetch
    # =========================
    trades = fetch_by_mode(client, fetch_mode)
    logger.info(f"✅ Fetched {len(trades)} trade records")

    # =========================
    # Optional export
    # =========================
    if export_format:
        logger.info(f"Exporting data as {export_format}")
        if export_format == "csv":
            client.export_custom_range("runtime", "runtime", fmt="csv")
        elif export_format == "json":
            client.export_custom_range("runtime", "runtime", fmt="json")
        elif export_format == "parquet":
            client.export_custom_range("runtime", "runtime", fmt="parquet")
        else:
            logger.warning(f"Unsupported EXPORT_FORMAT={export_format}")

    logger.info("🏁 Ingestion job finished successfully")


if __name__ == "__main__":
    main()
