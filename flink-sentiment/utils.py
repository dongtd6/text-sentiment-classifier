# utils.py: User-Defined Function for calling REST API and processing comments
import json
import sys
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def call_model_api(model_url: str, comment: str) -> dict:
    """Call REST API for sentiment prediction."""
    payload = {"comment": comment}
    try:
        resp = requests.post(model_url, json=payload, timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {
            "original_comment": comment,
            "predicted_sentiment": "UNKNOWN",
            "error": str(e),
        }


def process_comment(value, model_url):
    """Parse Kafka message, call model API, and decide whether to send to out topic."""
    try:
        data = json.loads(value)
        # Extract review from the 'after' field (Debezium structure)
        after = data.get("after", {})
        comment = after.get("review", "")
        if not comment:
            logger.info(f"No review found in data: {value}")
            return None

        # Call REST API
        result = call_model_api(model_url, comment)
        predicted_sentiment = result.get("predicted_sentiment", "NEUTRAL")

        # Debug: Log API result and input
        logger.info(f"Input review: {comment}, API result: {result}")

        # Only return messages with NEG sentiment
        if predicted_sentiment == "NEG":
            # Include the entire 'after' object and add predicted_sentiment
            after["sentiment"] = predicted_sentiment
            return json.dumps(after)
        else:
            logger.info(f"Skipping non-NEG sentiment: {predicted_sentiment}")
            return None
    except Exception as e:
        logger.info(f"Error processing: {e}, value={value}")
        return None


def send_to_telegram(value, bot_token, chat_id):
    """Send message to Telegram with full content."""
    logger.info(f"Preparing to send to Telegram: {value}", file=sys.stderr)
    try:
        data = json.loads(value)

        # Simple timestamp formatting for Unix timestamps (microseconds)
        def format_timestamp(timestamp):
            if not timestamp or timestamp == "N/A":
                return "N/A"
            try:
                # Check if timestamp is an integer (Unix timestamp in microseconds)
                if isinstance(timestamp, int):
                    # Convert microseconds to seconds
                    dt = datetime.fromtimestamp(timestamp / 1_000_000)
                    return dt.strftime("%d/%m/%Y %H:%M:%S")
                # Try parsing as string in YYYY-MM-DD HH:MM:SS format
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%d/%m/%Y %H:%M:%S")
            except (ValueError, TypeError, OverflowError) as e:
                logger.info(
                    f"Error parsing timestamp {timestamp}: {e}", file=sys.stderr
                )
                return str(timestamp)  # Return original as string

        created_at = format_timestamp(data.get("created_at", "N/A"))
        updated_at = format_timestamp(data.get("updated_at", "N/A"))

        message = (
            f"🚨 Negative Review Alert 🚨\n"
            f"Review ID: {data.get('review_id', 'N/A')}\n"
            f"Product ID: {data.get('product_id', 'N/A')}\n"
            f"User ID: {data.get('user_id', 'N/A')}\n"
            f"Review: {data.get('review', 'N/A')}\n"
            f"Source: {data.get('source', 'N/A')}\n"
            f"Sentiment: {data.get('sentiment', 'N/A')}\n"
            f"Created At: {created_at}\n"
            f"Updated At: {updated_at}\n"
            f"Is Deleted: {data.get('is_deleted', 'N/A')}"
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        logger.info(
            f"Sending to Telegram API: {url}, payload: {payload}", file=sys.stderr
        )
        session = requests.Session()
        retries = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        response = session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Sent to Telegram: {message}", file=sys.stderr)
        return value
    except Exception as e:
        logger.info(f"Error sending to Telegram: {e}, message={value}", file=sys.stderr)
        return None
