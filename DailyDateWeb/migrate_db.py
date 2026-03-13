import sqlite3
import pymysql

# 1. 连接旧的 SQLite 数据库
sqlite_file = 'stock_data.db'
print(f"正在连接 SQLite 数据库: {sqlite_file}...")
try:
    sqlite_conn = sqlite3.connect(sqlite_file)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
except Exception as e:
    print(f"无法连接 SQLite: {e}")
    exit(1)

# 2. 连接新的 MySQL 数据库
print("正在连接 MySQL 数据库 (192.168.1.65)...")
try:
    mysql_conn = pymysql.connect(
        host='192.168.1.65',
        user='root',
        password='',
        database='stock_data',
        charset='utf8mb4'
    )
    mysql_cursor = mysql_conn.cursor()
except Exception as e:
    print(f"无法连接 MySQL: {e}")
    exit(1)

# 3. 定义需要迁移的表和对应的插入 SQL
tables = {
    'daily_meta': "INSERT IGNORE INTO daily_meta (date) VALUES (%s)",

    'mood_config': "INSERT IGNORE INTO mood_config (name, rank, is_visible) VALUES (%s, %s, %s)",

    'mood_data': "INSERT IGNORE INTO mood_data (date, name, content) VALUES (%s, %s, %s)",

    'sector_config': "INSERT IGNORE INTO sector_config (name, rank, is_visible) VALUES (%s, %s, %s)",

    'sector_data': "INSERT IGNORE INTO sector_data (date, name, content) VALUES (%s, %s, %s)"
}

# 4. 开始逐表抽取并插入
for table_name, insert_sql in tables.items():
    print(f"--> 正在迁移表: {table_name} ...", end=" ")

    # 从 SQLite 读取
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print("跳过 (空表)")
        continue

    # 写入 MySQL
    insert_count = 0
    for row in rows:
        # row 是类似字典的对象，我们把它转成 tuple 传给 MySQL
        values = tuple(row[key] for key in row.keys())
        try:
            mysql_cursor.execute(insert_sql, values)
            insert_count += 1
        except Exception as e:
            print(f"\n插入数据出错 {values}: {e}")

    print(f"成功迁移 {insert_count} 条数据")

# 5. 提交并关闭连接
mysql_conn.commit()
sqlite_conn.close()
mysql_conn.close()

print("\n🎉 全部数据迁移完成！你现在可以启动最新的 app.py 使用 MySQL 了。")