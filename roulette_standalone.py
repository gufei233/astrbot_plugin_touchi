import os
import random
import math
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import sys
import logging

# 独立运行的日志配置
class Logger:
    def __init__(self):
        self.logger = logging.getLogger('roulette_standalone')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)

# 全局日志实例
logger = Logger()

class RouletteWheel:
    """转盘生成器 - 独立版本"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 地图难度映射关系
        self.map_difficulty_constraints = {
            "零号大坝": ["常规", "机密", "绝密"],  # 都有
            "巴克什": ["机密", "绝密"],  # 没有常规
            "长弓溪谷": ["常规", "机密"],  # 没有绝密
            "航天基地": ["机密", "绝密"],  # 没有常规
            "潮汐监狱": ["监狱"]  # 只有监狱
        }
        
        # 转盘配置 - 使用更美观的渐变色系 <mcreference link="https://how.dev/answers/how-to-make-a-circular-color-gradient-in-python" index="1">1</mcreference>
        self.wheel_configs = [
            {
                "title": "地图",
                "items": ["零号大坝", "巴克什", "长弓溪谷", "航天基地", "潮汐监狱"],
                "colors": ["#FF6B9D", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
            },
            {
                "title": "地图难度",
                "items": ["常规", "机密", "绝密", "监狱"],  # 添加监狱难度
                "colors": ["#74B9FF", "#FD79A8", "#FDCB6E", "#E17055"]
            },
            {
                "title": "子弹等级",
                "items": ["一级", "二级", "三级", "四级", "五级", "六级"],
                "colors": ["#FF9F43", "#10AC84", "#5F27CD", "#00D2D3", "#FF6348", "#2E86AB"]
            },
            {
                "title": "护甲等级",
                "items": ["一级", "二级", "三级", "四级", "五级", "六级"],
                "colors": ["#A55EEA", "#26DE81", "#2BCBBA", "#FED330", "#FA8231", "#FC5C65"]
            },
            {
                "title": "头盔等级",
                "items": ["一级", "二级", "三级", "四级", "五级", "六级"],
                "colors": ["#3742FA", "#2F3542", "#FF3838", "#FF9500", "#7BED9F", "#70A1FF"]
            },
            {
                "title": "枪",
                "items": ["狙击枪", "霰弹枪", "手枪", "冲锋枪", "突击步枪", "射手步枪", "不带枪"],
                "colors": ["#FF6B9D", "#74B9FF", "#00D2D3", "#FDCB6E", "#E84393", "#A29BFE", "#636E72"]
            }
        ]
        
        # 动画参数 - 动态计算画布大小，紧凑布局
        self.wheel_size = 140
        self.margin = 20  # 统一边距
        self.wheel_spacing_x = 200  # 转盘水平间距（更紧凑）
        self.wheel_spacing_y = 160  # 转盘垂直间距（更紧凑）
        
        # 动态计算画布大小：考虑转盘间距和文字显示空间
        # 3列转盘，每列之间有间距，右侧需要预留文字显示空间
        self.canvas_width = self.margin * 2 + self.wheel_size * 3 + self.wheel_spacing_x // 3 * 2 + 100  # 右侧预留文字空间
        # 2行转盘 + 边距
        self.canvas_height = self.margin * 2 + self.wheel_size * 2 + self.wheel_spacing_y // 2
        
        self.total_frames = 60  # 减少帧数，只用PIL生成静态图片序列
        
    def get_font(self, size=12):
        """获取字体，优先使用中文字体"""
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
            "arial.ttf"
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
        
        return ImageFont.load_default()
    
    def create_wheel_image(self, config, rotation_angle, current_result=""):
        """创建单个转盘图像 - 美观版本"""
        # 创建画布
        img_width = self.wheel_size + 40
        img_height = self.wheel_size + 60
        img = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        
        # 转盘中心
        center_x = img_width // 2
        center_y = (img_height - 20) // 2
        radius = self.wheel_size // 2
        
        # 绘制转盘扇形 <mcreference link="https://www.geeksforgeeks.org/python/python-pil-imagedraw-draw-pieslice/" index="3">3</mcreference>
        items = config["items"]
        colors = config["colors"]
        angle_per_item = 360 / len(items)
        
        # 绘制外圈阴影
        shadow_radius = radius + 3
        draw.ellipse(
            [center_x - shadow_radius, center_y - shadow_radius, 
             center_x + shadow_radius, center_y + shadow_radius],
            fill=(0, 0, 0, 30)
        )
        
        for i, (item, color) in enumerate(zip(items, colors)):
            start_angle = i * angle_per_item + rotation_angle
            end_angle = (i + 1) * angle_per_item + rotation_angle
            
            # 绘制扇形，使用更细的边框
            draw.pieslice(
                [center_x - radius, center_y - radius, center_x + radius, center_y + radius],
                start_angle, end_angle, fill=color, outline="#FFFFFF", width=1
            )
            
            # 绘制文字，去除背景色
            text_angle = math.radians(start_angle + angle_per_item / 2)
            text_radius = radius * 0.7
            text_x = center_x + text_radius * math.cos(text_angle)
            text_y = center_y + text_radius * math.sin(text_angle)
            
            font = self.get_font(9)
            
            # 计算文字边界框
            bbox = draw.textbbox((0, 0), item, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 直接绘制文字，使用白色描边效果
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        draw.text(
                            (text_x - text_width // 2 + dx, text_y - text_height // 2 + dy),
                            item, fill="#000000", font=font
                        )
            
            draw.text(
                (text_x - text_width // 2, text_y - text_height // 2),
                item, fill="#FFFFFF", font=font
            )
        
        # 绘制倒三角指针
        pointer_points = [
            (center_x - 8, center_y - radius - 5),  # 左上角
            (center_x + 8, center_y - radius - 5),  # 右上角
            (center_x, center_y - radius + 10)       # 底部尖角
        ]
        draw.polygon(pointer_points, fill="#FF4757", outline="#FFFFFF", width=2)
        
        # 绘制中心圆，使用渐变效果
        center_radius = 15
        draw.ellipse(
            [center_x - center_radius, center_y - center_radius, 
             center_x + center_radius, center_y + center_radius],
            fill="#2C2C54", outline="#FFFFFF", width=2
        )
        
        # 绘制内圈
        inner_radius = 8
        draw.ellipse(
            [center_x - inner_radius, center_y - inner_radius, 
             center_x + inner_radius, center_y + inner_radius],
            fill="#FF4757"
        )
        
        # 绘制标题
        title_font = self.get_font(12)
        title_bbox = draw.textbbox((0, 0), config["title"], font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(
            (center_x - title_width // 2, 5),
            config["title"], fill="#2C2C54", font=title_font
        )
        
        return img, current_result
    
    def get_result_at_angle(self, config, angle):
        """根据角度获取指针指向的结果"""
        items = config["items"]
        angle_per_item = 360 / len(items)
        
        # 标准化角度到0-360范围
        normalized_angle = angle % 360
        
        # 指针在顶部（270度位置），需要计算指针指向哪个扇形
        # 由于扇形是从0度开始绘制，指针在270度位置
        # 所以需要将角度调整为从指针位置开始计算
        pointer_angle = 270  # 指针在顶部
        relative_angle = (pointer_angle - normalized_angle) % 360
        
        # 计算指针指向的扇形索引
        item_index = int(relative_angle // angle_per_item)
        
        # 确保索引在有效范围内
        item_index = item_index % len(items)
        
        return items[item_index]
    
    def is_difficulty_valid_for_map(self, map_name, difficulty):
        """检查难度是否适用于指定地图"""
        if map_name in self.map_difficulty_constraints:
            return difficulty in self.map_difficulty_constraints[map_name]
        return True  # 如果地图不在约束中，默认允许所有难度
    
    def get_valid_difficulty_for_map(self, map_name):
        """为指定地图随机选择一个有效的难度"""
        if map_name in self.map_difficulty_constraints:
            valid_difficulties = self.map_difficulty_constraints[map_name]
            return random.choice(valid_difficulties)
        # 如果地图不在约束中，从所有难度中随机选择
        return random.choice(self.wheel_configs[1]["items"])
    
    def generate_roulette_gif(self):
        """生成转盘GIF动画（使用PIL生成帧序列）"""
        try:
            # 为每个转盘生成随机的最终角度
            final_angles = []
            final_results = []
            
            # 首先生成地图结果
            map_config = self.wheel_configs[0]  # 地图转盘
            map_angle = random.uniform(0, 360)
            final_angles.append(map_angle)
            map_result = self.get_result_at_angle(map_config, map_angle)
            final_results.append(map_result)
            
            # 根据地图结果生成兼容的难度
            difficulty_config = self.wheel_configs[1]  # 难度转盘
            valid_difficulty = self.get_valid_difficulty_for_map(map_result)
            
            # 计算难度对应的角度
            difficulty_items = difficulty_config["items"]
            difficulty_index = difficulty_items.index(valid_difficulty)
            angle_per_item = 360 / len(difficulty_items)
            # 计算指针指向该难度时的角度（考虑指针在270度位置）
            target_angle = (270 - (difficulty_index + 0.5) * angle_per_item) % 360
            final_angles.append(target_angle)
            final_results.append(valid_difficulty)
            
            # 为其他转盘生成随机角度
            for config in self.wheel_configs[2:]:
                # 生成随机的最终停止角度
                final_angle = random.uniform(0, 360)
                final_angles.append(final_angle)
                
                # 获取最终结果
                result = self.get_result_at_angle(config, final_angle)
                final_results.append(result)
            
            frames = []
            
            # 定义每个转盘的停止时间（帧数）
            stop_frames = [30, 35, 40, 45, 50, 55]  # 依次停止
            
            for frame in range(self.total_frames + 10):  # 多加10帧显示最终结果
                # 创建主画布，使用渐变背景
                canvas = Image.new('RGB', (self.canvas_width, self.canvas_height), '#F1F2F6')
                
                # 计算2行3列的紧凑布局，确保边距均匀
                col_spacing = self.wheel_spacing_x // 3  # 列间距
                row_spacing = self.wheel_spacing_y // 2  # 行间距
                
                wheel_positions = [
                    (self.margin, self.margin),   # 第一行第一列
                    (self.margin + self.wheel_size + col_spacing, self.margin),  # 第一行第二列
                    (self.margin + (self.wheel_size + col_spacing) * 2, self.margin),  # 第一行第三列
                    (self.margin, self.margin + self.wheel_size + row_spacing),  # 第二行第一列
                    (self.margin + self.wheel_size + col_spacing, self.margin + self.wheel_size + row_spacing), # 第二行第二列
                    (self.margin + (self.wheel_size + col_spacing) * 2, self.margin + self.wheel_size + row_spacing)  # 第二行第三列
                ]
                
                # 文字显示位置，位于转盘中心右上方一个转盘半径的位置
                text_positions = []
                for i, pos in enumerate(wheel_positions):
                    wheel_x, wheel_y = pos
                    # 转盘中心坐标
                    center_x = wheel_x + self.wheel_size // 2
                    center_y = wheel_y + self.wheel_size // 2
                    
                    # 计算右上方45度角位置，距离为一个转盘半径，然后向右偏移一个半径
                    radius = self.wheel_size // 2
                    import math
                    angle_rad = math.radians(-45)  # 右上方45度（负角度因为Y轴向下）
                    text_x = center_x + radius * math.cos(angle_rad) + radius  # 向右偏移一个半径
                    text_y = center_y + radius * math.sin(angle_rad)
                    
                    text_positions.append((int(text_x), int(text_y)))
                
                for i, (config, wheel_pos, text_pos, stop_frame, final_angle) in enumerate(zip(
                    self.wheel_configs, wheel_positions, text_positions, stop_frames, final_angles
                )):
                    if frame < stop_frame:
                        # 转盘还在转动
                        progress = frame / stop_frame
                        eased_progress = 1 - (1 - progress) ** 2  # 缓出效果
                        
                        # 计算当前角度（多转几圈再停到最终角度）
                        total_rotation = 720 + final_angle  # 转2圈加最终角度
                        current_angle = total_rotation * eased_progress
                        
                        # 获取当前指向的结果
                        current_result = self.get_result_at_angle(config, current_angle)
                    else:
                        # 转盘已停止
                        current_angle = final_angle
                        current_result = final_results[i]
                    
                    # 创建转盘图像
                    wheel_img, _ = self.create_wheel_image(config, current_angle, current_result)
                    
                    # 将转盘粘贴到主画布
                    canvas.paste(wheel_img, wheel_pos, wheel_img)
                    
                    # 在转盘旁边显示当前指向的内容
                    draw = ImageDraw.Draw(canvas)
                    result_font = self.get_font(14)
                    
                    # 绘制实时结果文字
                    result_text = f"→ {current_result}"
                    result_bbox = draw.textbbox((0, 0), result_text, font=result_font)
                    result_width = result_bbox[2] - result_bbox[0]
                    result_height = result_bbox[3] - result_bbox[1]
                    
                    # 使用计算好的文字位置，居中显示
                    text_x = text_pos[0] - result_width // 2
                    text_y = text_pos[1] - result_height // 2
                    
                    # 绘制文字背景
                    padding = 8
                    draw.rounded_rectangle(
                        [text_x - padding, text_y - padding,
                         text_x + result_width + padding, text_y + result_height + padding],
                        radius=5, fill="#2C2C54", outline="#FFFFFF", width=1
                    )
                    
                    # 绘制文字
                    draw.text((text_x, text_y), result_text, fill="#FFFFFF", font=result_font)
                
                frames.append(canvas)
            
            # 保存为GIF（使用PIL的save方法）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            gif_path = os.path.join(self.output_dir, f"roulette_{timestamp}.gif")
            
            # 使用PIL保存GIF
            frames[0].save(
                gif_path,
                save_all=True,
                append_images=frames[1:],
                duration=100,  # 每帧100ms
                loop=0
            )
            
            logger.info(f"转盘GIF已生成: {gif_path}")
            return gif_path, final_results
            
        except Exception as e:
            logger.error(f"生成转盘GIF失败: {e}")
            raise

def generate_roulette():
    """独立函数：生成转盘并返回结果"""
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_dir, "core", "output")
        
        # 创建转盘生成器
        roulette = RouletteWheel(output_dir)
        
        # 生成转盘GIF
        gif_path, results = roulette.generate_roulette_gif()
        
        # 构建结果消息
        result_message = "🎲 鼠鼠转盘结果 🎲\n\n"
        
        config_titles = [config["title"] for config in roulette.wheel_configs]
        
        for title, result in zip(config_titles, results):
            result_message += f"🎯 {title}: {result}\n"
        
        result_message += "\n🎮 祝你游戏愉快！"
        
        return {
            "success": True,
            "gif_path": gif_path,
            "results": results,
            "message": result_message
        }
        
    except Exception as e:
        logger.error(f"转盘生成失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"❌ 转盘生成失败: {str(e)}"
        }

if __name__ == "__main__":
    # 独立运行测试
    result = generate_roulette()
    if result["success"]:
        print("转盘生成成功！")
        print(f"GIF路径: {result['gif_path']}")
        print(f"结果: {result['results']}")
    else:
        print(f"转盘生成失败: {result['error']}")