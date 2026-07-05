import psycopg2

url_6543 = "postgresql://postgres.tomlgkdoxygxmmmhgsct:Iroman%40897846@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

print("\n--- Testing port 6543 ---")
try:
    conn = psycopg2.connect(url_6543)
    print("SUCCESS on 6543!")
    conn.close()
except Exception as e:
    print(f"FAILED on 6543: {e}")
