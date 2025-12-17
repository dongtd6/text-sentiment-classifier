import psycopg2
from datetime import datetime
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

# Create dummy data
dummy_data = {
    'order_number': 'ORD-20251217-001',
    'adv_no': 'ADV-12345',
    'trade_type': 'BUY',
    'asset': 'BTC',
    'fiat': 'VND',
    'fiat_symbol': '₫',
    'amount': 0.00123456,
    'total_price': 1250000.00,
    'unit_price': 1015854471.54,
    'order_status': 'COMPLETED',
    'create_time_ms': int(datetime.now().timestamp() * 1000),
    'commission': 1250.00,
    'counter_part_nick_name': 'TraderVN123',
    'advertisement_role': 'SELLER'
}

# Insert dummy row
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
ON CONFLICT (order_number) DO UPDATE SET
    order_status = EXCLUDED.order_status;
"""

try:
    cursor.execute(insert_query, dummy_data)
    conn.commit()
    print("✅ Dummy data đã được insert thành công!")
    print(f"\n📊 Chi tiết:")
    print(f"   Order Number: {dummy_data['order_number']}")
    print(f"   Trade Type: {dummy_data['trade_type']}")
    print(f"   Asset: {dummy_data['asset']}")
    print(f"   Amount: {dummy_data['amount']} {dummy_data['asset']}")
    print(f"   Total Price: {dummy_data['total_price']:,.0f} {dummy_data['fiat']}")
    print(f"   Status: {dummy_data['order_status']}")
    
    # Verify insertion
    cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
    count = cursor.fetchone()[0]
    print(f"\n📈 Tổng số records trong c2c.trades: {count}")
    
    # Show the inserted row
    cursor.execute("SELECT * FROM c2c.trades WHERE order_number = %s;", (dummy_data['order_number'],))
    row = cursor.fetchone()
    if row:
        print(f"\n✅ Xác nhận dữ liệu đã được lưu:")
        print(f"   {row}")
    
except psycopg2.Error as e:
    conn.rollback()
    print(f"❌ Lỗi khi insert data: {e}")
finally:
    cursor.close()
    conn.close()

