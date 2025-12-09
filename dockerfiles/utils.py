import csv
import json
import logging
import math
import os
from typing import Callable, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar
from binance_sdk_c2c.rest_api.models import GetC2CTradeHistoryResponseDataInner
from datetime import datetime, timedelta, timezone
from functools import wraps
from time import sleep

T = TypeVar("T")

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_timestamp(date: datetime = None) -> int:
    """
    Get timestamp in miliseconds for a given datatime or current time in UTC+7

    Args:
        date (datetime, optional): The dateime to convert to timestamp.
                                    If None, uses current time in UTC+7
    
    Returns:
        int: Timesptampt in miliseconds sice Unix epoch (00:00:00 UTC, 01/01/1970).

    """
    tz_vietnam = timezone(timedelta(hours=7)) # UTC+7 for Vietnam timezone

    # Use provided date or current time in UTC+7
    dt = date if date is not None else datetime.now(tz_vietnam)

    # Ensure the datetime is timezone-aware with UTC+7
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz_vietnam)
    
    # Return timestamp (milliseconds)
    return int(dt.timestamp() * 1000)


def to_datetime_ms(ms: int, tz: timezone = timezone(timedelta(hours=7))) -> datetime:
    """
    Convert milliseconds since epoch to timezone-aware datetime.

    Args:
        ms (int): Milliseconds since Unix epoch.
        tz (timezone): Target timezone. Defaults to UTC+7.

    Returns:
        datetime: Timezone-aware datetime.
    """
    seconds = ms / 1000.0
    return datetime.fromtimestamp(seconds, tz=tz)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S%z") -> str:
    return dt.strftime(fmt)


def parse_date(date_str: str, fmt: str = "%Y-%m-%d", tz: timezone = timezone(timedelta(hours=7))) -> datetime:
    dt = datetime.strptime(date_str, fmt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt


def get_vietnam_tz() -> timezone:
    return timezone(timedelta(hours=7))


def start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999000)


def start_of_week(dt: datetime) -> datetime:
    days_since_monday = dt.weekday()
    return (dt - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)


def previous_week_range(dt: datetime) -> Tuple[datetime, datetime]:
    sow = start_of_week(dt)
    start_prev = sow - timedelta(days=7)
    end_prev = start_prev + timedelta(days=7) - timedelta(milliseconds=1)
    return start_prev, end_prev


def previous_month_range(dt: datetime) -> Tuple[datetime, datetime]:
    start_current_month = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_prev = (start_current_month - timedelta(days=1)).replace(day=1)
    if start_prev.month == 12:
        end_prev = start_prev.replace(year=start_prev.year + 1, month=1, day=1)
    else:
        end_prev = start_prev.replace(month=start_prev.month + 1, day=1)
    end_prev -= timedelta(milliseconds=1)
    return start_prev, end_prev


