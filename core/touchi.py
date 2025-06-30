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

# Define border color
ITEM_BORDER_COLOR = (100, 100, 110)
BORDER_WIDTH = 1

def get_size(size_str):
    if 'x' in size_str:
        parts = size_str.split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return 1, 1

# 物品价值映射表
ITEM_VALUES = {
    # Blue items (蓝色物品)
    "blue_1x1_cha": 10030, "blue_1x1_jidianqi": 10459, "blue_1x1_kele": 12654,
    "blue_1x1_paotengpian": 9908, "blue_1x1_sanjiao": 11984, "blue_1x1_shangyewenjian": 7812,
    "blue_1x1_yinbi": 8661, "blue_1x2_kafeihu": 16604, "blue_1x2_nvlang": 15242,
    "blue_1x2_wangyuanjing": 11389, "blue_1x2_yandou": 15504, "blue_1x2_zidanlingjian": 20405,
    "blue_1x3_luyin": 28296, "blue_2x1_qiangxieliangjian": 17558, "blue_2x1_xianwei": 25325,
    "blue_2x2_meiqiguan": 21715, "blue_2x2_wenduji": 17403, "blue_2x2_wurenji": 98589,
    "blue_2x2_youqi": 21361, "blue_2x2_zazhi": 16694, "blue_2x3_shuini": 50545,
    "blue_3x1_guju": 19900, "blue_4x2_tainengban": 24434,
    
    # Gold items (金色物品)
    "gold_1x1_1": 1936842, "gold_1x1_2": 1576462, "gold_1x1_chuliqi": 105766,
    "gold_1x1_cpu": 64177, "gold_1x1_duanzi": 58182, "gold_1x1_huoji": 61611,
    "gold_1x1_jinbi": 57741, "gold_1x1_jingtou": 105244, "gold_1x1_jiubei": 62760,
    "gold_1x1_kafei": 68304, "gold_1x1_mofang": 94669, "gold_1x1_ranliao": 68336,
    "gold_1x1_shouji": 61319, "gold_1x1_tuzhi": 67208, "gold_1x2_longshelan": 80863,
    "gold_1x2_maixiaodan": 0, "gold_1x2_taoyong": 90669, "gold_2x2_danfan": 129910,
    "gold_2x2_dianlan": 447649, "gold_2x2_tongxunyi": 501153, "gold_2x2_wangyuanjing": 93442,
    "gold_2x2_zhayao": 131427, "gold_2x2_zhong": 58000, "gold_2x3_ranliaodianchi": 378482,
    "gold_3x1_touguan": 143697, "gold_3x2_": 394788, "gold_3x2_bendishoushi": 424032,
    "gold_4x3_fuwuqi": 593475,
    
    # Purple items (紫色物品)
    "purple_1x1_1": 338091, "purple_1x1_2": 824218, "purple_1x1_3": 335980, "purple_1x1_4": 1056413,
    "purple_1x1_erhuan": 13172, "purple_1x1_ganraoqi": 12079, "purple_1x1_jiandiebi": 21086,
    "purple_1x1_junshiqingbao": 12554, "purple_1x1_neicun": 26305, "purple_1x1_rexiangyi": 55993,
    "purple_1x1_shoubing": 34616, "purple_1x1_shoudian": 19861, "purple_1x1_wandao": 24128,
    "purple_1x2_dangan": 22530, "purple_1x2_fuliaobao": 18685, "purple_1x2_jiuhu": 24732,
    "purple_1x2_shizhang": 20464, "purple_1x2_shuihu": 32154, "purple_1x2_tezhonggang": 44260,
    "purple_1x2_tideng": 36019, "purple_2x1_niuniu": 17145, "purple_2x2_lixinji": 60559,
    "purple_2x2_shouju": 51703, "purple_2x2_xueyayi": 37439, "purple_2x2_zhuban": 47223,
    "purple_2x3_dentai": 112592, "purple_3x2_bishou": 114755, "purple_3x2_diandongche": 66852,
    
    # Red items (红色物品)
    "red_1x1_1": 4085603, "red_1x1_2": 6775951, "red_1x1_3": 4603790,
    "red_1x1_huaibiao": 214532, "red_1x1_jixiebiao": 210234, "red_1x1_xin": 13581911,
    "red_1x1_yuzijiang": 174537, "red_1x2_jintiao": 330271, "red_1x2_maixiaodan": 0,
    "red_1x2_xiangbin": 337113, "red_2x1_huashi": 346382, "red_2x1_xianka": 332793,
    "red_2x2_jingui": 440000, "red_2x2_junyongji": 534661, "red_2x2_lu": 434781,
    "red_2x2_tianyuandifang": 537003, "red_2x2_weixing": 245000, "red_2x3_liushengji": 1264435,
    "red_2x3_rentou": 1300362, "red_2x3_yiliaobot": 1253570, "red_3x2_buzhanche": 1333684,
    "red_3x2_dainnao": 3786322, "red_3x2_paodan": 1440722, "red_3x2_zhuangjiadianchi": 1339889,
    "red_3x3_banzi": 2111841, "red_3x3_chaosuan": 2003197, "red_3x3_fanyinglu": 2147262,
    "red_3x3_huxiji": 10962096, "red_3x3_tanke": 2113480, "red_3x3_wanjinleiguan": 3646401,
    "red_3x3_zongheng": 3337324, "red_3x4_daopian": 1427562, "red_3x4_ranliao": 1400000,
    "red_4x1_huatang": 676493, "red_4x3_cipanzhenlie": 1662799, "red_4x3_dongdidianchi": 1409728
}

