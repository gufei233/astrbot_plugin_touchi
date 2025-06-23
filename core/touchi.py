import os
import random
from PIL import Image, ImageDraw, ImageOps
from datetime import datetime
import glob

# 创建必要的文件夹
os.makedirs("items", exist_ok=True)
os.makedirs("expressions", exist_ok=True)
os.makedirs("output", exist_ok=True)

# 从items文件夹加载物品图片
def load_items():
    items = []
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    
    for filename in os.listdir("items"):
        if any(filename.lower().endswith(ext) for ext in valid_extensions):
            parts = os.path.splitext(filename)[0].split('_')
            if len(parts) < 2:
                level = "purple"
                size = "1x1"
            else:
                level = parts[0]
                size = parts[1]
            
            width, height = get_size(size)
            item_path = os.path.join("items", filename)
            
            try:
                with Image.open(item_path) as img:
                    img_width, img_height = img.size
                    aspect_ratio = img_width / img_height
            except:
                img_width, img_height = width * 100, height * 100
                aspect_ratio = width / height
            
            items.append({
                "path": item_path,
                "level": level.lower(),
                "size": size,
                "grid_width": width,
                "grid_height": height,
                "img_width": img_width,
                "img_height": img_height,
                "aspect_ratio": aspect_ratio
            })
    
    return items

# 加载表情图片
def load_expressions():
    expressions = {}
    valid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    
    for filename in os.listdir("expressions"):
        if any(filename.lower().endswith(ext) for ext in valid_extensions):
            expr_name = os.path.splitext(filename)[0]
            expr_path = os.path.join("expressions", filename)
            expressions[expr_name] = expr_path
    
    return expressions

# 获取物品尺寸
def get_size(size_str):
    if 'x' in size_str:
        parts = size_str.split('x')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return 1, 1

# 优化后的网格放置算法 - 增加随机性和空白空间
def place_items(items, grid_width, grid_height):
    grid = [[0] * grid_width for _ in range(grid_height)]
    placed = []
    
        # 按物品大小排序（大物品优先）
    sorted_items = sorted(items, key=lambda x: x["grid_width"] * x["grid_height"], reverse=True)
    
    # 尝试放置每个物品
    for item in sorted_items:
        # 尝试两个方向（正常和旋转）
        orientations = [
            (item["grid_width"], item["grid_height"], False),
            (item["grid_height"], item["grid_width"], True)
        ] if item["grid_width"] != item["grid_height"] else [
            (item["grid_width"], item["grid_height"], False)
        ]
        
        placed_success = False
        
        # 随机尝试次数限制（避免过于紧凑）
        max_attempts = 5
        attempts = 0
        
        while not placed_success and attempts < max_attempts:
            # 尝试网格中的随机位置
            possible_y = list(range(grid_height))
            possible_x = list(range(grid_width))
            random.shuffle(possible_y)
            random.shuffle(possible_x)
            
            for y in possible_y:
                for x in possible_x:
                    for width, height, rotated in orientations:
                        # 检查是否超出边界
                        if x + width > grid_width or y + height > grid_height:
                            continue
                            
                        # 检查位置是否可用
                        if all(grid[y + i][x + j] == 0 
                               for i in range(height) 
                               for j in range(width)):
                            # 标记位置为已占用
                            for i in range(height):
                                for j in range(width):
                                    grid[y + i][x + j] = 1
                            
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
            attempts += 1
    
    return placed

