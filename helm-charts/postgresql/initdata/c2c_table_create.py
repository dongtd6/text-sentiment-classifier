import psycopg2
from helpers import load_cfg

# Load config
cfg = load_cfg("../auth-values.yaml")
auth = cfg.get("auth")

# Connect to default DB to create database if needed
conn = psycopg2.connect(
    host=auth["host"],
    port=auth["port"],
    database=auth["database"],
    user=auth["username"],
    password=auth["password"],
)
conn.autocommit = True
cursor = conn.cursor()

# 1) Create database c2c_trade if not exists (PostgreSQL)
cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'c2c_trade';")
exists = cursor.fetchone()
if not exists:
    cursor.execute("CREATE DATABASE c2c_trade;")
    print("✅ Database c2c_trade created")
else:
    print("ℹ️  Database c2c_trade already exists")

cursor.close()
conn.close()

# 2) Connect to c2c_trade to create schema/table
conn = psycopg2.connect(
    host=auth["host"],
    port=auth["port"],
    database="c2c_trade",
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
    create_time BIGINT,
    commission NUMERIC(38, 8) CHECK (commission >= 0),
    counter_part_nick_name TEXT,
    advertisement_role TEXT
);
""")

conn.commit()
cursor.close()
conn.close()

print("✅ Database c2c_trade, schema c2c, and table trades are ready!")


