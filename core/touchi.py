import os
import random
from PIL import Image, ImageDraw
from datetime import datetime
import glob

script_dir = os.path.dirname(os.path.abspath(__file__))
items_dir = os.path.join(script_dir, "items")
expressions_dir = os.path.join(script_dir, "expressions")
output_dir = os.path.join(script_dir, "output")

os.makedirs(items_dir, exist_ok=True)
os.makedirs(expressions_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

def get_size(size_str):
    if 'x' in size_str:
        parts = size_str.split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return 1, 1

def load_items():
    items = []
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    for filename in os.listdir(items_dir):
        file_path = os.path.join(items_dir, filename)
        if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in valid_extensions):
            parts = os.path.splitext(filename)[0].split('_')
            level = parts[0] if len(parts) >= 2 else "purple"
            size = parts[1] if len(parts) >= 2 else "1x1"
            width, height = get_size(size)
            items.append({
                "path": file_path, "level": level.lower(), "size": size,
                "grid_width": width, "grid_height": height
            })
    return items

def load_expressions():
    expressions = {}
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    for filename in os.listdir(expressions_dir):
        file_path = os.path.join(expressions_dir, filename)
        if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in valid_extensions):
            expressions[os.path.splitext(filename)[0]] = file_path
    return expressions

def place_items(items, grid_width, grid_height):
    grid = [[0] * grid_width for _ in range(grid_height)]
    placed = []
    # 按尺寸
    sorted_items = sorted(items, key=lambda x: x["grid_width"] * x["grid_height"], reverse=True)
    
    for item in sorted_items:
        # 生成方向选项（考虑旋转）
        orientations = [(item["grid_width"], item["grid_height"], False)]
        if item["grid_width"] != item["grid_height"]:
            orientations.append((item["grid_height"], item["grid_width"], True))
        
        placed_success = False
        
       
        for y in range(grid_height):
            for x in range(grid_width):
                for width, height, rotated in orientations:
                    # 边界检查
                    if x + width > grid_width or y + height > grid_height:
                        continue
                        
                    # 检查空间是否可用
                    if all(grid[y+i][x+j] == 0 for i in range(height) for j in range(width)):
                        # 标记空间为已占用
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
                        placed_success = True
                        break
                if placed_success:
                    break
            if placed_success:
                break
    
    return placed

def create_safe_layout(items):
    selected_items = []
    level_chances = {"purple": 0.5, "blue": 0.27, "gold": 0.2, "red": 0.03}
    
    # 概率选择物品
    for item in items:
        if random.random() <= level_chances.get(item["level"], 0):
            selected_items.append(item)
    
   
    num_items = random.randint(1, 5)
    if len(selected_items) > num_items:
        selected_items = random.sample(selected_items, num_items)
    elif len(selected_items) < num_items:
        # 补充紫色物品
        purple_items = [item for item in items if item["level"] == "purple"]
        if purple_items:
            needed = min(num_items - len(selected_items), len(purple_items))
            selected_items.extend(random.sample(purple_items, needed))
    
    random.shuffle(selected_items)
    
    # 区域选择（带权重）
    region_options = [(2, 1), (3, 1), (4, 1), (4, 2), (4, 3), (4, 4)]
    weights = [2, 3, 3, 3, 1.5, 1]
    region_width, region_height = random.choices(region_options, weights=weights, k=1)[0]
    
    # 固定放置在左上角
    placed_items = place_items(selected_items, region_width, region_height)
    return placed_items, 0, 0, region_width, region_height

def render_safe_layout(placed_items, start_x, start_y, region_width, region_height, cell_size=100):
    grid_size = 4
    img_size = grid_size * cell_size
    safe_img = Image.new("RGB", (img_size, img_size), (50, 50, 50))
    draw = ImageDraw.Draw(safe_img)

    # 绘制整个网格的线条
    for i in range(1, grid_size):
        # 垂直线
        draw.line([(i * cell_size, 0), (i * cell_size, img_size)], fill=(80, 80, 80), width=1)
        # 水平线
        draw.line([(0, i * cell_size), (img_size, i * cell_size)], fill=(80, 80, 80), width=1)

    # 定义物品背景色
    background_colors = {"purple": (50, 43, 97), "blue": (49, 91, 126), "gold": (153, 116, 22), "red": (139, 35, 35)}
    border_color = (100, 100, 100)
    border_width = 2

    # 放置物品
    for placed in placed_items:
        item = placed["item"]
        x0, y0 = placed["x"] * cell_size, placed["y"] * cell_size
        x1, y1 = x0 + placed["width"] * cell_size, y0 + placed["height"] * cell_size
        
        # 获取物品背景色，默认为灰色
        bg_color = background_colors.get(item["level"], (128, 128, 128))
        
        # 绘制物品背景
        draw.rectangle([x0, y0, x1, y1], fill=bg_color, outline=border_color, width=border_width)
        
        try:
            # 加载并放置物品图片
            with Image.open(item["path"]).convert("RGBA") as item_img:
                if placed["rotated"]:
                    item_img = item_img.rotate(90, expand=True)
                
                # 计算物品在单元格内的位置
                inner_width = (placed["width"] * cell_size) - (2 * border_width)
                inner_height = (placed["height"] * cell_size) - (2 * border_width)
                item_img.thumbnail((inner_width, inner_height), Image.LANCZOS)
                
                paste_x = x0 + border_width + (inner_width - item_img.width) // 2
                paste_y = y0 + border_width + (inner_height - item_img.height) // 2
                safe_img.paste(item_img, (paste_x, paste_y), item_img)
        except Exception as e:
            print(f"无法加载或粘贴物品图片: {item['path']}, 错误: {e}")
            
    return safe_img

def get_highest_level(placed_items):
    if not placed_items: return "purple"
    levels = {"purple": 2, "blue": 1, "gold": 3, "red": 4}
    return max((p["item"]["level"] for p in placed_items), key=lambda level: levels.get(level, 0), default="purple")

def cleanup_old_images(keep_recent=2):
    try:
        image_files = glob.glob(os.path.join(output_dir, "*.png"))
        image_files.sort(key=os.path.getmtime, reverse=True)
        for old_file in image_files[keep_recent:]:
            os.remove(old_file)
    except Exception as e:
        print(f"清理旧图片时出错: {e}")

def generate_safe_image():
    """
    生成一张保险箱图片，并返回图片路径和放置的物品列表。
    """
    items = load_items()
    expressions = load_expressions()
    
    if not items or not expressions:
        print("错误: 缺少 items 或 expressions 文件夹中的图片资源。")
        return None, []
    
    placed_items, start_x, start_y, region_width, region_height = create_safe_layout(items)
    safe_img = render_safe_layout(placed_items, start_x, start_y, region_width, region_height)
    highest_level = get_highest_level(placed_items)
    
    expression_map = {"gold": "happy", "red": "eat"}
    expression = expression_map.get(highest_level, "cry")
    
    expr_path = expressions.get(expression)
    if not expr_path: return None, []
    
    try:
        with Image.open(expr_path) as expr_img:
            expr_img.thumbnail((safe_img.height, safe_img.height), Image.LANCZOS)
            final_img = Image.new("RGB", (expr_img.width + safe_img.width, safe_img.height), (240, 240, 240))
            final_img.paste(expr_img, (0, 0))
            final_img.paste(safe_img, (expr_img.width, 0))
    except Exception as e:
        print(f"创建最终图片时出错: {e}")
        return None, []

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"safe_{timestamp}.png")
    final_img.save(output_path)
    
    cleanup_old_images()
    
    return output_path, placed_items
