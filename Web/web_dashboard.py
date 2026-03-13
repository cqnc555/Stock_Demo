from flask import Flask, render_template, jsonify
import requests
import time
import datetime

app = Flask(__name__)


# --- 核心逻辑 ---

def calculate_limit_price(code, name, prev_close):
    if prev_close is None or prev_close == 0: return 0
    limit_ratio = 0.10
    if code.startswith('688') or code.startswith('300'):
        limit_ratio = 0.20
    elif code.startswith('8') or code.startswith('4'):
        limit_ratio = 0.30
    if 'ST' in name or 'st' in name: limit_ratio = 0.05
    return float(int((prev_close * (1 + limit_ratio) * 100) + 0.5) / 100)


def fetch_em_data(sort_field, sort_type, page_size=20):
    """
    通用请求函数
    sort_field: 排序字段 (f22=涨速, f3=涨幅)
    sort_type: 1=降序, 0=升序
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "http://82.push2.eastmoney.com/api/qt/clist/get"
    # f100 是所属行业板块
    fields = "f12,f14,f2,f3,f15,f18,f22,f100"
    params = {
        "pn": "1", "pz": str(page_size), "po": str(sort_type), "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2", "invt": "2", "fid": sort_field,
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": fields,
        "_": str(int(time.time() * 1000))
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=2)
        data = resp.json()
        if data and 'data' in data and 'diff' in data['data']:
            return data['data']['diff']
    except Exception as e:
        print(f"Err: {e}")
    return []


# --- 功能1：炸板监控 (复用逻辑) ---
def get_zhaban_data():
    # 既然要全市场扫，我们这里还是用f3(涨幅)排序拉5000只，在内存里筛
    # 为了效率，我们只拉涨幅前300名，通常炸板都在这里面
    raw_list = fetch_em_data(sort_field="f3", sort_type=1, page_size=300)
    result = []

    for item in raw_list:
        try:
            code = item.get('f12')
            name = item.get('f14')
            curr = float(item.get('f2', 0))
            high = float(item.get('f15', 0))
            prev = float(item.get('f18', 0))
            industry = item.get('f100', '-')  # 板块

            if curr == 0: continue
            limit_price = calculate_limit_price(code, name, prev)

            # 炸板逻辑
            if high >= (limit_price - 0.01) and curr < high:
                drop_pct = round((curr - high) / high * 100, 2)
                curr_pct = round((curr - prev) / prev * 100, 2)

                result.append({
                    "code": code, "name": name, "price": curr,
                    "pct": curr_pct, "drop": drop_pct,
                    "industry": industry,
                    "time": datetime.datetime.now().strftime("%H:%M:%S")
                })
        except:
            continue

    result.sort(key=lambda x: x['drop'], reverse=True)
    return result


# --- 功能2：直线拉升榜 (Rocket) ---
def get_rocket_data():
    # f22 是 5分钟涨速
    raw_list = fetch_em_data(sort_field="f22", sort_type=1, page_size=15)
    result = []
    for item in raw_list:
        try:
            curr_pct = float(item.get('f3', 0))
            speed = float(item.get('f22', 0))

            # 过滤：涨幅已经超过9%的（可能要板了）或者涨幅小于0的（下跌中反抽）我们不看
            # 专看 1% < 涨幅 < 8% 的票，且涨速快，这是最佳半路点
            if 1 < curr_pct < 8.5:
                result.append({
                    "code": item.get('f12'),
                    "name": item.get('f14'),
                    "price": item.get('f2'),
                    "pct": curr_pct,
                    "speed": speed,  # 5分钟涨速
                    "industry": item.get('f100', '-')
                })
        except:
            continue
    return result


# --- 路由 ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    return jsonify({
        "zhaban": get_zhaban_data(),
        "rocket": get_rocket_data()
    })


if __name__ == '__main__':
    app.run(debug=True, port=81)