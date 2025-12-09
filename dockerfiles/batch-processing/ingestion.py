import os
import sys
import logging
from binance_sdk_c2c.c2c import ConfigurationRestAPI, C2C_REST_API_PROD_URL
from data_ingestion import C2CExtended

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    try:
        logging.info("Starting batch ingestion job...")

        # Retrieve secrets from environment variables (injected by K8s or Docker)
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")

        if not api_key or not api_secret:
            raise ValueError("BINANCE_API_KEY/BINANCE_API_SECRET are missing; set them in environment")
        
        # Configure the REST API client with the retrieved secrets
        configuration_rest_api = ConfigurationRestAPI(
            api_key=api_key,
            api_secret=api_secret,
            base_path=C2C_REST_API_PROD_URL
        )

        # Initialize the extended C2C client with the configuration
        ingestion = C2CExtended(configuration_rest_api)
        
        # Fetch yesterday's data
        logging.info("Fetching trade history for yesterday...")
        data = ingestion.get_yesterday()
        
        logging.info(f"Successfully retrieved {len(data)} records.")
        
        # You might want to save or process 'data' here
        # For now, just logging the count is enough as a proof of concept
        
    except Exception as e:
        logging.error(f"Ingestion job failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
