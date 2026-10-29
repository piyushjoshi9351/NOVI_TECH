from dotenv import load_dotenv
import os
import pymysql

load_dotenv("backend/.env")

conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

cur = conn.cursor()

for table in ["careers", "universities", "university_matches"]:
    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
    print(f"{table}: {cur.fetchone()[0]} rows")

conn.close()
