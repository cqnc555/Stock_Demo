import configparser

config = configparser.ConfigParser()

# 读取INI文件
config.read('D:\Stock\THS_9.10.50_20220602\cqnc\StockBlock.ini')

# print(config['BLOCK_STOCK_CONTEXT']['EB'])
# print(config['BLOCK_NAME_MAP_TABLE']['EB'])

eb_split = config['BLOCK_STOCK_CONTEXT']['EB'].split(",")
eb_list = []
for eb in eb_split:
    if eb != None:
        split = eb.split(":")
        if split[0] == '33':
            eb_list.append("0"+split[1])
        elif split[0] == '17':
            eb_list.append("1"+split[1])
        elif split[0] == '-105':
            eb_list.append("2"+split[1])

# 将集合写入文件，每个元素换行
with open("D:\Stock\\TdxDate\\T0002\\blocknew\\ZRSCZT~TCST.blk", "w", encoding="utf-8") as file:
    for item in eb_list:
        file.write(item + "\n")
