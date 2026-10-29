from dotenv import load_dotenv
import os
import pymysql
import sqlparse

load_dotenv("backend/.env")

files = ["careers.sql", "universities.sql", "university_matches.sql"]

conn = pymysql.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl={"ssl": True},
    autocommit=False
)

try:
    with conn.cursor() as cur:
        cur.execute("SET NAMES utf8mb4")
        cur.execute("SET FOREIGN_KEY_CHECKS=0")

        for filename in files:
            print(f"\nImporting {filename}...")

            with open(filename, "r", encoding="utf-8-sig") as f:
                sql = f.read()

            statements = sqlparse.split(sql)

            for statement in statements:
                statement = statement.strip()
                if statement:
                    cur.execute(statement)

            conn.commit()
            print(f"SUCCESS: {filename}")

        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()

        for table in ["careers", "universities", "university_matches"]:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            print(f"{table}: {cur.fetchone()[0]} rows")

except Exception as e:
    conn.rollback()
    print(f"\nIMPORT FAILED: {e}")
    raise

finally:
    conn.close()