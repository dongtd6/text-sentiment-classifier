import psycopg2
from helpers import load_cfg

# Load config
cfg = load_cfg("../auth-values.yaml")
auth = cfg.get("auth")

# Connect
conn = psycopg2.connect(
    host=auth["host"],
    port=auth["port"],
    database=auth["database"],
    user=auth["username"],
    password=auth["password"],
)

cursor = conn.cursor()

# Create schema
cursor.execute("CREATE SCHEMA IF NOT EXISTS c2c;")

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS c2c.trades (
    order_number TEXT PRIMARY KEY,
    adv_no TEXT,
    trade_type TEXT CHECK (trade_type IN ('BUY','SELL')),
    asset VARCHAR(16),
    fiat VARCHAR(16),
    fiat_symbol VARCHAR(16),
    amount NUMERIC(38, 8) CHECK (amount >= 0),
    total_price NUMERIC(38, 8) CHECK (total_price >= 0),
    unit_price NUMERIC(38, 8) CHECK (unit_price >= 0),
    order_status TEXT,
    create_time_ms BIGINT,
    commission NUMERIC(38, 8) CHECK (commission >= 0),
    counter_part_nick_name TEXT,
    advertisement_role TEXT
);
""")

conn.commit()
cursor.close()
conn.close()

print("✅ Schema và table đã được tạo thành công!")


