import sqlite3
import json
import os
from flask import Flask, render_template, request, g

app = Flask(__name__)
DATABASE = 'stock_data.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()

        # 1. 日期主表 (只存日期)
        db.execute('CREATE TABLE IF NOT EXISTS daily_meta (date TEXT PRIMARY KEY)')

        # 2. 情绪配置表 (存指标名、顺序)
        db.execute(
            'CREATE TABLE IF NOT EXISTS mood_config (name TEXT PRIMARY KEY, rank INTEGER DEFAULT 0, is_visible INTEGER DEFAULT 1)')

        # 3. 情绪数据表
        db.execute(
            'CREATE TABLE IF NOT EXISTS mood_data (date TEXT, name TEXT, content TEXT, PRIMARY KEY (date, name))')

        # 4. 板块配置表
        db.execute(
            'CREATE TABLE IF NOT EXISTS sector_config (name TEXT PRIMARY KEY, rank INTEGER DEFAULT 0, is_visible INTEGER DEFAULT 1)')

        # 5. 板块数据表
        db.execute(
            'CREATE TABLE IF NOT EXISTS sector_data (date TEXT, name TEXT, content TEXT, PRIMARY KEY (date, name))')

        # --- 初始化默认情绪指标 ---
        defaults = ['🚀 市场最高标', '💔 断板反馈', '🐉 核心龙头']
        for idx, name in enumerate(defaults):
            db.execute('INSERT OR IGNORE INTO mood_config (name, rank, is_visible) VALUES (?, ?, 1)', (name, idx))

        db.commit()


@app.route('/')
def index():
    db = get_db()

    # 获取日期
    cur = db.execute('SELECT date FROM daily_meta ORDER BY date DESC')
    dates = [row['date'] for row in cur.fetchall()]

    # --- 获取情绪行 (Moods) ---
    cur = db.execute('SELECT name FROM mood_config WHERE is_visible = 1 ORDER BY rank ASC, rowid ASC')
    moods = [row['name'] for row in cur.fetchall()]

    cur = db.execute('SELECT name FROM mood_config WHERE is_visible = 0 ORDER BY rank ASC')
    hidden_moods = [row['name'] for row in cur.fetchall()]

    # --- 获取板块行 (Sectors) ---
    cur = db.execute('SELECT name FROM sector_config WHERE is_visible = 1 ORDER BY rank ASC, rowid ASC')
    sectors = [row['name'] for row in cur.fetchall()]

    cur = db.execute('SELECT name FROM sector_config WHERE is_visible = 0 ORDER BY rank ASC')
    hidden_sectors = [row['name'] for row in cur.fetchall()]

    # --- 获取所有数据内容 ---
    # 统一拼装成 map: key=(date, name), value=content
    data_map = {}

    # 读取情绪数据
    cur = db.execute('SELECT * FROM mood_data')
    for row in cur.fetchall():
        data_map[(row['date'], row['name'])] = row['content']

    # 读取板块数据
    cur = db.execute('SELECT * FROM sector_data')
    for row in cur.fetchall():
        data_map[(row['date'], row['name'])] = row['content']

    return render_template('index.html',
                           dates=dates,
                           moods=moods, hidden_moods=hidden_moods,
                           sectors=sectors, hidden_sectors=hidden_sectors,
                           data_map=data_map)


# --- 通用：添加行 (type=mood 或 sector) ---
@app.route('/add_item', methods=['POST'])
def add_item():
    name = request.form['name']
    item_type = request.form['type']  # 'mood' or 'sector'
    table = 'mood_config' if item_type == 'mood' else 'sector_config'

    db = get_db()
    # 插入或更新为可见
    db.execute(f'INSERT OR IGNORE INTO {table} (name, rank, is_visible) VALUES (?, 0, 1)', (name,))
    db.execute(f'UPDATE {table} SET is_visible = 1 WHERE name = ?', (name,))
    db.commit()
    return {'status': 'success'}


# --- 通用：排序 ---
@app.route('/reorder_items', methods=['POST'])
def reorder_items():
    new_order = request.json.get('order', [])
    item_type = request.json.get('type')
    table = 'mood_config' if item_type == 'mood' else 'sector_config'

    db = get_db()
    for index, name in enumerate(new_order):
        db.execute(f'UPDATE {table} SET rank = ? WHERE name = ?', (index, name))
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
    db.execute(f'UPDATE {table} SET is_visible = ? WHERE name = ?', (visible, name))
    db.commit()
    return {'status': 'success'}


# --- 通用：更新单元格内容 ---
@app.route('/update_cell', methods=['POST'])
def update_cell():
    data = request.json
    date = data.get('date')
    key = data.get('key')  # 指标名 或 板块名
    val = data.get('value')
    item_type = data.get('type')  # 'mood' or 'sector'

    table = 'mood_data' if item_type == 'mood' else 'sector_data'

    db = get_db()
    sql = f"INSERT INTO {table} (date, name, content) VALUES (?, ?, ?) ON CONFLICT(date, name) DO UPDATE SET content=excluded.content"
    db.execute(sql, (date, key, val))
    db.commit()
    return {'status': 'success'}


# --- 日期操作 ---
@app.route('/add_date', methods=['POST'])
def add_date():
    date = request.form['date']
    get_db().execute('INSERT OR IGNORE INTO daily_meta (date) VALUES (?)', (date,)).connection.commit()
    return {'status': 'success'}


@app.route('/delete_date/<date>')
def delete_date(date):
    db = get_db()
    db.execute('DELETE FROM daily_meta WHERE date = ?', (date,))
    db.execute('DELETE FROM mood_data WHERE date = ?', (date,))
    db.execute('DELETE FROM sector_data WHERE date = ?', (date,))
    db.commit()
    return {'status': 'success'}


if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host="0.0.0.0",debug=True, port=88)