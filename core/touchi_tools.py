import httpx
import asyncio
import json
import random
import os
import time
import httpx
import aiosqlite  # Import the standard SQLite library
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.message_components import At, Plain, Image
from astrbot.api import logger
from .touchi import generate_safe_image, get_item_value

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
        
        self.character_names = ["威龙", "老黑", "蜂医", "红狼", "乌鲁鲁", "深蓝", "无名"]
    
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
        """将获得的物品添加到用户收藏中并更新仓库价值"""
        if not self.db_path or not placed_items:
            return
        
        try:
            total_value = 0
            async with aiosqlite.connect(self.db_path) as db:
                # 添加物品到收藏
                for placed in placed_items:
                    item = placed["item"]
                    item_name = os.path.splitext(os.path.basename(item["path"]))[0]
                    item_level = item["level"]
                    item_value = item.get("value", get_item_value(item_name))
                    total_value += item_value
                    
                    await db.execute(
                        "INSERT OR IGNORE INTO user_touchi_collection (user_id, item_name, item_level) VALUES (?, ?, ?)",
                        (user_id, item_name, item_level)
                    )
                
                # 更新用户经济数据
                await db.execute(
                    "INSERT OR IGNORE INTO user_economy (user_id) VALUES (?)",
                    (user_id,)
                )
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value + ? WHERE user_id = ?",
                    (total_value, user_id)
                )
                await db.commit()
            logger.info(f"用户 {user_id} 成功记录了 {len(placed_items)} 个物品到[collection.db]，总价值: {total_value}。")
        except Exception as e:
            logger.error(f"为用户 {user_id} 添加物品到数据库[collection.db]时出错: {e}")

    async def get_user_economy_data(self, user_id):
        """获取用户经济数据"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT warehouse_value, teqin_level, grid_size, menggong_active, menggong_end_time FROM user_economy WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                if result:
                    return {
                        "warehouse_value": result[0],
                        "teqin_level": result[1],
                        "grid_size": result[2],
                        "menggong_active": result[3],
                        "menggong_end_time": result[4]
                    }
                else:
                    # 创建新用户记录
                    await db.execute(
                        "INSERT INTO user_economy (user_id) VALUES (?)",
                        (user_id,)
                    )
                    await db.commit()
                    return {
                        "warehouse_value": 0,
                        "teqin_level": 0,
                        "grid_size": 4,
                        "menggong_active": 0,
                        "menggong_end_time": 0
                    }
        except Exception as e:
            logger.error(f"获取用户经济数据时出错: {e}")
            return None

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

    async def send_delayed_safe_box(self, event, wait_time, menggong_mode=False):
        """异步生成保险箱图片，发送并记录到数据库"""
        try:
            await asyncio.sleep(wait_time)
            
            user_id = event.get_sender_id()
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                await event.send(MessageChain([Plain("🎁获取用户数据失败！")]))
                return
            
            # 检查猛攻状态
            current_time = int(time.time())
            if economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]:
                menggong_mode = True
            
            loop = asyncio.get_running_loop()
            safe_image_path, placed_items = await loop.run_in_executor(
                None, generate_safe_image, menggong_mode, economy_data["grid_size"]
            )
            
            if safe_image_path and os.path.exists(safe_image_path):
                await self.add_items_to_collection(user_id, placed_items)
                
                # 计算总价值
                total_value = sum(item["item"].get("value", get_item_value(
                    os.path.splitext(os.path.basename(item["item"]["path"]))[0]
                )) for item in placed_items)
                
                message = "鼠鼠偷吃到了" if not menggong_mode else "鼠鼠猛攻获得了"
                chain = MessageChain([
                    At(qq=event.get_sender_id()),
                    Plain(f"{message}\n总价值: {total_value:,}"),
                    Image.fromFileSystem(safe_image_path),
                ])
                await event.send(chain)
            else:
                await event.send(MessageChain([Plain("🎁 图片生成失败！")]))
                
        except Exception as e:
            logger.error(f"执行偷吃代码或发送结果时出错: {e}")
            await event.send(MessageChain([Plain("🎁打开时出了点问题！")]))

    async def menggong_attack(self, event):
        """六套猛攻功能"""
        user_id = event.get_sender_id()
        
        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return
            
            # 检查仓库价值是否足够
            if economy_data["warehouse_value"] < 3000000:
                yield event.plain_result(f"仓库价值不足！当前价值: {economy_data['warehouse_value']:,}，需要: 3,000,000")
                return
            
            # 检查是否已经在猛攻状态
            current_time = int(time.time())
            if economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]:
                remaining_time = economy_data["menggong_end_time"] - current_time
                yield event.plain_result(f"猛攻状态进行中，剩余时间: {remaining_time // 60}分{remaining_time % 60}秒")
                return
            
            # 扣除仓库价值并激活猛攻状态
            menggong_end_time = current_time + 120  # 2分钟
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value - 3000000, menggong_active = 1, menggong_end_time = ? WHERE user_id = ?",
                    (menggong_end_time, user_id)
                )
                await db.commit()
            
            # 发送猛攻图片
            menggong_image_path = os.path.join(self.biaoqing_dir, "menggong.png")
            if os.path.exists(menggong_image_path):
                chain = [
                    At(qq=event.get_sender_id()),
                    Plain("🔥 六套猛攻激活！2分钟内提高红色和金色物品概率，不出现蓝色物品！\n消耗仓库价值: 3,000,000"),
                    Image.fromFileSystem(menggong_image_path)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result("🔥 六套猛攻激活！2分钟内提高红色和金色物品概率，不出现蓝色物品！\n消耗仓库价值: 3,000,000")
            
            # 2分钟后自动关闭猛攻状态
            asyncio.create_task(self._disable_menggong_after_delay(user_id, 120))
            
        except Exception as e:
            logger.error(f"六套猛攻功能出错: {e}")
            yield event.plain_result("六套猛攻功能出错，请重试")

    async def _disable_menggong_after_delay(self, user_id, delay):
        """延迟关闭猛攻状态"""
        try:
            await asyncio.sleep(delay)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET menggong_active = 0, menggong_end_time = 0 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
            logger.info(f"用户 {user_id} 的猛攻状态已自动关闭")
        except Exception as e:
            logger.error(f"关闭猛攻状态时出错: {e}")

    async def upgrade_teqin(self, event):
        """特勤处升级功能"""
        user_id = event.get_sender_id()
        
        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return
            
            current_level = economy_data["teqin_level"]
            
            # 升级费用和等级限制
            upgrade_costs = [640000, 3200000, 2560000]
            if current_level >= 3:
                yield event.plain_result("特勤处已达到最高等级（3级）！")
                return
            
            upgrade_cost = upgrade_costs[current_level]
            
            # 检查仓库价值是否足够
            if economy_data["warehouse_value"] < upgrade_cost:
                yield event.plain_result(f"仓库价值不足！当前价值: {economy_data['warehouse_value']:,}，升级到{current_level + 1}级需要: {upgrade_cost:,}")
                return
            
            # 执行升级
            new_level = current_level + 1
            new_grid_size = 4 + new_level  # 4->5->6->7
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value - ?, teqin_level = ?, grid_size = ? WHERE user_id = ?",
                    (upgrade_cost, new_level, new_grid_size, user_id)
                )
                await db.commit()
            
            yield event.plain_result(
                f"🎉 特勤处升级成功！\n"
                f"等级: {current_level} → {new_level}\n"
                f"格子大小: {economy_data['grid_size']}x{economy_data['grid_size']} → {new_grid_size}x{new_grid_size}\n"
                f"消耗价值: {upgrade_cost:,}\n"
                f"剩余价值: {economy_data['warehouse_value'] - upgrade_cost:,}"
            )
            
        except Exception as e:
            logger.error(f"特勤处升级功能出错: {e}")
            yield event.plain_result("特勤处升级功能出错，请重试")

    async def get_warehouse_info(self, event):
        """查看仓库价值和特勤处信息"""
        user_id = event.get_sender_id()
        
        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return
            
            # 检查猛攻状态
            current_time = int(time.time())
            menggong_status = ""
            if economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]:
                remaining_time = economy_data["menggong_end_time"] - current_time
                menggong_status = f"\n🔥 猛攻状态: 激活中 (剩余 {remaining_time // 60}分{remaining_time % 60}秒)"
            else:
                menggong_status = "\n🔥 猛攻状态: 未激活"
            
            # 下一级升级费用
            upgrade_costs = [640000, 3200000, 2560000]
            next_upgrade_info = ""
            if economy_data["teqin_level"] < 3:
                next_cost = upgrade_costs[economy_data["teqin_level"]]
                next_upgrade_info = f"\n📈 下级升级费用: {next_cost:,}"
            else:
                next_upgrade_info = "\n📈 已达最高等级"
            
            info_text = (
                f"💰 仓库价值: {economy_data['warehouse_value']:,}\n"
                f"🏢 特勤处等级: {economy_data['teqin_level']}级\n"
                f"📦 格子大小: {economy_data['grid_size']}x{economy_data['grid_size']}"
                f"{next_upgrade_info}"
                f"{menggong_status}"
            )
            
            yield event.plain_result(info_text)
            
        except Exception as e:
            logger.error(f"查看仓库信息功能出错: {e}")
            yield event.plain_result("查看仓库信息功能出错，请重试")