# 稀有物品列表 - 概率为原来的三分之一
RARE_ITEMS = {
    "gold_1x1_1", "gold_1x1_2", "red_1x1_1", "red_1x1_2", "red_1x1_3", 
    "red_3x3_huxiji", "gold_3x2_bendishoushi", "purple_1x1_2", "purple_1x1_4","purple_1x1_3", "purple_1x1_1","red_4x3_cipanzhenlie","red_4x3_dongdidianchi","red_3x4_daopian","red_3x3_wanjinleiguan","red_3x3_tanke"
}

# 超稀有物品列表 - 概率为0.0009%
ULTRA_RARE_ITEMS = {
    "red_1x1_xin"
}

def get_item_value(item_name):
    """获取物品价值"""
    return ITEM_VALUES.get(item_name, 1000)

# 缓存物品列表以提高性能
_items_cache = None
_items_cache_time = 0
CACHE_DURATION = 300  # 5分钟缓存

def load_items():
    global _items_cache, _items_cache_time
    import time
    
    current_time = time.time()
    # 检查缓存是否有效
    if _items_cache is not None and (current_time - _items_cache_time) < CACHE_DURATION:
        return _items_cache
    
    items = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')  # 使用元组提高性能
    
    try:
        for filename in os.listdir(items_dir):
            if not filename.lower().endswith(valid_extensions):
                continue
                
            file_path = os.path.join(items_dir, filename)
            if not os.path.isfile(file_path):
                continue
                
            parts = os.path.splitext(filename)[0].split('_')
            level = parts[0].lower() if len(parts) >= 2 else "purple"
            size = parts[1] if len(parts) >= 2 else "1x1"
            width, height = get_size(size)
            
            # 获取物品基础名称（不含扩展名）
            item_base_name = os.path.splitext(filename)[0]
            item_value = get_item_value(item_base_name)
            
            items.append({
                "path": file_path, "level": level, "size": size,
                "grid_width": width, "grid_height": height,
                "base_name": item_base_name, "value": item_value,
                "name": f"{item_base_name} (价值: {item_value:,})"
            })
    except Exception as e:
        print(f"Error loading items: {e}")
        return []
    
    # 更新缓存
    _items_cache = items
    _items_cache_time = current_time
    return items

def load_expressions():
    expressions = {}
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    for filename in os.listdir(expressions_dir):
        file_path = os.path.join(expressions_dir, filename)
        if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in valid_extensions):
            expressions[os.path.splitext(filename)[0]] = file_path
    return expressions

