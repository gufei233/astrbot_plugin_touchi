import os
import random
import math
import aiosqlite
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from astrbot.api import logger

# 定义路径
script_dir = os.path.dirname(os.path.abspath(__file__))
items_dir = os.path.join(script_dir, "items")
output_dir = os.path.join(script_dir, "output")
os.makedirs(output_dir, exist_ok=True)

# 定义颜色常量
BACKGROUND_COLOR = (40, 40, 45)  # 深灰背景色
GRID_LINE_COLOR = (80, 80, 85)    # 网格线颜色
GRID_TEXT_COLOR = (180, 180, 180) # 网格文字颜色
ITEM_BORDER_COLOR = (100, 100, 110) # 物品边框颜色

# 定义物品背景色（带透明度）
background_colors = {
    "purple": (50, 43, 97, 80), 
    "blue": (49, 91, 126, 80), 
    "gold": (153, 116, 22, 80), 
    "red": (139, 35, 35, 80)
}

# 定义等级优先级
LEVEL_PRIORITY = {
    "red": 4,     # 最高级
    "gold": 3,
    "purple": 2,
    "blue": 1,
    "green": 0     # 最低级
}

# 只显示这些等级的物品
DISPLAY_LEVELS = {"red", "gold"}

# --- Helper Functions ---

def get_size(size_str):
    if 'x' in size_str:
        parts = size_str.split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return 1, 1

def place_items(items):
    """
    计算所需网格大小并放置物品
    返回: (放置的物品列表, 网格宽度, 网格高度)
    """
    # 计算总占用面积
    total_area = sum(item["grid_width"] * item["grid_height"] for item in items)
    
    # 计算初始网格大小 (正方形)
    grid_size = max(5, math.ceil(math.sqrt(total_area * 1.5)))
    
    # 尝试放置物品，如果放不下则增加网格大小
    while True:
        grid = [[0] * grid_size for _ in range(grid_size)]
        placed = []
        
        # 按等级优先级从高到低排序，相同等级再按面积从大到小排序
        sorted_items = sorted(
            items,
            key=lambda x: (LEVEL_PRIORITY.get(x["level"], 0), x["grid_width"] * x["grid_height"]),
            reverse=True
        )
        
        # 尝试放置每个物品
        for item in sorted_items:
            orientations = [(item["grid_width"], item["grid_height"], False)]
            if item["grid_width"] != item["grid_height"]:
                orientations.append((item["grid_height"], item["grid_width"], True))
            
            placed_successfully = False
            
            # 尝试每个方向
            for width, height, rotated in orientations:
                if placed_successfully:
                    break
                    
                # 按顺序遍历网格位置
                for y in range(grid_size - height + 1):
                    if placed_successfully:
                        break
                    for x in range(grid_size - width + 1):
                        # 检查位置是否可用
                        can_place = True
                        for i in range(height):
                            for j in range(width):
                                if grid[y+i][x+j] != 0:
                                    can_place = False
                                    break
                            if not can_place:
                                break
                        
                        # 如果位置可用，放置物品
                        if can_place:
                            for i in range(height):
                                for j in range(width):
                                    grid[y+i][x+j] = 1
                            
                            placed.append({
                                "item": item,
                                "x": x,
                                "y": y,
                                "width": width,
                                "height": height,
                                "rotated": rotated
                            })
                            placed_successfully = True
                            break
        
        # 检查是否所有物品都已放置
        if len(placed) == len(items):
            return placed, grid_size, grid_size
        
        # 如果放不下，增加网格大小
        grid_size += 1

