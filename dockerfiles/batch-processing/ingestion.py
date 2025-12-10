import os
import sys
import logging
from datetime import datetime, timedelta
from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from data_ingestion import C2CExtended
from utils import write_to_parquet, ensure_directory, get_vietnam_tz

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    try:
        logging.info("Starting batch ingestion job...")

        # Retrieve secrets
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        # Output directory from env, default to local if not set
        output_dir = os.getenv("OUTPUT_DIR", "/app/data")

        if not api_key or not api_secret:
            raise ValueError("BINANCE_API_KEY/BINANCE_API_SECRET are missing")
        
        # Configure API
        configuration_rest_api = ConfigurationRestAPI(
            api_key=api_key,
            api_secret=api_secret,
            base_path=C2C_REST_API_PROD_URL
        )

        ingestion = C2CExtended(configuration_rest_api)
        
        # Fetch yesterday's data
        logging.info("Fetching trade history for yesterday...")
        data = ingestion.get_yesterday()
        logging.info(f"Successfully retrieved {len(data)} records.")
        
        # Save to Parquet
        if data:
            ensure_directory(output_dir)
            # Generate filename with yesterday's date
            tz = get_vietnam_tz()
            yesterday = (datetime.now(tz) - timedelta(days=1)).strftime('%Y%m%d')
            output_file = os.path.join(output_dir, f"c2c_trades_{yesterday}.parquet")
            
            logging.info(f"Writing data to {output_file}...")
            write_to_parquet(data, output_file)
            logging.info("Write complete.")
        else:
            logging.warning("No data retrieved to save.")
        
    except Exception as e:
        logging.error(f"Ingestion job failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
