import re
import os
import logging
from paddleocr import PaddleOCR
from loguru import logger

# 1. 屏蔽繁琐的 debug 日志 (替代 show_log=False)
logging.getLogger("ppocr").setLevel(logging.WARNING)

# 2. 初始化模型
# 注意：v2.9+ 版本使用 use_textline_orientation=True 替代了 use_angle_cls=True
# 这一步已经开启了方向分类器
# ocr = PaddleOCR(use_textline_orientation=True, lang="ch")

# ✅ 修改后：增加 det_limit_side_len 参数
ocr = PaddleOCR(
    use_textline_orientation=True,
    lang="ch",
    det_limit_side_len=7000  # 设置为 7000 (大于你的 6323 即可)
)


def parse_stock_image(image_path):
    if not os.path.exists(image_path):
        logger.error(f"找不到图片: {image_path}")
        return

    logger.info(f"开始识别图片: {image_path} ...")

    try:
        # 3. 执行 OCR 识别
        # ★★★ 关键修改：不要传 cls=True，直接传路径 ★★★
        result = ocr.ocr(image_path)
    except Exception as e:
        logger.error(f"OCR 识别内部错误: {e}")
        return

    # 4. 解析结果
    # 新版 PaddleOCR 有时候返回结构可能有细微变化，增加一个非空判断
    if not result or not result[0]:
        logger.warning("未识别到任何文字内容")
        return {}

    # 提取所有的文本行
    # 结构通常是: [ [ [坐标], [文本, 置信度] ], ... ]
    try:
        lines = [line[1][0] for line in result[0] if line and line[1]]
    except Exception as e:
        logger.error(f"解析结果结构失败: {e} | 原始数据: {result[0][:1]}")
        return {}

    # 5. 结构化解析数据
    structured_data = {}
    current_sector = None

    sector_pattern = re.compile(r"【(.*?)】")
    stock_code_pattern = re.compile(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4})\b")

    logger.info("正在分析文本结构...")

    for text in lines:
        # A. 检查是否是板块标题
        sector_match = sector_pattern.search(text)
        if sector_match:
            sector_name = sector_match.group(1)
            current_sector = sector_name
            if current_sector not in structured_data:
                structured_data[current_sector] = []
            logger.info(f"发现板块: {current_sector}")
            continue

        # B. 检查是否包含股票代码
        if current_sector:
            codes = stock_code_pattern.findall(text)
            for code in codes:
                if code not in structured_data[current_sector]:
                    structured_data[current_sector].append(code)
                    logger.success(f"  -> 提取到股票: {code} (所属: {current_sector})")

    return structured_data


if __name__ == "__main__":
    img_path = "1.png"  # 确保这里文件名正确

    data = parse_stock_image(img_path)

    if data:
        print("\n====== 最终解析结果 ======")
        for sector, stocks in data.items():
            print(f"板块【{sector}】: {stocks}")