def place_items(items, grid_width, grid_height, total_grid_size=2):
    # 优化：使用一维数组代替二维数组提高性能
    grid = [0] * (grid_width * grid_height)
    placed = []
    
    # Sort by size (biggest first) - 优化排序
    sorted_items = sorted(items, key=lambda x: x["grid_width"] * x["grid_height"], reverse=True)
    
    for item in sorted_items:
        # Generate orientation options (consider rotation)
        orientations = [(item["grid_width"], item["grid_height"], False)]
        if item["grid_width"] != item["grid_height"]:
            orientations.append((item["grid_height"], item["grid_width"], True))
        
        placed_success = False
        
        # Try to place the item - 优化循环
        for y in range(grid_height):
            if placed_success:
                break
            for x in range(grid_width):
                if placed_success:
                    break
                for width, height, rotated in orientations:
                    # 新的边界检查：物品左上角必须在放置格子内，但物品整体必须在总格子内
                    # 左上角在放置格子内的检查（x, y必须在grid_width, grid_height范围内）
                    if x >= grid_width or y >= grid_height:
                        continue
                    
                    # 物品整体在总格子内的检查
                    if x + width > total_grid_size or y + height > total_grid_size:
                        continue
                        
                    # Check if space is available - 只检查在放置格子内的部分
                    can_place = True
                    for i in range(height):
                        if not can_place:
                            break
                        for j in range(width):
                            # 只检查在放置格子范围内的格子是否被占用
                            check_x = x + j
                            check_y = y + i
                            if check_x < grid_width and check_y < grid_height:
                                if grid[check_y * grid_width + check_x] != 0:
                                    can_place = False
                                    break
                    
                    if can_place:
                        # Mark space as occupied - 只标记在放置格子内的部分
                        for i in range(height):
                            for j in range(width):
                                mark_x = x + j
                                mark_y = y + i
                                if mark_x < grid_width and mark_y < grid_height:
                                    grid[mark_y * grid_width + mark_x] = 1
                        
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
    
    return placed