# 创建保险箱布局 - 减少物品数量并随机选择放置区域
def create_safe_layout(items):
    # 概率分布选择物品
    selected_items = []
    for item in items:
        r = random.random()
        if item["level"] == "purple" and r <= 0.5:  
            selected_items.append(item)
        elif item["level"] == "blue" and r <= 0.27:  
            selected_items.append(item)
        elif item["level"] == "gold" and r <= 0.2:
            selected_items.append(item)
        elif item["level"] == "red" and r <= 0.03:
            selected_items.append(item)
    
    # 减少物品数量：1-4个
    num_items = random.randint(1, 4)
    if len(selected_items) < num_items:
        purple_items = [item for item in items if item["level"] == "purple"]
        if purple_items:
            needed = min(num_items - len(selected_items), len(purple_items))
            selected_items.extend(random.sample(purple_items, needed))
    
    # 随机打乱物品顺序
    random.shuffle(selected_items)
    
    # 随机选择放置区域大小 (1x2, 2x2, 2x3, 3x3, 3x4, 4x4)
    region_options = [
        (2, 1), (3, 1),(4, 1),(4, 2), (4, 3), (4, 4)
    ]
        # 设置权重分布：中间高，两边低
    weights = [2, 3, 3, 3, 1.5, 1]
    
    # 根据权重随机选择区域尺寸
    region_width, region_height = random.choices(
        region_options, 
        weights=weights, 
        k=1
    )[0]

    # 固定放置区域在左上角 (0,0)
    start_x = 0
    start_y = 0
    
    # 放置物品到网格
    placed_items = place_items(selected_items, region_width, region_height)
    
    # 调整坐标到整个网格
    for item in placed_items:
        item["x"] += start_x
        item["y"] += start_y
    
    return placed_items, start_x, start_y, region_width, region_height

# 渲染保险箱图像 - 添加淡灰色边框
def render_safe_layout(placed_items, start_x, start_y, region_width, region_height, cell_size=100):
    grid_size = 4
    img_size = grid_size * cell_size
    safe_img = Image.new("RGB", (img_size, img_size), (50, 50, 50))
    draw = ImageDraw.Draw(safe_img)
    
    # 绘制网格线
    for i in range(1, grid_size):
        draw.line([(i * cell_size, 0), (i * cell_size, img_size)], fill=(80, 80, 80), width=1)
        draw.line([(0, i * cell_size), (img_size, i * cell_size)], fill=(80, 80, 80), width=1)
    
    # 高亮显示放置区域
    region_x0 = start_x * cell_size
    region_y0 = start_y * cell_size
    region_x1 = (start_x + region_width) * cell_size
    region_y1 = (start_y + region_height) * cell_size
    
    # 绘制放置区域背景（比主背景稍亮）
    draw.rectangle([region_x0, region_y0, region_x1, region_y1], fill=(60, 60, 60))
    
    # 定义各级别的背景色
    background_colors = {
        "purple": (50, 43, 97),    # 紫色背景
        "blue": (49, 91, 126),     # 蓝色背景
        "gold": (153, 116, 22),    # 金色背景
        "red": (139, 35, 35)       # 红色背景
    }
    
    # 定义边框颜色和宽度
    border_color = (100, 100, 100)  # 淡灰色边框
    border_width = 2  # 边框宽度
    
    # 放置物品
    for placed in placed_items:
        item = placed["item"]
        img_path = item["path"]
        level = item["level"]
        
        # 计算物品位置和尺寸
        x0 = placed["x"] * cell_size
        y0 = placed["y"] * cell_size
        x1 = x0 + placed["width"] * cell_size
        y1 = y0 + placed["height"] * cell_size
        
        # 获取对应级别的背景色
        bg_color = background_colors.get(level, (128, 128, 128))  # 默认灰色
        
        # 绘制背景矩形
        draw.rectangle([x0, y0, x1, y1], fill=bg_color)
        
        # 绘制淡灰色边框
        draw.rectangle([x0, y0, x1, y1], outline=border_color, width=border_width)
        
        try:
            item_img = Image.open(img_path).convert("RGBA")
            
            # 应用旋转
            if placed["rotated"]:
                item_img = item_img.rotate(90, expand=True)
            
            # 计算目标尺寸（考虑边框）
            inner_width = placed["width"] * cell_size - 2 * border_width
            inner_height = placed["height"] * cell_size - 2 * border_width
            
            # 保持宽高比调整大小
            img_width, img_height = item_img.size
            img_aspect = img_width / img_height
            target_aspect = inner_width / inner_height
            
            if img_aspect > target_aspect:
                # 图片比目标宽
                new_height = int(inner_width / img_aspect)
                new_width = inner_width
                if new_height > inner_height:
                    new_height = inner_height
                    new_width = int(inner_height * img_aspect)
            else:
                # 图片比目标高
                new_width = int(inner_height * img_aspect)
                new_height = inner_height
                if new_width > inner_width:
                    new_width = inner_width
                    new_height = int(inner_width / img_aspect)
            
            # 调整大小
            item_img = item_img.resize((new_width, new_height), Image.LANCZOS)
            
            # 计算居中位置（考虑边框）
            paste_x = x0 + border_width + (inner_width - new_width) // 2
            paste_y = y0 + border_width + (inner_height - new_height) // 2
            
            # 粘贴到安全图像
            safe_img.paste(item_img, (paste_x, paste_y), item_img)
            
        except Exception as e:
            print(f"无法加载物品图片: {img_path}, 错误: {e}")
            # 如果加载失败，背景色和边框已经绘制，无需额外处理
    
    return safe_img

