import httpx
import asyncio
import json
import random
import os
import subprocess
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.message_components import At, Plain, Image
from astrbot.api import logger

class TouchiTools:
    def __init__(self, enable_touchi=True,enable_beauty_pic=True, cd=5):
        self.enable_touchi = enable_touchi
        self.enable_beauty_pic = enable_beauty_pic  # 新增：是否开启美图功能
        self.cd = cd
        self.last_usage = {}
        self.semaphore = asyncio.Semaphore(10)
        
        # 获取当前脚本所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 设置表情包目录路径
        self.biaoqing_dir = os.path.join(current_dir, "biaoqing")
        os.makedirs(self.biaoqing_dir, exist_ok=True)  # 确保目录存在
        
        # 设置与touchi.py一致的输出目录
        self.output_dir = os.path.join(current_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)  # 确保目录存在
        
        # 添加倍率属性
        self.multiplier = 1.0  # 默认倍率为1.0
        
        # 修改提示消息结构，包含原始时间
        self.safe_box_messages = [
            ("鼠鼠偷吃中...(预计{}min)", "touchi.png", 120),  # 120秒 = 2分钟
            ("鼠鼠猛攻中...(预计{}min)", "menggong.png", 60)   # 60秒 = 1分钟
        ]
        
        # 人物名称列表（用于随机选择）
        self.character_names = ["威龙", "老黑", "蜂衣", "红狼", "乌鲁鲁", "深蓝", "无名"]
    
    # 添加设置倍率的方法
    def set_multiplier(self, multiplier: float):
        if multiplier < 0.01 or multiplier > 100:
            return "倍率必须在0.01到100之间"
        
        self.multiplier = multiplier
        return f"鼠鼠冷却倍率已设置为 {multiplier} 倍！"
        
    async def fetch_touchi(self):
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("https://api.lolicon.app/setu/v2?r18=0")
            resp.raise_for_status()
            return resp.json()

    async def get_latest_safe_image(self):
        """获取output文件夹中最新的图片"""
        if not os.path.exists(self.output_dir):
            return None
            
        # 获取所有png文件并按修改时间排序
        image_files = [f for f in os.listdir(self.output_dir) if f.lower().endswith('.png')]
        if not image_files:
            return None
            
        # 按修改时间排序，最新的在前
        image_files.sort(key=lambda f: os.path.getmtime(os.path.join(self.output_dir, f)), reverse=True)
        return os.path.join(self.output_dir, image_files[0])

    async def get_touchi(self, event):
        if not self.enable_touchi:
            yield event.plain_result("盲盒功能已关闭")
            return
            
        user_id = event.get_sender_id()
        now = asyncio.get_event_loop().time()
        
        # 检查冷却时间
        if user_id in self.last_usage and (now - self.last_usage[user_id]) < self.cd:
            remaining_time = self.cd - (now - self.last_usage[user_id])
            yield event.plain_result(f"冷却中，请等待 {remaining_time:.1f} 秒后重试。")
            return
        
        # 生成随机数决定结果类型
        rand_num = random.random()
        
        if self.enable_beauty_pic and rand_num < 0.3: 
            async with self.semaphore:
                try:
                    data = await self.fetch_touchi()
                    if data['data']:
                        image_url = data['data'][0]['urls']['original']
                        character = random.choice(self.character_names)
                        
                        chain = [
                            At(qq=event.get_sender_id()),
                            Plain(f"🎉 恭喜开到{character}珍藏美图："),
                            Image.fromURL(image_url, size='small'),
                        ]
                        self.last_usage[user_id] = now
                        yield event.chain_result(chain)
                    else:
                        yield event.plain_result("没有找到图。")
                except httpx.HTTPStatusError as e:
                    yield event.plain_result(f"获取图时发生HTTP错误: {e.response.status_code}")
                except httpx.TimeoutException:
                    yield event.plain_result("获取图超时，请稍后重试。")
                except httpx.HTTPError as e:
                    yield event.plain_result(f"获取图时发生网络错误: {e}")
                except json.JSONDecodeError as e:
                    yield event.plain_result(f"解析JSON时发生错误: {e}")
        else:  # 偷吃
            # 随机选择一个提示消息模板、表情图片和原始等待时间
            message_template, image_name, original_wait_time = random.choice(self.safe_box_messages)

            # 应用倍率计算实际等待时间（除法）
            actual_wait_time = original_wait_time / self.multiplier
            
            # 计算分钟数（四舍五入到整数）
            minutes = round(actual_wait_time / 60)
            
            
            # 生成实际消息
            message = message_template.format(minutes)
            
            # 构建表情图片路径
            image_path = os.path.join(self.biaoqing_dir, image_name)
            
            # 确保图片文件存在
            if not os.path.exists(image_path):
                logger.warning(f"表情图片不存在: {image_path}")
                # 如果图片不存在，只发送文字消息
                yield event.plain_result(message)
            else:
                # 发送包含文字和表情图片的消息链
                chain = [
                    Plain(message),
                    Image.fromFileSystem(image_path),
                ]
                yield event.chain_result(chain)
            
            # 创建异步任务处理生成，传入实际等待时间
            asyncio.create_task(self.send_delayed_safe_box(event, actual_wait_time))
            
            # 更新冷却时间
            self.last_usage[user_id] = now

    async def send_delayed_safe_box(self, event, wait_time):
        """异步发送延迟的图片"""
        try:
            # 等待指定时间
            await asyncio.sleep(wait_time)
            
            # 运行touchi代码
            script_path = os.path.join(os.path.dirname(__file__), "touchi.py")
            subprocess.run(["python", script_path], check=True)
            
            # 获取最新生成的touchi图片
            safe_image_path = await self.get_latest_safe_image()
            
            if safe_image_path:
                # 使用 event.send 方法发送消息
                chain = MessageChain([
                    At(qq=event.get_sender_id()),
                    Plain("鼠鼠偷吃到了"),
                    Image.fromFileSystem(safe_image_path),
                ])
                await event.send(chain)
            else:
                await event.send(MessageChain([Plain("🎁 图片生成失败！")]))
                
        except Exception as e:
            logger.error(f"执行偷吃代码时出错: {e}")
            await event.send(MessageChain([Plain("🎁打开时出了点问题！")]))

    def set_cd(self, cd: int):
        if cd > 0:
            self.cd = cd
            return f"发图指令冷却时间已设置为 {cd} 秒。"
        else:
            return "冷却时间必须大于 0。"
