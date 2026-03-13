import pymysql
import pymysql.cursors
import json
import os
from flask import Flask, render_template, request, g

app = Flask(__name__)

# --- MySQL 数据库配置 ---
DB_CONFIG = {
    'host': '192.168.1.65',
    'user': 'root',
    'password': '',
    'database': 'stock_data',  # 确保你已经在 MySQL 中创建了此数据库
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,  # 返回字典格式，类似 sqlite3.Row
}


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = pymysql.connect(**DB_CONFIG)
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with db.cursor() as cursor:
            # 1. 日期主表 (只存日期) - MySQL主键推荐用 VARCHAR
            cursor.execute('CREATE TABLE IF NOT EXISTS daily_meta (date VARCHAR(20) PRIMARY KEY)')

            # 2. 情绪配置表 (存指标名、顺序)
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS mood_config (name VARCHAR(100) PRIMARY KEY, rank INTEGER DEFAULT 0, is_visible INTEGER DEFAULT 1)')

            # 3. 情绪数据表
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS mood_data (date VARCHAR(20), name VARCHAR(100), content TEXT, PRIMARY KEY (date, name))')

            # 4. 板块配置表
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS sector_config (name VARCHAR(100) PRIMARY KEY, rank INTEGER DEFAULT 0, is_visible INTEGER DEFAULT 1)')

            # 5. 板块数据表
            cursor.execute(
                'CREATE TABLE IF NOT EXISTS sector_data (date VARCHAR(20), name VARCHAR(100), content TEXT, PRIMARY KEY (date, name))')

            # --- 初始化默认情绪指标 ---
            defaults = ['🚀 市场最高标', '💔 断板反馈', '🐉 核心龙头']
            for idx, name in enumerate(defaults):
                # MySQL 使用 INSERT IGNORE，占位符使用 %s
                cursor.execute('INSERT IGNORE INTO mood_config (name, rank, is_visible) VALUES (%s, %s, 1)',
                               (name, idx))

        db.commit()


@app.route('/')
def index():
    # 获取前端传来的查询参数
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    db = get_db()
    data_map = {}

    with db.cursor() as cursor:
        # 1. 获取日期：根据是否有传参决定查询范围
        if start_date and end_date:
            # 自定义区间查询
            cursor.execute('SELECT date FROM daily_meta WHERE date >= %s AND date <= %s ORDER BY date DESC',
                           (start_date, end_date))
            dates = [row['date'] for row in cursor.fetchall()]
        else:
            # 默认查询最近15天
            cursor.execute('SELECT date FROM daily_meta ORDER BY date DESC LIMIT 15')
            dates = [row['date'] for row in cursor.fetchall()]

        # --- 获取情绪行 (Moods) ---
        cursor.execute('SELECT name FROM mood_config WHERE is_visible = 1 ORDER BY rank ASC, name ASC')
        moods = [row['name'] for row in cursor.fetchall()]

        cursor.execute('SELECT name FROM mood_config WHERE is_visible = 0 ORDER BY rank ASC')
        hidden_moods = [row['name'] for row in cursor.fetchall()]

        # --- 获取板块行 (Sectors) ---
        cursor.execute('SELECT name FROM sector_config WHERE is_visible = 1 ORDER BY rank ASC, name ASC')
        sectors = [row['name'] for row in cursor.fetchall()]

        cursor.execute('SELECT name FROM sector_config WHERE is_visible = 0 ORDER BY rank ASC')
        hidden_sectors = [row['name'] for row in cursor.fetchall()]

        # --- 获取所有数据内容 ---
        # 优化：只获取当前展示日期范围内的数据，提升查询性能
        if dates:
            placeholders = ', '.join(['%s'] * len(dates))

            # 读取情绪数据
            cursor.execute(f'SELECT * FROM mood_data WHERE date IN ({placeholders})', dates)
            for row in cursor.fetchall():
                data_map[(row['date'], row['name'])] = row['content']

            # 读取板块数据
            cursor.execute(f'SELECT * FROM sector_data WHERE date IN ({placeholders})', dates)
            for row in cursor.fetchall():
                data_map[(row['date'], row['name'])] = row['content']

    return render_template('index.html',
                           dates=dates,
                           moods=moods, hidden_moods=hidden_moods,
                           sectors=sectors, hidden_sectors=hidden_sectors,
                           data_map=data_map,
                           current_start=start_date or '',
                           current_end=end_date or '')


# --- 通用：添加行 (type=mood 或 sector) ---
@app.route('/add_item', methods=['POST'])
def add_item():
    name = request.form['name']
    item_type = request.form['type']
    table = 'mood_config' if item_type == 'mood' else 'sector_config'

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(f'INSERT IGNORE INTO {table} (name, rank, is_visible) VALUES (%s, 0, 1)', (name,))
        cursor.execute(f'UPDATE {table} SET is_visible = 1 WHERE name = %s', (name,))
    db.commit()
    return {'status': 'success'}


# --- 通用：排序 ---
@app.route('/reorder_items', methods=['POST'])
def reorder_items():
    new_order = request.json.get('order', [])
    item_type = request.json.get('type')
    table = 'mood_config' if item_type == 'mood' else 'sector_config'

    db = get_db()
    with db.cursor() as cursor:
        for index, name in enumerate(new_order):
            cursor.execute(f'UPDATE {table} SET rank = %s WHERE name = %s', (index, name))
    db.commit()
    return {'status': 'success'}


# --- 通用：切换显隐 ---
@app.route('/toggle_item', methods=['POST'])
def toggle_item():
    name = request.json.get('name')
    visible = request.json.get('visible')
    item_type = request.json.get('type')
    table = 'mood_config' if item_type == 'mood' else 'sector_config'

    db = get_db()
    with db.cursor() as cursor:
        cursor.execute(f'UPDATE {table} SET is_visible = %s WHERE name = %s', (visible, name))
    db.commit()
    return {'status': 'success'}


# --- 通用：更新单元格内容 ---
@app.route('/update_cell', methods=['POST'])
def update_cell():
    data = request.json
    date = data.get('date')
    key = data.get('key')
    val = data.get('value')
    item_type = data.get('type')

    table = 'mood_data' if item_type == 'mood' else 'sector_data'
    db = get_db()

    # MySQL 的 UPSERT 语法: ON DUPLICATE KEY UPDATE
    sql = f"INSERT INTO {table} (date, name, content) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE content=VALUES(content)"
    with db.cursor() as cursor:
        cursor.execute(sql, (date, key, val))
    db.commit()
    return {'status': 'success'}


# --- 日期操作 ---
@app.route('/add_date', methods=['POST'])
def add_date():
    date = request.form['date']
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('INSERT IGNORE INTO daily_meta (date) VALUES (%s)', (date,))
    db.commit()
    return {'status': 'success'}


@app.route('/delete_date/<date>')
def delete_date(date):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute('DELETE FROM daily_meta WHERE date = %s', (date,))
        cursor.execute('DELETE FROM mood_data WHERE date = %s', (date,))
        cursor.execute('DELETE FROM sector_data WHERE date = %s', (date,))
    db.commit()
    return {'status': 'success'}


if __name__ == '__main__':
    # 因为不是本地文件了，去掉 os.path.exists 判断，每次启动直接执行建表检查（IF NOT EXISTS 会确保安全）
    init_db()
    app.run(host="0.0.0.0", debug=True, port=88)