def chunk_iterable(items: Sequence[T], chunk_size: int) -> Iterator[Sequence[T]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def filter_by_time_range(
    items: Iterable[GetC2CTradeHistoryResponseDataInner],
    start_ms: Optional[int],
    end_ms: Optional[int],
) -> List[GetC2CTradeHistoryResponseDataInner]:
    result: List[GetC2CTradeHistoryResponseDataInner] = []
    for it in items:
        ts = getattr(it, "create_time", None)
        if ts is None:
            continue
        if start_ms is not None and ts < start_ms:
            continue
        if end_ms is not None and ts > end_ms:
            continue
        result.append(it)
    return result


def stable_sort_by_time(items: List[GetC2CTradeHistoryResponseDataInner]) -> List[GetC2CTradeHistoryResponseDataInner]:
    return sorted(items, key=lambda x: getattr(x, "create_time", 0))


def env_str(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


def env_int(key: str, default: Optional[int] = None) -> Optional[int]:
    val = env_str(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        logging.warning(f"Invalid int for env {key}={val}, using default {default}")
        return default


def retry(
    exceptions: Tuple[type, ...],
    tries: int = 3,
    delay_seconds: float = 1.0,
    backoff: float = 2.0,
    logger: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            _tries = max(1, tries)
            _delay = max(0.0, delay_seconds)
            for attempt in range(1, _tries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:  # type: ignore[misc]
                    if attempt == _tries:
                        raise
                    log = logger if logger is not None else logging
                    log.warning(f"Attempt {attempt} failed: {exc}. Retrying in {_delay:.2f}s...")
                    sleep(_delay)
                    _delay *= backoff
            # Unreachable
            return func(*args, **kwargs)
        return wrapper
    return decorator


def write_to_csv(data: List[GetC2CTradeHistoryResponseDataInner], date_str: str) -> str:
    """
    Write trade history data to a CSV file with an auto-generated name based on the provided date string.

    Args:
        data (List[GetC2CTradeHistoryResponseDataInner]): List of trade records to write.
        date_str (str): Date string (e.g., '2025-09-23') to include in the CSV filename.

    Returns:
        str: Path to the generated CSV file.
    """
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Format date string to ensure no invalid characters (e.g., replace '-' with '')
    cleaned_date_str = date_str.replace('-', '').replace('/', '').replace(' ', '')
    output_file = f"c2c_trade_history_{cleaned_date_str}.csv"

    # Define headers for CSV
    headers = [
        'order_number', 'adv_no', 'trade_type', 'asset', 'fiat',
        'fiat_symbol', 'amount', 'total_price', 'unit_price',
        'order_status', 'create_time', 'commission',
        'counter_part_nick_name', 'advertisement_role'
    ]

    try:
        if data:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()

                for item in data:
                    writer.writerow({
                        'order_number': item.order_number,
                        'adv_no': item.adv_no,
                        'trade_type': item.trade_type,
                        'asset': item.asset,
                        'fiat': item.fiat,
                        'fiat_symbol': item.fiat_symbol,
                        'amount': item.amount,
                        'total_price': item.total_price,
                        'unit_price': item.unit_price,
                        'order_status': item.order_status,
                        'create_time': item.create_time,  # Keep as timestamp
                        'commission': item.commission,
                        'counter_part_nick_name': item.counter_part_nick_name,
                        'advertisement_role': item.advertisement_role
                    })

            logging.info(f"Trade history written to {output_file} with {len(data)} records")
            return output_file
        else:
            logging.warning(f"No data to write to CSV for date {date_str}")
            return output_file

    except Exception as e:
        logging.error(f"Error writing to CSV for date {date_str}: {str(e)}")
        return output_file


def write_to_json(data: List[GetC2CTradeHistoryResponseDataInner], output_file: str) -> str:
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([_as_dict(d) for d in data], f, ensure_ascii=False)
        logging.info(f"Trade history written to {output_file} with {len(data)} records")
        return output_file
    except Exception as e:
        logging.error(f"Error writing to JSON {output_file}: {str(e)}")
        return output_file


def _as_dict(item: GetC2CTradeHistoryResponseDataInner) -> dict:
    return {
        'order_number': item.order_number,
        'adv_no': item.adv_no,
        'trade_type': item.trade_type,
        'asset': item.asset,
        'fiat': item.fiat,
        'fiat_symbol': item.fiat_symbol,
        'amount': item.amount,
        'total_price': item.total_price,
        'unit_price': item.unit_price,
        'order_status': item.order_status,
        'create_time': item.create_time,
        'commission': item.commission,
        'counter_part_nick_name': item.counter_part_nick_name,
        'advertisement_role': item.advertisement_role,
    }


def write_to_parquet(data: List[GetC2CTradeHistoryResponseDataInner], output_file: str) -> Optional[str]:
    try:
        import pandas as pd
        if not data:
            logging.warning("No data to write to Parquet")
            return output_file
        df = pd.DataFrame([_as_dict(d) for d in data])
        df.to_parquet(output_file, index=False)
        logging.info(f"Trade history written to {output_file} with {len(data)} records")
        return output_file
    except Exception as e:
        logging.error(f"Error writing to Parquet {output_file}: {str(e)}")
        return None


def clamp(n: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(n, max_value))


def milliseconds_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


def ensure_directory(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logging.error(f"Cannot create directory {path}: {e}")