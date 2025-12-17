import psycopg2
from datetime import datetime, timedelta
import random
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

# Sample data for generating dummy records
assets = ['BTC', 'ETH', 'USDT', 'BNB', 'SOL']
fiats = [
    ('VND', '₫'),
    ('USD', '$'),
    ('EUR', '€'),
    ('JPY', '¥'),
]
trade_types = ['BUY', 'SELL']
statuses = ['COMPLETED', 'PROCESSING', 'PENDING', 'CANCELLED']
advertisement_roles = ['BUYER', 'SELLER']

def generate_dummy_trade(index):
    """Generate a single dummy trade record"""
    fiat, fiat_symbol = random.choice(fiats)
    asset = random.choice(assets)
    trade_type = random.choice(trade_types)
    
    # Generate realistic amounts based on asset
    if asset == 'BTC':
        amount = round(random.uniform(0.001, 0.5), 8)
        unit_price = random.uniform(800000000, 1200000000) if fiat == 'VND' else random.uniform(40000, 60000)
    elif asset == 'ETH':
        amount = round(random.uniform(0.01, 5), 8)
        unit_price = random.uniform(50000000, 80000000) if fiat == 'VND' else random.uniform(2500, 4000)
    elif asset == 'USDT':
        amount = round(random.uniform(10, 10000), 8)
        unit_price = random.uniform(23000, 25000) if fiat == 'VND' else 1.0
    else:
        amount = round(random.uniform(0.1, 100), 8)
        unit_price = random.uniform(1000000, 5000000) if fiat == 'VND' else random.uniform(50, 200)
    
    total_price = round(amount * unit_price, 8)
    commission = round(total_price * 0.001, 8)  # 0.1% commission
    
    # Generate timestamp (random time in the last 30 days)
    days_ago = random.randint(0, 30)
    create_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
    
    return {
        'order_number': f'ORD-{create_time.strftime("%Y%m%d")}-{index:04d}',
        'adv_no': f'ADV-{random.randint(10000, 99999)}',
        'trade_type': trade_type,
        'asset': asset,
        'fiat': fiat,
        'fiat_symbol': fiat_symbol,
        'amount': amount,
        'total_price': total_price,
        'unit_price': unit_price,
        'order_status': random.choice(statuses),
        'create_time_ms': int(create_time.timestamp() * 1000),
        'commission': commission,
        'counter_part_nick_name': f'Trader{random.choice(["VN", "US", "JP", "EU"])}{random.randint(100, 999)}',
        'advertisement_role': random.choice(advertisement_roles)
    }

# Insert query
insert_query = """
INSERT INTO c2c.trades (
    order_number, adv_no, trade_type, asset, fiat, fiat_symbol,
    amount, total_price, unit_price, order_status, create_time_ms,
    commission, counter_part_nick_name, advertisement_role
) VALUES (
    %(order_number)s, %(adv_no)s, %(trade_type)s, %(asset)s, 
    %(fiat)s, %(fiat_symbol)s, %(amount)s, %(total_price)s, 
    %(unit_price)s, %(order_status)s, %(create_time_ms)s, 
    %(commission)s, %(counter_part_nick_name)s, %(advertisement_role)s
)
ON CONFLICT (order_number) DO NOTHING;
"""

# Number of dummy records to insert
NUM_RECORDS = 20

print(f"🚀 Đang insert {NUM_RECORDS} dummy records vào c2c.trades...")

inserted_count = 0
try:
    for i in range(1, NUM_RECORDS + 1):
        dummy_data = generate_dummy_trade(i)
        cursor.execute(insert_query, dummy_data)
        inserted_count += 1
        if i % 5 == 0:
            print(f"   ⏳ Đã insert {i}/{NUM_RECORDS} records...")
    
    conn.commit()
    print(f"\n✅ Đã insert thành công {inserted_count} dummy records!")
    
    # Show statistics
    cursor.execute("""
        SELECT 
            trade_type, 
            COUNT(*) as count, 
            SUM(total_price) as total_volume
        FROM c2c.trades 
        GROUP BY trade_type;
    """)
    
    print(f"\n📊 Thống kê theo loại giao dịch:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} giao dịch, Tổng giá trị: {row[2]:,.2f}")
    
    cursor.execute("""
        SELECT 
            asset, 
            COUNT(*) as count,
            SUM(amount) as total_amount
        FROM c2c.trades 
        GROUP BY asset
        ORDER BY count DESC;
    """)
    
    print(f"\n💰 Thống kê theo tài sản:")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} giao dịch, Tổng: {row[2]:.8f}")
    
    # Total count
    cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
    total_count = cursor.fetchone()[0]
    print(f"\n📈 Tổng số records trong database: {total_count}")
    
except psycopg2.Error as e:
    conn.rollback()
    print(f"❌ Lỗi khi insert data: {e}")
finally:
    cursor.close()
    conn.close()

