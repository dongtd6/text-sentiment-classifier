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

# Set autocommit for ALTER SYSTEM commands
conn.autocommit = True
cursor = conn.cursor()

print("🚀 Đang thiết lập PostgreSQL CDC cho c2c.trades...\n")

# Step 1: Verify c2c schema and table exist
print("📋 Step 1: Kiểm tra c2c schema và table...")
try:
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.schemata 
            WHERE schema_name = 'c2c'
        );
    """)
    schema_exists = cursor.fetchone()[0]
    
    if schema_exists:
        print("   ✅ Schema c2c tồn tại")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'c2c' AND table_name = 'trades'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("   ✅ Table c2c.trades tồn tại")
        else:
            print("   ❌ Table c2c.trades không tồn tại!")
            print("   Chạy: python3 c2c_table_create.py")
            exit(1)
    else:
        print("   ❌ Schema c2c không tồn tại!")
        print("   Chạy: python3 c2c_table_create.py")
        exit(1)
        
except Exception as e:
    print(f"   ❌ Lỗi: {e}")
    exit(1)

# Step 2: Configure PostgreSQL for logical replication
print("\n⚙️  Step 2: Cấu hình PostgreSQL cho logical replication...")
try:
    cursor.execute("ALTER SYSTEM SET wal_level = logical;")
    print("   ✅ wal_level = logical")
    
    cursor.execute("ALTER SYSTEM SET max_replication_slots = 4;")
    print("   ✅ max_replication_slots = 4")
    
    cursor.execute("ALTER SYSTEM SET max_wal_senders = 4;")
    print("   ✅ max_wal_senders = 4")
    
    print("\n   ⚠️  LƯU Ý: Cần RESTART PostgreSQL để áp dụng các thay đổi!")
    print("   Chạy lệnh: kubectl exec -it postgresql-0 -n storage -- pg_ctl restart")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Step 3: Grant replication privileges
print("\n🔐 Step 3: Cấp quyền replication cho pgadmin...")
try:
    cursor.execute("ALTER ROLE pgadmin WITH REPLICATION;")
    print("   ✅ pgadmin đã có quyền REPLICATION")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Step 4: Create publication for c2c.trades
print("\n📢 Step 4: Tạo publication cho Debezium...")
try:
    # Drop existing publication if exists
    cursor.execute("DROP PUBLICATION IF EXISTS c2c_publication;")
    
    # Create new publication for c2c.trades
    cursor.execute("CREATE PUBLICATION c2c_publication FOR TABLE c2c.trades;")
    print("   ✅ Publication 'c2c_publication' đã được tạo cho table c2c.trades")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Verification
print("\n" + "="*70)
print("📊 KIỂM TRA CẤU HÌNH")
print("="*70)

# Check WAL level
print("\n1️⃣  WAL Level:")
try:
    cursor.execute("SHOW wal_level;")
    wal_level = cursor.fetchone()[0]
    if wal_level == 'logical':
        print(f"   ✅ {wal_level}")
    else:
        print(f"   ⚠️  {wal_level} (cần restart PostgreSQL để thành 'logical')")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check replication settings
print("\n2️⃣  Replication Settings:")
try:
    cursor.execute("SHOW max_replication_slots;")
    print(f"   max_replication_slots: {cursor.fetchone()[0]}")
    
    cursor.execute("SHOW max_wal_senders;")
    print(f"   max_wal_senders: {cursor.fetchone()[0]}")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check if pgadmin has replication privilege
print("\n3️⃣  User Privileges:")
try:
    cursor.execute("""
        SELECT rolname, rolreplication 
        FROM pg_roles 
        WHERE rolname = 'pgadmin';
    """)
    role = cursor.fetchone()
    if role and role[1]:
        print(f"   ✅ {role[0]} có quyền REPLICATION")
    else:
        print(f"   ⚠️  {role[0] if role else 'pgadmin'} KHÔNG có quyền REPLICATION")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check publications
print("\n4️⃣  Publications:")
try:
    cursor.execute("""
        SELECT pubname, puballtables 
        FROM pg_publication 
        WHERE pubname = 'c2c_publication';
    """)
    publications = cursor.fetchall()
    if publications:
        for pub in publications:
            print(f"   ✅ {pub[0]} (all_tables: {pub[1]})")
    else:
        print("   ⚠️  Publication 'c2c_publication' không tồn tại")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check publication tables
print("\n5️⃣  Publication Tables:")
try:
    cursor.execute("""
        SELECT schemaname, tablename 
        FROM pg_publication_tables 
        WHERE pubname = 'c2c_publication';
    """)
    tables = cursor.fetchall()
    if tables:
        for table in tables:
            print(f"   ✅ {table[0]}.{table[1]}")
    else:
        print("   ⚠️  Không có table nào trong publication 'c2c_publication'")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check current WAL LSN
print("\n6️⃣  Current WAL LSN:")
try:
    cursor.execute("SELECT pg_current_wal_lsn();")
    lsn = cursor.fetchone()[0]
    print(f"   📍 {lsn}")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check replication slots
print("\n7️⃣  Replication Slots:")
try:
    cursor.execute("""
        SELECT slot_name, slot_type, active, active_pid 
        FROM pg_replication_slots;
    """)
    slots = cursor.fetchall()
    if slots:
        for slot in slots:
            status = "🟢 ACTIVE" if slot[2] else "🔴 INACTIVE"
            print(f"   {status} {slot[0]} (type: {slot[1]}, pid: {slot[3]})")
    else:
        print("   ℹ️  Chưa có replication slot nào (sẽ được tạo khi Debezium kết nối)")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check replication status
print("\n8️⃣  Replication Status:")
try:
    cursor.execute("""
        SELECT application_name, state, sync_state 
        FROM pg_stat_replication;
    """)
    stats = cursor.fetchall()
    if stats:
        for stat in stats:
            print(f"   ✅ {stat[0]} - {stat[1]} ({stat[2]})")
    else:
        print("   ℹ️  Chưa có active replication (chờ Debezium kết nối)")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Check current data in c2c.trades
print("\n9️⃣  Dữ liệu hiện tại trong c2c.trades:")
try:
    cursor.execute("SELECT COUNT(*) FROM c2c.trades;")
    count = cursor.fetchone()[0]
    print(f"   📊 Tổng số records: {count}")
    
    if count > 0:
        cursor.execute("""
            SELECT order_number, trade_type, asset, amount, order_status 
            FROM c2c.trades 
            ORDER BY create_time_ms DESC 
            LIMIT 3;
        """)
        trades = cursor.fetchall()
        print("\n   📝 3 records mới nhất:")
        for trade in trades:
            print(f"      • {trade[0]}: {trade[1]} {trade[3]} {trade[2]} - {trade[4]}")
except Exception as e:
    print(f"   ❌ Lỗi: {e}")

# Close connection
cursor.close()
conn.close()

print("\n" + "="*70)
print("✅ HOÀN TẤT THIẾT LẬP CDC CHO C2C!")
print("="*70)

print("\n📋 BƯỚC TIẾP THEO:")
print("   1. ⚠️  RESTART PostgreSQL:")
print("      kubectl exec -it postgresql-0 -n storage -- pg_ctl restart")
print("\n   2. ✅ Verify wal_level sau khi restart:")
print("      python3 setup_cdc_for_c2c.py")
print("\n   3. 🔌 Tạo Debezium Kafka Connector:")
print("      kubectl apply -f ../strimzi-kafka-operator/c2c-connector.yaml")
print("\n   4. 🧪 Test CDC bằng cách insert dữ liệu mới:")
print("      python3 c2c_insert_dummy.py")
print("\n   5. 📊 Kiểm tra Kafka topic để xem CDC events")

print("\n💡 TIP: Sau khi restart, chạy script này lại để verify wal_level = 'logical'")

