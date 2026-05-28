import json
import pandas as pd
import sys
from datetime import datetime

def convert_value(val):
    """
    转换值为JSON可序列化格式
    """
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, float) and val == int(val):
        return int(val)
    return val

def convert_excel_to_json(excel_path, json_path):
    """
    将Excel文件转换为JSON格式，保持与dispatch_scheme_data_base.json相同的结构
    
    Args:
        excel_path: Excel文件路径
        json_path: 输出JSON文件路径
    """
    try:
        # 读取Excel文件
        df = pd.read_excel(excel_path, sheet_name=0, header=None)
        
        # 获取行数和列数
        row_count, column_count = df.shape
        
        # 定义标准列名（与dispatch_scheme_data_base.json保持一致）
        standard_columns = [
            "时间",
            "三门峡",
            "三门峡.1",
            "三门峡.2",
            "三门峡.3",
            "小浪底",
            "小浪底.1",
            "小浪底.2",
            "小浪底.3",
            "陆浑",
            "陆浑.1",
            "陆浑.2",
            "陆浑.3",
            "故县",
            "故县.1",
            "故县.2",
            "故县.3",
            "河口村",
            "河口村.1",
            "河口村.2",
            "河口村.3",
            "龙门镇",
            "白马寺",
            "黑石关",
            "花园口"
        ]
        
        # 使用标准列名
        columns = standard_columns[:column_count]
        
        # 提取数据行
        data = []
        for row in range(1, row_count):
            row_data = {}
            has_data = False
            for col in range(column_count):
                if col < len(columns):
                    val = df.iloc[row, col]
                    converted_val = convert_value(val)
                    if converted_val is not None:
                        row_data[columns[col]] = converted_val
                        has_data = True
            if has_data:
                data.append(row_data)
        
        # 创建输出结构
        output = {
            "sheet_name": "Sheet1",
            "row_count": row_count,
            "column_count": column_count,
            "columns": columns,
            "data": data
        }
        
        # 写入JSON文件
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"成功转换！")
        print(f"行数: {row_count}")
        print(f"列数: {column_count}")
        print(f"列名: {columns}")
        print(f"数据行数: {len(data)}")
        
        return True
    except Exception as e:
        print(f"转换失败: {str(e)}")
        return False

if __name__ == "__main__":
    excel_path = "/mnt/d/workspace/Flood-Control-Four-Pre-System/mcp-servers/data/2021秋汛方案单1002-提胡光亮.xlsx"
    json_path = "/mnt/d/workspace/Flood-Control-Four-Pre-System/mcp-servers/data/dispatch_scheme_data_base.json"
    
    print(f"正在将 Excel 文件转换为 JSON...")
    print(f"源文件: {excel_path}")
    print(f"目标文件: {json_path}")
    print()
    
    success = convert_excel_to_json(excel_path, json_path)
    
    if success:
        print("\n转换成功！")
    else:
        print("\n转换失败！")
        sys.exit(1)