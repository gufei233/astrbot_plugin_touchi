import httpx
import asyncio
import json
import random
import os
import aiosqlite  # Import the standard SQLite library
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.message_components import At, Plain, Image
from astrbot.api import logger
from .touchi import generate_safe_image

class TouchiTools:
    def __init__(self, enable_touchi=True, enable_beauty_pic=True, cd=5, db_path=None):
        self.enable_touchi = enable_touchi
        self.enable_beauty_pic = enable_beauty_pic
        self.cd = cd
        self.db_path = db_path # Path to the database file
        self.last_usage = {}
        self.semaphore = asyncio.Semaphore(10)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.biaoqing_dir = os.path.join(current_dir, "biaoqing")
        os.makedirs(self.biaoqing_dir, exist_ok=True)
        
        self.output_dir = os.path.join(current_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.multiplier = 1.0
        
        self.safe_box_messages = [
            ("鼠鼠偷吃中...(预计{}min)", "touchi.png", 120),
            ("鼠鼠猛攻中...(预计{}min)", "menggong.png", 60)
        ]
        
        self.character_names = ["威龙", "老黑", "蜂衣", "红狼", "乌鲁鲁", "深蓝", "无名"]
    
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

    async def add_items_to_collection(self, user_id, placed_items):
        """将获得的物品添加到用户收藏中"""
        if not self.db_path or not placed_items:
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for placed in placed_items:
                    item = placed["item"]
                    item_name = os.path.splitext(os.path.basename(item["path"]))[0]
                    item_level = item["level"]
                    await db.execute(
                        "INSERT OR IGNORE INTO user_touchi_collection (user_id, item_name, item_level) VALUES (?, ?, ?)",
                        (user_id, item_name, item_level)
                    )
                await db.commit()
            logger.info(f"用户 {user_id} 成功记录了 {len(placed_items)} 个物品到[collection.db]。")
        except Exception as e:
            logger.error(f"为用户 {user_id} 添加物品到数据库[collection.db]时出错: {e}")

    async def get_touchi(self, event):
        if not self.enable_touchi:
            yield event.plain_result("盲盒功能已关闭")
            return
            
        user_id = event.get_sender_id()
        now = asyncio.get_event_loop().time()
        
        if user_id in self.last_usage and (now - self.last_usage[user_id]) < self.cd:
            remaining_time = self.cd - (now - self.last_usage[user_id])
            yield event.plain_result(f"冷却中，请等待 {remaining_time:.1f} 秒后重试。")
            return
        
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
                except Exception as e:
                    yield event.plain_result(f"获取美图时发生错误: {e}")
        else:
            message_template, image_name, original_wait_time = random.choice(self.safe_box_messages)
            actual_wait_time = original_wait_time / self.multiplier
            minutes = round(actual_wait_time / 60)
            message = message_template.format(minutes)
            image_path = os.path.join(self.biaoqing_dir, image_name)
            
            if not os.path.exists(image_path):
                logger.warning(f"表情图片不存在: {image_path}")
                yield event.plain_result(message)
            else:
                chain = [Plain(message), Image.fromFileSystem(image_path)]
                yield event.chain_result(chain)
            
            asyncio.create_task(self.send_delayed_safe_box(event, actual_wait_time))
            self.last_usage[user_id] = now

    async def send_delayed_safe_box(self, event, wait_time):
        """异步生成保险箱图片，发送并记录到数据库"""
        try:
            await asyncio.sleep(wait_time)
            
            loop = asyncio.get_running_loop()
            safe_image_path, placed_items = await loop.run_in_executor(None, generate_safe_image)
            
            if safe_image_path and os.path.exists(safe_image_path):
                await self.add_items_to_collection(event.get_sender_id(), placed_items)
                
                chain = MessageChain([
                    At(qq=event.get_sender_id()),
                    Plain("鼠鼠偷吃到了"),
                    Image.fromFileSystem(safe_image_path),
                ])
                await event.send(chain)
            else:
                await event.send(MessageChain([Plain("🎁 图片生成失败！")]))
                
        except Exception as e:
            logger.error(f"执行偷吃代码或发送结果时出错: {e}")
            await event.send(MessageChain([Plain("🎁打开时出了点问题！")]))
