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
    "blue_1x1_cha": 1200, "blue_1x1_jidianqi": 1500, "blue_1x1_kele": 800,
    "blue_1x1_paotengpian": 1000, "blue_1x1_sanjiao": 900, "blue_1x1_shangyewenjian": 1100,
    "blue_1x1_yinbi": 1300, "blue_1x2_kafeihu": 2400, "blue_1x2_nvlang": 2200,
    "blue_1x2_wangyuanjing": 2600, "blue_1x2_yandou": 2000, "blue_1x2_zidanlingjian": 2800,
    "blue_1x3_luyin": 3600, "blue_2x1_qiangxieliangjian": 2400, "blue_2x1_xianwei": 2200,
    "blue_2x2_meiqiguan": 4800, "blue_2x2_wenduji": 4400, "blue_2x2_wurenji": 4600,
    "blue_2x2_youqi": 4200, "blue_2x2_zazhi": 4000, "blue_2x3_shuini": 7200,
    "blue_3x1_guju": 3600, "blue_4x2_tainengban": 9600,
    
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
    "purple_1x1_1": 338091, "purple_1x1_2": 824218, "purple_1x1_3": 3643636, "purple_1x1_4": 1936842,
    "purple_1x1_erhuan": 9500, "purple_1x1_ganraoqi": 10000, "purple_1x1_jiandiebi": 9000,
    "purple_1x1_junshiqingbao": 11000, "purple_1x1_neicun": 10500, "purple_1x1_rexiangyi": 9200,
    "purple_1x1_shoubing": 8800, "purple_1x1_shoudian": 8600, "purple_1x1_wandao": 9800,
    "purple_1x2_dangan": 18000, "purple_1x2_fuliaobao": 16000, "purple_1x2_jiuhu": 17000,
    "purple_1x2_shizhang": 19000, "purple_1x2_shuihu": 15000, "purple_1x2_tezhonggang": 20000,
    "purple_1x2_tideng": 16500, "purple_2x1_niuniu": 18000, "purple_2x2_lixinji": 36000,
    "purple_2x2_shouju": 34000, "purple_2x2_xueyayi": 38000, "purple_2x2_zhuban": 35000,
    "purple_2x3_dentai": 54000, "purple_3x2_bishou": 54000, "purple_3x2_diandongche": 56000,
    
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

def get_item_value(item_name):
    """获取物品价值"""
    return ITEM_VALUES.get(item_name, 1000)

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
            
            # 获取物品基础名称（不含扩展名）
            item_base_name = os.path.splitext(filename)[0]
            item_value = get_item_value(item_base_name)
            
            items.append({
                "path": file_path, "level": level.lower(), "size": size,
                "grid_width": width, "grid_height": height,
                "base_name": item_base_name, "value": item_value,
                "name": f"{item_base_name} (价值: {item_value:,})"
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
    # Sort by size (biggest first)
    sorted_items = sorted(items, key=lambda x: x["grid_width"] * x["grid_height"], reverse=True)
    
    for item in sorted_items:
        # Generate orientation options (consider rotation)
        orientations = [(item["grid_width"], item["grid_height"], False)]
        if item["grid_width"] != item["grid_height"]:
            orientations.append((item["grid_height"], item["grid_width"], True))
        
        placed_success = False
        
        # Try to place the item
        for y in range(grid_height):
            for x in range(grid_width):
                for width, height, rotated in orientations:
                    # Boundary check
                    if x + width > grid_width or y + height > grid_height:
                        continue
                        
                    # Check if space is available
                    if all(grid[y+i][x+j] == 0 for i in range(height) for j in range(width)):
                        # Mark space as occupied
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

def create_safe_layout(items, menggong_mode=False, grid_size=4):
    selected_items = []
    
    # 根据猛攻模式调整概率
    if menggong_mode:
        level_chances = {"purple": 0.45, "blue": 0.0, "gold": 0.4, "red": 0.15}
    else:
        level_chances = {"purple": 0.42, "blue": 0.25, "gold": 0.28, "red": 0.05}
    
    # Probabilistic item selection
    for item in items:
        if random.random() <= level_chances.get(item["level"], 0):
            selected_items.append(item)
    
    # Limit number of items
    num_items = random.randint(1, 5)
    if len(selected_items) > num_items:
        selected_items = random.sample(selected_items, num_items)
    elif len(selected_items) < num_items:
        # Supplement with purple items
        purple_items = [item for item in items if item["level"] == "purple"]
        if purple_items:
            needed = min(num_items - len(selected_items), len(purple_items))
            selected_items.extend(random.sample(purple_items, needed))
    
    random.shuffle(selected_items)
    
    # Region selection (with weights) - 根据特勤处等级调整
    base_options = [(2, 1), (3, 1), (4, 1), (4, 2), (4, 3), (4, 4)]
    
    # 根据grid_size扩展region_options
    if grid_size == 5:  # 特勤处1级
        region_options = [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 6:  # 特勤处2级
        region_options = [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    elif grid_size == 7:  # 特勤处3级
        region_options = [(w+3, h+3) for w, h in base_options] + [(w+2, h+2) for w, h in base_options] + [(w+1, h+1) for w, h in base_options] + base_options
    else:
        region_options = base_options
    
    # 确保region不超过grid_size
    region_options = [(w, h) for w, h in region_options if w <= grid_size and h <= grid_size]
    
    weights = [1] * len(region_options)
    region_width, region_height = random.choices(region_options, weights=weights, k=1)[0]
    
    # Fixed placement in top-left corner
    placed_items = place_items(selected_items, region_width, region_height)
    return placed_items, 0, 0, region_width, region_height

def render_safe_layout(placed_items, start_x, start_y, region_width, region_height, grid_size=4, cell_size=100):
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

def generate_safe_image(menggong_mode=False, grid_size=4):
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
        with Image.open(expr_path) as expr_img:
            expr_img.thumbnail((safe_img.height, safe_img.height), Image.LANCZOS)
            final_img = Image.new("RGB", (expr_img.width + safe_img.width, safe_img.height), (240, 240, 240))
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
