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

def create_safe_layout(items):
    selected_items = []
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
    
    # Region selection (with weights)
    region_options = [(2, 1), (3, 1), (4, 1), (4, 2), (4, 3), (4, 4)]
    weights = [1, 1.5, 2.5, 2, 2, 1]
    region_width, region_height = random.choices(region_options, weights=weights, k=1)[0]
    
    # Fixed placement in top-left corner
    placed_items = place_items(selected_items, region_width, region_height)
    return placed_items, 0, 0, region_width, region_height

def render_safe_layout(placed_items, start_x, start_y, region_width, region_height, cell_size=100):
    grid_size = 4
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

def generate_safe_image():
    """
    Generate a safe image and return the image path and list of placed items.
    """
    items = load_items()
    expressions = load_expressions()
    
    if not items or not expressions:
        print("Error: Missing image resources in items or expressions folders.")
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
        print(f"Error creating final image: {e}")
        return None, []

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"safe_{timestamp}.png")
    final_img.save(output_path)
    
    cleanup_old_images()
    
    return output_path, placed_items