def create_safe_layout(items, menggong_mode=False, grid_size=2, auto_mode=False):
    selected_items = []
    
    # 根据模式调整概率
    if auto_mode:
        # 自动模式：金红概率降低
        if menggong_mode:
            level_chances = {"purple": 0.55, "blue": 0.0, "gold": 0.15, "red": 0.033}
        else:
            level_chances = {"purple": 0.52, "blue": 0.35, "gold": 0.093, "red": 0.017}
    elif menggong_mode:
        level_chances = {"purple": 0.45, "blue": 0.0, "gold": 0.45, "red": 0.10}
    else:
        level_chances = {"purple": 0.42, "blue": 0.25, "gold": 0.28, "red": 0.05}
    
    # Probabilistic item selection with rare item handling
    for item in items:
        base_chance = level_chances.get(item["level"], 0)
        item_name = item["base_name"]
        
        # 调整稀有物品概率
        if item_name in ULTRA_RARE_ITEMS:
            # 超稀有物品：0.0009%概率
            final_chance = 0.000009
        elif item_name in RARE_ITEMS:
            # 稀有物品：原概率的三分之一
            final_chance = base_chance / 3
        else:
            final_chance = base_chance
            
        if random.random() <= final_chance:
            selected_items.append(item)
    
    # Limit number of items
    num_items = random.randint(1, 5)
    if len(selected_items) > num_items:
        selected_items = random.sample(selected_items, num_items)
    elif len(selected_items) < num_items:
        # Supplement with purple items (excluding rare ones)
        purple_items = [item for item in items if item["level"] == "purple" and item["base_name"] not in RARE_ITEMS]
        if purple_items:
            needed = min(num_items - len(selected_items), len(purple_items))
            selected_items.extend(random.sample(purple_items, needed))
    
    random.shuffle(selected_items)
    
    # Region selection (with weights) - 根据特勤处等级调整
    base_options = [(2, 1), (3, 1), (4, 1), (4, 2), (4, 3), (4, 4)]
    
    # 根据grid_size扩展region_options
    if grid_size == 3:  # 特勤处1级
        region_options = [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 4:  # 特勤处2级
        region_options = [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 5:  # 特勤处3级
        region_options = [(w+3, h+3) for w, h in base_options] + [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 6:  # 特勤处4级
        region_options = [(w+4, h+4) for w, h in base_options] + [(w+3, h+3) for w, h in base_options] + [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 7:  # 特勤处5级
        region_options = [(w+5, h+5) for w, h in base_options] + [(w+4, h+4) for w, h in base_options] + [(w+3, h+3) for w, h in base_options] + [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    else:
        region_options = base_options
    
    # 确保region不超过grid_size
    region_options = [(w, h) for w, h in region_options if w <= grid_size and h <= grid_size]
    
    weights = [1] * len(region_options)
    region_width, region_height = random.choices(region_options, weights=weights, k=1)[0]
    
    # Fixed placement in top-left corner
    placed_items = place_items(selected_items, region_width, region_height, grid_size)
    return placed_items, 0, 0, region_width, region_height

def render_safe_layout(placed_items, start_x, start_y, region_width, region_height, grid_size=2, cell_size=100):
    img_size = grid_size * cell_size
    safe_img = Image.new("RGB", (img_size, img_size), (50, 50, 50))
    draw = ImageDraw.Draw(safe_img)

    # Draw grid lines first
    for i in range(1, grid_size):
        # Vertical lines
        draw.line([(i * cell_size, 0), (i * cell_size, img_size)], fill=(80, 80, 80), width=1)
        # Horizontal lines
        draw.line([(0, i * cell_size), (img_size, i * cell_size)], fill=(80, 80, 80), width=1)

    # Define item background colors (with transparency)
    background_colors = {
        "purple": (50, 43, 97, 90), 
        "blue": (49, 91, 126, 90), 
        "gold": (153, 116, 22, 90), 
        "red": (139, 35, 35, 90)
    }

    # Create temporary transparent layer for item backgrounds
    overlay = Image.new("RGBA", safe_img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Place items
    for placed in placed_items:
        item = placed["item"]
        x0, y0 = placed["x"] * cell_size, placed["y"] * cell_size
        x1, y1 = x0 + placed["width"] * cell_size, y0 + placed["height"] * cell_size
        
        # Get item background color
        bg_color = background_colors.get(item["level"], (128, 128, 128, 200))
        
        # Draw item background (with transparency)
        overlay_draw.rectangle([x0, y0, x1, y1], fill=bg_color)
        
        try:
            # Load and place item image
            with Image.open(item["path"]).convert("RGBA") as item_img:
                if placed["rotated"]:
                    item_img = item_img.rotate(90, expand=True)
                
                # Calculate position within cell
                inner_width = placed["width"] * cell_size
                inner_height = placed["height"] * cell_size
                item_img.thumbnail((inner_width, inner_height), Image.LANCZOS)
                
                paste_x = x0 + (inner_width - item_img.width) // 2
                paste_y = y0 + (inner_height - item_img.height) // 2
                
                # Paste item image onto overlay
                overlay.paste(item_img, (int(paste_x), int(paste_y)), item_img)
        except Exception as e:
            print(f"Error loading/pasting item image: {item['path']}, error: {e}")
    
        # Draw item border (on the main image, not the overlay)
        draw.rectangle([x0, y0, x1, y1], outline=ITEM_BORDER_COLOR, width=BORDER_WIDTH)
    
    # Merge overlay with base image
    safe_img = Image.alpha_composite(safe_img.convert("RGBA"), overlay).convert("RGB")
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
        print(f"Error cleaning up old images: {e}")

def generate_safe_image(menggong_mode=False, grid_size=2):
    """
    Generate a safe image and return the image path and list of placed items.
    """
    items = load_items()
    expressions = load_expressions()
    
    if not items or not expressions:
        print("Error: Missing image resources in items or expressions folders.")
        return None, []
    
    placed_items, start_x, start_y, region_width, region_height = create_safe_layout(items, menggong_mode, grid_size)
    safe_img = render_safe_layout(placed_items, start_x, start_y, region_width, region_height, grid_size)
    highest_level = get_highest_level(placed_items)
    
    expression_map = {"gold": "happy", "red": "eat"}
    expression = expression_map.get(highest_level, "cry")
    
    expr_path = expressions.get(expression)
    if not expr_path: return None, []
    
    try:
        with Image.open(expr_path).convert("RGBA") as expr_img:
            # 移除白边：创建一个没有白边的版本
            # 转换为RGBA以处理透明度
            expr_img.thumbnail((safe_img.height, safe_img.height), Image.LANCZOS)
            
            # 创建一个与保险箱背景色相同的背景
            final_img = Image.new("RGB", (expr_img.width + safe_img.width, safe_img.height), (50, 50, 50))
            
            # 如果表情图片有透明通道，使用背景色填充
            if expr_img.mode == 'RGBA':
                # 创建一个与背景色相同的底图
                expr_bg = Image.new("RGB", expr_img.size, (50, 50, 50))
                expr_bg.paste(expr_img, mask=expr_img.split()[-1])  # 使用alpha通道作为mask
                final_img.paste(expr_bg, (0, 0))
            else:
                final_img.paste(expr_img, (0, 0))
            
            final_img.paste(safe_img, (expr_img.width, 0))
    except Exception as e:
        print(f"Error creating final image: {e}")
        return None, []

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"safe_{timestamp}.png")
    final_img.save(output_path)
    
    cleanup_old_images()
    
    return output_path, placed_items
