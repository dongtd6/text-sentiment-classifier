import psycopg2
import random
import string
from datetime import datetime
from helpers import load_cfg

# =====================
# Utils
# =====================
def random_order_number():
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = ''.join(random.choices(string.digits, k=4))
    return f"ORD-{ts}-{rand}"

def random_adv_no():
    return f"ADV-{random.randint(10000, 99999)}"

def random_trade_type():
    return random.choice(["BUY", "SELL"])

def random_asset():
    return random.choice(["BTC", "ETH", "USDT"])

def random_fiat():
    return ("VND", "₫")

def random_amount(asset):
    if asset == "BTC":
        return round(random.uniform(0.0001, 0.01), 8)
    if asset == "ETH":
        return round(random.uniform(0.001, 0.5), 6)
    return round(random.uniform(10, 1000), 2)

def random_price(asset):
    prices = {
        "BTC": random.uniform(900_000_000, 1_200_000_000),
        "ETH": random.uniform(40_000_000, 80_000_000),
        "USDT": random.uniform(24_000, 26_000),
    }
    return round(prices[asset], 2)

def random_status():
    return random.choice(["COMPLETED", "CANCELLED", "PENDING"])

def random_nickname():
    return f"Trader_{random.randint(1000, 9999)}"


# =====================
# Load config
# =====================
cfg = load_cfg("../auth-values.yaml")
auth = cfg.get("auth")

# =====================
# Connect DB
# =====================
conn = psycopg2.connect(
    host=auth["host"],
    port=auth["port"],
    database=auth["database"],
    user=auth["username"],
    password=auth["password"],
)

cursor = conn.cursor()

# =====================
# Generate dummy data
# =====================
asset = random_asset()
fiat, fiat_symbol = random_fiat()
amount = random_amount(asset)
unit_price = random_price(asset)
total_price = round(amount * unit_price, 2)

dummy_data = {
    "order_number": random_order_number(),
    "adv_no": random_adv_no(),
    "trade_type": random_trade_type(),
    "asset": asset,
    "fiat": fiat,
    "fiat_symbol": fiat_symbol,
    "amount": amount,
    "total_price": total_price,
    "unit_price": unit_price,
    "order_status": random_status(),
    "create_time_ms": int(datetime.now().timestamp() * 1000),
    "commission": round(total_price * random.uniform(0.0005, 0.002), 2),
    "counter_part_nick_name": random_nickname(),
    "advertisement_role": random.choice(["BUYER", "SELLER"]),
}

# =====================
# Insert query
# =====================
insert_query = """
INSERT INTO c2c.trades (
    order_number, adv_no, trade_type, asset, fiat, fiat_symbol,
    amount, total_price, unit_price, order_status, create_time,
    commission, counter_part_nick_name, advertisement_role
) VALUES (
    %(order_number)s, %(adv_no)s, %(trade_type)s, %(asset)s, 
    %(fiat)s, %(fiat_symbol)s, %(amount)s, %(total_price)s, 
    %(unit_price)s, %(order_status)s, %(create_time_ms)s, 
    %(commission)s, %(counter_part_nick_name)s, %(advertisement_role)s
)
ON CONFLICT (order_number) DO UPDATE SET
    order_status = EXCLUDED.order_status;
"""

# =====================
# Execute
# =====================
try:
    cursor.execute(insert_query, dummy_data)
    conn.commit()

    print("✅ Insert random dummy data thành công")
    print("📊 Chi tiết record:")
    for k, v in dummy_data.items():
        print(f"   {k}: {v}")

    cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
    count = cursor.fetchone()[0]
    print(f"\n📈 Tổng số records trong c2c.trades: {count}")

except psycopg2.Error as e:
    conn.rollback()
    print(f"❌ Lỗi khi insert data: {e}")

finally:
    cursor.close()
    conn.close()