def render_tujian_image(placed_items, grid_width, grid_height, cell_size=100):
    # 计算图片大小 (移除文字区域后减小高度)
    img_width = grid_width * cell_size + 100  # 保留边距
    img_height = grid_height * cell_size + 50  # 减小高度
    
    # 创建图片
    tujian_img = Image.new("RGB", (img_width, img_height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(tujian_img)
    
    # 计算网格起始位置 (居中)
    grid_start_x = (img_width - grid_width * cell_size) // 2
    grid_start_y = 20  # 上移起始位置
    
    # 绘制网格线
    for i in range(grid_width + 1):
        x = grid_start_x + i * cell_size
        draw.line([(x, grid_start_y), (x, grid_start_y + grid_height * cell_size)], 
                  fill=GRID_LINE_COLOR, width=1)
    
    for i in range(grid_height + 1):
        y = grid_start_y + i * cell_size
        draw.line([(grid_start_x, y), (grid_start_x + grid_width * cell_size, y)], 
                  fill=GRID_LINE_COLOR, width=1)
    
    # 绘制每个物品
    for placed in placed_items:
        item = placed["item"]
        x0 = grid_start_x + placed["x"] * cell_size
        y0 = grid_start_y + placed["y"] * cell_size
        x1 = x0 + placed["width"] * cell_size
        y1 = y0 + placed["height"] * cell_size
        
        # 获取背景色
        bg_color = background_colors.get(item["level"], (128, 128, 128, 80))
        
        # 创建半透明层
        overlay = Image.new('RGBA', (placed["width"] * cell_size, placed["height"] * cell_size), bg_color)
        
        # 将半透明层粘贴到主图像上
        tujian_img.paste(overlay, (x0, y0), overlay)
        
        # 绘制物品边框
        draw.rectangle([x0, y0, x1, y1], outline=ITEM_BORDER_COLOR, width=1)
        
        # 添加物品图片
        try:
            with Image.open(item["path"]).convert("RGBA") as item_img:
                if placed["rotated"]:
                    item_img = item_img.rotate(90, expand=True)
                
                # 缩放图片以适应格子
                max_width = placed["width"] * cell_size - 20
                max_height = placed["height"] * cell_size - 20
                item_img.thumbnail((max_width, max_height), Image.LANCZOS)
                
                # 居中放置图片
                paste_x = x0 + (placed["width"] * cell_size - item_img.width) // 2
                paste_y = y0 + (placed["height"] * cell_size - item_img.height) // 2
                tujian_img.paste(item_img, (paste_x, paste_y), item_img)
        except Exception as e:
            logger.error(f"图鉴渲染：无法加载物品图片 {item['path']}, 错误: {e}")
            
            # 绘制错误占位符
            cross_size = min(placed["width"], placed["height"]) * cell_size // 3
            center_x = x0 + placed["width"] * cell_size // 2
            center_y = y0 + placed["height"] * cell_size // 2
            draw.line([(center_x-cross_size, center_y-cross_size),
                      (center_x+cross_size, center_y+cross_size)],
                     fill=(255, 50, 50), width=3)
            draw.line([(center_x-cross_size, center_y+cross_size),
                      (center_x+cross_size, center_y-cross_size)],
                     fill=(255, 50, 50), width=3)
    
    return tujian_img

# --- Main Class ---

class TujianTools:
    def __init__(self, db_path):
        self.db_path = db_path
        self.all_items = self._load_all_item_definitions()

    def _load_all_item_definitions(self):
        items = []
        valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
        if not os.path.exists(items_dir):
            logger.error("图鉴工具：items 文件夹不存在！")
            return []
        
        for filename in os.listdir(items_dir):
            file_path = os.path.join(items_dir, filename)
            if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in valid_extensions):
                item_name = os.path.splitext(filename)[0]
                parts = item_name.split('_')
                
                if len(parts) >= 2:
                    level = parts[0].lower()
                    size_str = parts[1]
                else:
                    level = "purple"
                    size_str = "1x1"
                
                width, height = get_size(size_str)
                items.append({
                    "path": file_path,
                    "name": item_name,
                    "level": level,
                    "size": size_str,
                    "grid_width": width,
                    "grid_height": height
                })
        return items

    async def generate_tujian(self, user_id: str):
        if not self.db_path:
            return "数据库路径未配置，无法查询图鉴。"
        
        records = []
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT DISTINCT item_name FROM user_touchi_collection WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    records = await cursor.fetchall()
        except Exception as e:
            logger.error(f"查询用户 {user_id} 图鉴时出错: {e}")
            return "查询图鉴时数据库出错。"

        if not records:
            return "您还没有收集到任何物品！"

        user_item_names = {rec[0] for rec in records}
        
        # 只加载金色和红色的物品
        user_items_to_render = [
            item for item in self.all_items 
            if item["name"] in user_item_names and item["level"] in DISPLAY_LEVELS
        ]

        if not user_items_to_render:
            return "您还没有收集到金色或红色品质的物品！"
        
        # 放置物品并获取网格大小
        placed_items, grid_width, grid_height = place_items(user_items_to_render)
        
        if not placed_items:
            return "生成图鉴图片时发生布局错误。"

        # 渲染图鉴图片
        tujian_image = render_tujian_image(placed_items, grid_width, grid_height, cell_size=100)

        # 保存图片
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f"tujian_{user_id}_{timestamp}.png")
        tujian_image.save(output_path)
        
        logger.info(f"成功为用户 {user_id} 生成图鉴: {output_path}")

        return output_path