# 获取最高级别物品
def get_highest_level(placed_items):
    if not placed_items:
        return "purple"
    
    levels = {"purple": 2, "blue": 1, "gold": 3, "red": 4}
    highest_level = "blue"
    highest_value = 1
    
    for placed in placed_items:
        level = placed["item"]["level"]
        value = levels.get(level, 1)
        if value > highest_value:
            highest_value = value
            highest_level = level
        elif value == highest_value and level == "red":
            highest_level = level
    
    return highest_level

# 清理旧图片（只保留最新生成的图片）
def cleanup_old_images(keep_recent=1):
    try:
        # 获取output文件夹中的所有图片
        image_files = glob.glob(os.path.join("output", "*.png"))
        
        # 按修改时间排序（最新的在前）
        image_files.sort(key=os.path.getmtime, reverse=True)
        
        # 删除旧图片（只保留最新的一张）
        if len(image_files) > keep_recent:
            for old_file in image_files[keep_recent:]:
                try:
                    os.remove(old_file)
                    print(f"已删除旧图片: {os.path.basename(old_file)}")
                except Exception as e:
                    print(f"删除图片时出错: {old_file}, 错误: {e}")
    except Exception as e:
        print(f"清理旧图片时出错: {e}")

# 主函数
def main():
    items = load_items()
    expressions = load_expressions()
    
    if not items:
        print("错误: items文件夹中没有找到任何物品图片！")
        print("请将物品图片放入items文件夹中，命名格式为: 级别_尺寸_唯一标识.扩展名")
        print("例如: purple_1x1_1.png, red_2x3_2.jpg")
        print("可用级别: purple(紫色), blue(蓝色), gold(金色), red(红色)")
        return
    
    if not expressions:
        print("错误: expressions文件夹中没有找到表情图片！")
        print("请将表情图片放入expressions文件夹中，命名为: cry.png, happy.png, eat.png")
        return
    
    # 创建保险箱布局
    placed_items, start_x, start_y, region_width, region_height = create_safe_layout(items)
    
    # 渲染保险箱图像
    safe_img = render_safe_layout(placed_items, start_x, start_y, region_width, region_height)
    
    # 获取最高级别物品
    highest_level = get_highest_level(placed_items)
    
    # 根据最高级别选择表情
    expression = "cry"
    if  highest_level == "gold":
        expression = "happy"
    elif highest_level == "red":
        expression = "eat"
    
    # 加载表情图片
    expr_path = expressions.get(expression)
    if not expr_path:
        print(f"错误: 找不到表情图片 '{expression}'！")
        return
    
    try:
        expr_img = Image.open(expr_path)
    except Exception as e:
        print(f"无法加载表情图片: {expr_path}, 错误: {e}")
        return
    
    # 创建最终图像
    # 调整表情图片大小以适应保险箱高度
    expr_img = expr_img.resize((safe_img.height, safe_img.height))
    
    # 创建最终图像（表情在左侧，保险箱在右侧）
    final_width = expr_img.width + safe_img.width
    final_height = max(expr_img.height, safe_img.height)
    final_img = Image.new("RGB", (final_width, final_height), (240, 240, 240))
    
    # 粘贴表情图片（左侧）
    final_img.paste(expr_img, (0, 0))
    
    # 粘贴保险箱图片（右侧）
    final_img.paste(safe_img, (expr_img.width, 0))
    
    # 保存输出
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"output/safe_{timestamp}.png"
    final_img.save(output_path)
    
    # 清理旧图片（只保留最新的一张）
    cleanup_old_images()
    

if __name__ == "__main__":
    main()