# data_ingestion.py
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from binance_sdk_c2c.rest_api.models import GetC2CTradeHistoryResponseDataInner
from binance_sdk_c2c.c2c import C2C, ConfigurationRestAPI, C2C_REST_API_PROD_URL
from utils import (
    get_timestamp,
    filter_by_time_range,
    stable_sort_by_time,
    retry,
    write_to_csv,
    write_to_parquet,
    write_to_json,
    get_vietnam_tz,
    start_of_day,
    end_of_day,
    start_of_week,
    start_of_month,
    previous_week_range,
    previous_month_range,
)

# Configure logging
logging.basicConfig(level=logging.INFO)


class C2CExtended(C2C):
    """Extended C2C API with specific time-based trade history retrieval methods for Vietnam timezone (UTC+7)."""

    def __init__(self, config_rest_api: ConfigurationRestAPI = None) -> None:
        super().__init__(config_rest_api)
        self.max_records = 50  # Maximum records per request as per observed API limit
        self.tz_vietnam = get_vietnam_tz()  # UTC+7 For Vietnam timezone

    def _fetch_data(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Fetch all trade history records with pagination.
        
        Args:
            start_time (Optional[int]): Start timestamp in milliseconds
            end_time (Optional[int]): End timestamp in milliseconds
            
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of all trade records
        """
        fetch_data: List[GetC2CTradeHistoryResponseDataInner] = []
        page = 1
        consecutive_empty_pages = 0
        max_consecutive_empty_pages = 3  # Stop after 3 consecutive pages with no data in time range

        @retry(exceptions=(Exception,), tries=3, delay_seconds=1.0, backoff=2.0)
        def _get_page(p: int):
            return self.rest_api.get_c2_c_trade_history(
                page=p,
                recv_window=60000,
            )

        while True:
            response = _get_page(page)

            rate_limits = response.rate_limits
            logging.info(f"Page {page} rate limits: {rate_limits}")

            # Extract the inner data list from the response
            response_data = response.data()
            if response_data.code != '000000' or not response_data.data:
                logging.info(f"Stopping at page {page}: No more data or error (code: {response_data.code})")
                break

            data = response_data.data
            filtered_data = filter_by_time_range(data, start_time, end_time)
            fetch_data.extend(filtered_data)
            logging.info(f"Page {page} retrieved {len(data)} records, {len(filtered_data)} within time range")

            # Track consecutive empty pages
            if len(filtered_data) == 0:
                consecutive_empty_pages += 1
                logging.info(f"Consecutive empty pages: {consecutive_empty_pages}/{max_consecutive_empty_pages}")
                
                # Stop if we hit too many consecutive empty pages
                if consecutive_empty_pages >= max_consecutive_empty_pages:
                    logging.info(f"Stopping early: {consecutive_empty_pages} consecutive pages with no data in time range")
                    break
            else:
                # Reset counter if we found data
                consecutive_empty_pages = 0

            # If fewer than max_records, we've reached the end
            if len(data) < self.max_records:
                logging.info(f"Stopping at page {page}: Retrieved {len(data)} < {self.max_records} records (end of data)")
                break

            page += 1
        
        # Deduplicate by order_number and sort by create_time
        unique = {}
        for item in fetch_data:
            unique[getattr(item, 'order_number', None)] = item
        deduped = list(unique.values())
        return stable_sort_by_time(deduped)

    def get_latest(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history from 00:00 of current day to now in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """
        now = datetime.now(self.tz_vietnam)
        start_of_today = start_of_day(now)
        end_of_today = end_of_day(now)

        start_time = get_timestamp(start_of_today)
        end_time = get_timestamp(end_of_today)

        return self._fetch_data(start_time, end_time)

    def get_latest_by_week(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history from start of current week (Monday) to now in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """

        now = datetime.now(self.tz_vietnam)
        start_of_week_dt = start_of_week(now)

        start_time = get_timestamp(start_of_week_dt)
        end_time = get_timestamp(now)

        return self._fetch_data(start_time, end_time)

    def get_latest_by_month(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history from start of current month to now in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """
        now = datetime.now(self.tz_vietnam)
        start_of_month_dt = start_of_month(now)

        start_time = get_timestamp(start_of_month_dt)
        end_time = get_timestamp(now)

        return self._fetch_data(start_time, end_time)
    
    def get_prev_week_data(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history for the entire previous week (Monday to Sunday) in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """
        now = datetime.now(self.tz_vietnam)
        start_of_prev_week, end_of_prev_week = previous_week_range(now)

        start_time = get_timestamp(start_of_prev_week)
        end_time = get_timestamp(end_of_prev_week)

        return self._fetch_data(start_time, end_time)


    def get_prev_month(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history for the entire previous month in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """

        now = datetime.now(self.tz_vietnam)
        start_of_prev_month, end_of_prev_month = previous_month_range(now)

        start_time = get_timestamp(start_of_prev_month)
        end_time = get_timestamp(end_of_prev_month)

        return self._fetch_data(start_time, end_time)

        
    def get_yesterday(self) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history for the yesterday since today in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """

        now = datetime.now(self.tz_vietnam)
        
        # Start of yesterday
        start_of_yesterday = (now - timedelta(days=1)).replace(hour=0, 
                                                            minute=0,
                                                            second=0,
                                                            microsecond=0)
        
        # End of yesterday
        end_of_yesterday = start_of_yesterday.replace(hour=23,
                                                    minute=59,
                                                    second=59,
                                                    microsecond=999000)

        start_time = get_timestamp(start_of_yesterday)
        end_time = get_timestamp(end_of_yesterday)

        return self._fetch_data(start_time, end_time)

    def get_custom_range(self, start_date: str, end_date: str) -> List[GetC2CTradeHistoryResponseDataInner]:
        """
        Get trade history for a custom date range in Vietnam timezone (UTC+7).
        Includes both BUY and SELL trades.
        
        Args:
            start_date (str): Start date in format 'YYYY-MM-DD' (e.g., '2025-09-01')
            end_date (str): End date in format 'YYYY-MM-DD' (e.g., '2025-09-23')
        
        Returns:
            List[GetC2CTradeHistoryResponseDataInner]: List of trade records
        """
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').replace(tzinfo=self.tz_vietnam, hour=0, minute=0, second=0, microsecond=0)
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(tzinfo=self.tz_vietnam, hour=23, minute=59, second=59, microsecond=999000)
            
            # Validate date range (max 30 days as per API limit)
            if (end_dt - start_dt).days > 30:
                raise ValueError("Date range cannot exceed 30 days")

            start_time = get_timestamp(start_dt)
            end_time = get_timestamp(end_dt)

            return self._fetch_data(start_time, end_time)
        except ValueError as e:
            logging.error(f"Invalid date format or range: {str(e)}")
            return []

    def export_custom_range(self, start_date: str, end_date: str, fmt: str = 'csv') -> Optional[str]:
        """
        Fetch trades for a custom range and export to the desired format.

        Args:
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            fmt: 'csv' | 'json' | 'parquet'

        Returns:
            Optional[str]: Output file path (if created)
        """
        data = self.get_custom_range(start_date, end_date)
        cleaned = f"{start_date}_to_{end_date}"
        if fmt.lower() == 'csv':
            return write_to_csv(data, cleaned)
        if fmt.lower() == 'json':
            output_file = f"c2c_trade_history_{cleaned.replace('-', '').replace('/', '').replace(' ', '')}.json"
            return write_to_json(data, output_file)
        if fmt.lower() == 'parquet':
            output_file = f"c2c_trade_history_{cleaned.replace('-', '').replace('/', '').replace(' ', '')}.parquet"
            return write_to_parquet(data, output_file)
        logging.error(f"Unsupported export format: {fmt}")
        return None
