import httpx
import asyncio
import json
import random
import os
import time
import httpx
import aiosqlite  # Import the standard SQLite library
from astrbot.api.message_components import At, Plain, Image
from astrbot.api import logger

from .touchi import generate_safe_image, get_item_value

class TouchiTools:
    def __init__(self, enable_touchi=True, enable_beauty_pic=True, cd=5, db_path=None, enable_static_image=False,
                 experimental_custom_drop_rates=False, normal_mode_drop_rates=None, menggong_mode_drop_rates=None,
                 chixiao_system=None):
        self.enable_touchi = enable_touchi
        self.enable_beauty_pic = enable_beauty_pic
        self.cd = cd
        self.db_path = db_path # Path to the database file
        self.enable_static_image = enable_static_image
        self.experimental_custom_drop_rates = experimental_custom_drop_rates
        self.normal_mode_drop_rates = normal_mode_drop_rates or {"blue": 0.25, "purple": 0.42, "gold": 0.28, "red": 0.05}
        self.menggong_mode_drop_rates = menggong_mode_drop_rates or {"purple": 0.45, "gold": 0.45, "red": 0.10}
        self.chixiao_system = chixiao_system  # 赤枭系统
        self.last_usage = {}
        self.waiting_users = {}  # 记录正在等待的用户及其结束时间
        self.semaphore = asyncio.Semaphore(10)
        self.next_touchi_wait_multipliers = {}

        current_dir = os.path.dirname(os.path.abspath(__file__))

        self.biaoqing_dir = os.path.join(current_dir, "biaoqing")
        os.makedirs(self.biaoqing_dir, exist_ok=True)

        self.output_dir = os.path.join(current_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.multiplier = 1.0

        # 异步初始化倍率
        asyncio.create_task(self._load_multiplier())

        # 初始化概率事件系统
        from .touchi_events import TouchiEvents
        self.events = TouchiEvents(self.db_path, self.biaoqing_dir, chixiao_system=self.chixiao_system)

        self.safe_box_messages = [
            ("鼠鼠偷吃中...(预计{}min)", ["touchi1.gif", "touchi2.gif", "touchi3.gif", "touchi4.gif"], 120),
            ("鼠鼠猛攻中...(预计{}min)", ["menggong.gif", "menggong2.gif", "menggong3.gif"], 60)
        ]

        self.character_names = ["威龙", "老黑", "蜂医", "红狼", "乌鲁鲁", "深蓝", "无名"]

        # 自动偷吃相关
        self.auto_touchi_tasks = {}  # 存储用户的自动偷吃任务
        self.auto_touchi_data = {}   # 存储自动偷吃期间的数据
        self.nickname_cache = {}     # 缓存群成员昵称，格式: {group_id: {user_id: nickname}}
        self.cache_expire_time = {}  # 缓存过期时间

        # 检视功能相关
        self.jianshi_dir = os.path.join(current_dir, "jianshi")
        os.makedirs(self.jianshi_dir, exist_ok=True)

    def _is_auto_touchi_task_running(self, user_id):
        task = self.auto_touchi_tasks.get(user_id)
        if task and not task.done():
            return True
        if task:
            self.auto_touchi_tasks.pop(user_id, None)
        return False

    async def _clear_stale_auto_touchi_state(self, user_id):
        self.auto_touchi_tasks.pop(user_id, None)
        self.auto_touchi_data.pop(user_id, None)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_economy SET auto_touchi_active = 0, auto_touchi_start_time = 0 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()

    @staticmethod
    def _split_item_filename(filename_or_path):
        stem = os.path.splitext(os.path.basename(filename_or_path))[0]
        parts = stem.split('_')
        if len(parts) >= 4 and parts[-1].isdigit():
            return '_'.join(parts[:-1]), int(parts[-1]), stem
        return stem, None, stem

    async def _load_multiplier(self):
        """从数据库加载冷却倍率"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT config_value FROM system_config WHERE config_key = 'touchi_cooldown_multiplier'"
                )
                result = await cursor.fetchone()
                if result:
                    self.multiplier = float(result[0])
                    logger.info(f"从数据库加载冷却倍率: {self.multiplier}")
                else:
                    # 如果没有配置，插入默认值
                    await db.execute(
                        "INSERT OR IGNORE INTO system_config (config_key, config_value) VALUES ('touchi_cooldown_multiplier', '1.0')"
                    )
                    await db.commit()
                    logger.info("冷却倍率配置不存在，使用默认值 1.0")
        except Exception as e:
            logger.error(f"加载冷却倍率时出错: {e}")
            self.multiplier = 1.0  # 出错时使用默认值

    async def set_multiplier(self, multiplier: float):
        if multiplier < 0.01 or multiplier > 100:
            return "倍率必须在0.01到100之间"

        try:
            # 保存到数据库
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO system_config (config_key, config_value) VALUES ('touchi_cooldown_multiplier', ?)",
                    (str(multiplier),)
                )
                await db.commit()

            # 更新内存中的值
            self.multiplier = multiplier
            logger.info(f"冷却倍率已更新并保存到数据库: {multiplier}")
            return f"鼠鼠冷却倍率已设置为 {multiplier} 倍！\n💾 设置已持久化保存"
        except Exception as e:
            logger.error(f"保存冷却倍率时出错: {e}")
            return f"保存冷却倍率失败: {str(e)}"

    async def clear_user_data(self, user_id=None):
        """清除用户数据（管理员功能）"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if user_id:
                    # 清除指定用户数据
                    await db.execute("DELETE FROM user_touchi_collection WHERE user_id = ?", (user_id,))
                    await db.execute("DELETE FROM user_economy WHERE user_id = ?", (user_id,))
                    await db.commit()
                    return f"已清除用户 {user_id} 的所有数据"
                else:
                    # 清除所有用户数据
                    await db.execute("DELETE FROM user_touchi_collection")
                    await db.execute("DELETE FROM user_economy")
                    await db.commit()
                    return "已清除所有用户数据"
        except Exception as e:
            logger.error(f"清除用户数据时出错: {e}")
            return "清除数据失败，请重试"

    async def _get_group_member_nicknames(self, event, group_id: str):
        """获取群成员昵称映射，带缓存机制"""
        current_time = time.time()

        # 检查缓存是否有效（10分钟过期）
        if (group_id in self.nickname_cache and
            group_id in self.cache_expire_time and
            current_time < self.cache_expire_time[group_id]):
            return self.nickname_cache[group_id]

        nickname_map = {}

        try:
            # 直接使用event.bot获取群成员列表
            members = await event.bot.get_group_member_list(group_id=int(group_id))

            # 创建昵称映射字典
            for member in members:
                user_id = str(member['user_id'])
                nickname = member.get('card') or member.get('nickname') or f"用户{user_id[:6]}"
                nickname_map[user_id] = nickname

            # 更新缓存
            self.nickname_cache[group_id] = nickname_map
            self.cache_expire_time[group_id] = current_time + 600  # 10分钟后过期

            logger.info(f"成功获取群{group_id}的{len(nickname_map)}个成员昵称")

        except Exception as e:
            logger.error(f"获取群成员信息失败: {str(e)}")

        return nickname_map

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
            items_for_jianshi = []

            async with aiosqlite.connect(self.db_path) as db:
                # 添加物品到收藏
                for placed in placed_items:
                    item = placed["item"]
                    item_name = os.path.splitext(os.path.basename(item["path"]))[0]
                    item_level = item["level"]
                    item_value = item.get("value", get_item_value(item_name))
                    total_value += item_value

                    # 提取物品的唯一标识（最后一个下划线后的部分）
                    parts = item_name.split('_')
                    if len(parts) >= 3:
                        unique_id = parts[-1]  # 获取最后一部分作为唯一标识
                        items_for_jianshi.append({
                            'item_name': item_name,
                            'unique_id': unique_id,
                            'item_level': item_level
                        })

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

                # 记录最后一次偷吃的物品（用于检视功能）
                if items_for_jianshi:
                    import json
                    items_json = json.dumps(items_for_jianshi)
                    await db.execute(
                        "INSERT OR REPLACE INTO user_last_touchi (user_id, items_json, jianshi_index) VALUES (?, ?, 0)",
                        (user_id, items_json)
                    )

                await db.commit()
            logger.info(f"用户 {user_id} 成功记录了 {len(placed_items)} 个物品到[collection.db]，总价值: {total_value}。")
        except Exception as e:
            logger.error(f"为用户 {user_id} 添加物品到数据库[collection.db]时出错: {e}")

    async def add_items_to_collection_without_value_update(self, user_id, placed_items):
        """将获得的物品添加到用户收藏中但不更新仓库价值（用于追缴事件）"""
        if not self.db_path or not placed_items:
            return

        try:
            items_for_jianshi = []

            async with aiosqlite.connect(self.db_path) as db:
                # 添加物品到收藏
                for placed in placed_items:
                    item = placed["item"]
                    item_name = os.path.splitext(os.path.basename(item["path"]))[0]
                    item_level = item["level"]

                    # 提取物品的唯一标识（最后一个下划线后的部分）
                    parts = item_name.split('_')
                    if len(parts) >= 3:
                        unique_id = parts[-1]  # 获取最后一部分作为唯一标识
                        items_for_jianshi.append({
                            'item_name': item_name,
                            'unique_id': unique_id,
                            'item_level': item_level
                        })

                    await db.execute(
                        "INSERT OR IGNORE INTO user_touchi_collection (user_id, item_name, item_level) VALUES (?, ?, ?)",
                        (user_id, item_name, item_level)
                    )

                # 记录最后一次偷吃的物品（用于检视功能）
                if items_for_jianshi:
                    import json
                    items_json = json.dumps(items_for_jianshi)
                    await db.execute(
                        "INSERT OR REPLACE INTO user_last_touchi (user_id, items_json, jianshi_index) VALUES (?, ?, 0)",
                        (user_id, items_json)
                    )

                await db.commit()
            logger.info(f"用户 {user_id} 成功记录了 {len(placed_items)} 个物品到[collection.db]（追缴事件，不更新价值）。")
        except Exception as e:
            logger.error(f"为用户 {user_id} 添加物品到数据库[collection.db]时出错: {e}")

    async def _add_warehouse_value(self, user_id, amount):
        if not self.db_path or not user_id or amount <= 0:
            return

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO user_economy (user_id) VALUES (?)",
                    (user_id,)
                )
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to add warehouse value for user {user_id}: {e}")

    async def get_user_economy_data(self, user_id):
        """获取用户经济数据"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT warehouse_value, teqin_level, grid_size, menggong_active, menggong_end_time, auto_touchi_active, auto_touchi_start_time FROM user_economy WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()
                if result:
                    return {
                        "warehouse_value": result[0],
                        "teqin_level": result[1],
                        "grid_size": result[2],
                        "menggong_active": result[3],
                        "menggong_end_time": result[4],
                        "auto_touchi_active": result[5],
                        "auto_touchi_start_time": result[6]
                    }
                else:
                    # 获取系统配置的基础等级
                    config_cursor = await db.execute(
                        "SELECT config_value FROM system_config WHERE config_key = 'base_teqin_level'"
                    )
                    config_result = await config_cursor.fetchone()
                    base_level = int(config_result[0]) if config_result else 0

                    # 计算对应的grid_size
                    if base_level == 0:
                        base_grid_size = 2
                    else:
                        base_grid_size = 2 + base_level

                    # 创建新用户记录
                    await db.execute(
                        "INSERT INTO user_economy (user_id, teqin_level, grid_size) VALUES (?, ?, ?)",
                        (user_id, base_level, base_grid_size)
                    )
                    await db.commit()
                    return {
                        "warehouse_value": 0,
                        "teqin_level": base_level,
                        "grid_size": base_grid_size,
                        "menggong_active": 0,
                        "menggong_end_time": 0,
                        "auto_touchi_active": 0,
                        "auto_touchi_start_time": 0
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

        # 检查用户是否在自动偷吃状态，如果是则不允许手动偷吃
        economy_data = await self.get_user_economy_data(user_id)
        if economy_data and economy_data["auto_touchi_active"]:
            if self._is_auto_touchi_task_running(user_id):
                yield event.plain_result("自动偷吃进行中，无法手动偷吃。请先关闭自动偷吃。")
                return
            await self._clear_stale_auto_touchi_state(user_id)
            economy_data["auto_touchi_active"] = 0
            logger.warning(f"用户 {user_id} 的自动偷吃状态存在但后台任务不存在，已自动清理")

        # 检查用户是否在等待状态
        if user_id in self.waiting_users:
            end_time = self.waiting_users[user_id]
            remaining_time = end_time - now
            if remaining_time > 0:
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)
                if minutes > 0:
                    yield event.plain_result(f"鼠鼠还在偷吃中，请等待 {minutes}分{seconds}秒")
                else:
                    yield event.plain_result(f"鼠鼠还在偷吃中，请等待 {seconds}秒")
                return
            else:
                # 等待时间已过，清除等待状态
                del self.waiting_users[user_id]

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
                        yield event.chain_result(chain)
                    else:
                        yield event.plain_result("没有找到图。")
                except Exception as e:
                    yield event.plain_result(f"获取美图时发生错误: {e}")
        else:
            message_template, image_name, original_wait_time = random.choice(self.safe_box_messages)

            # 添加0.6-1.4倍的时间波动
            time_multiplier = random.uniform(0.6, 1.4)
            next_wait_multiplier = self.next_touchi_wait_multipliers.pop(user_id, 1.0)
            actual_wait_time = (original_wait_time * time_multiplier * next_wait_multiplier) / self.multiplier
            minutes = int(actual_wait_time // 60)
            seconds = int(actual_wait_time % 60)

            # 根据时间长度动态生成时间显示
            if minutes > 0:
                time_display = f"{minutes}分{seconds}秒"
            else:
                time_display = f"{seconds}秒"

            # 替换消息模板中的时间占位符
            message = message_template.replace("(预计{}min)", f"(预计{time_display})")

            # 将时间倍率传递给后续处理，用于影响爆率
            setattr(event, '_time_multiplier', time_multiplier)

            # 处理图片名称，如果是列表则随机选择一个
            if isinstance(image_name, list):
                selected_image = random.choice(image_name)
            else:
                selected_image = image_name

            image_path = os.path.join(self.biaoqing_dir, selected_image)

            if not os.path.exists(image_path):
                logger.warning(f"表情图片不存在: {image_path}")
                yield event.plain_result(message)
            else:
                chain = [
                    Plain(message),
                    Image.fromFileSystem(image_path)
                ]
                yield event.chain_result(chain)

            # 记录用户等待结束时间
            self.waiting_users[user_id] = now + actual_wait_time

            result, delayed_event_message = await self.send_delayed_safe_box(
                event, actual_wait_time, user_id, time_multiplier=time_multiplier
            )
            if result:

                # 如果有事件触发，先发送事件消息
                if delayed_event_message:
                    yield event.chain_result(delayed_event_message)

                # 发送偷吃结果
                if result['success']:
                    if result['image_path']:
                        chain = [
                            At(qq=event.get_sender_id()),
                            Plain(f"\n{result['message']}"),
                            Image.fromFileSystem(result['image_path']),
                        ]
                        yield event.chain_result(chain)
                    else:
                        chain = [
                            At(qq=event.get_sender_id()),
                            Plain(f"\n{result['message']}")
                        ]
                        yield event.chain_result(chain)
                else:
                    chain = [
                        At(qq=event.get_sender_id()),
                        Plain(f"\n{result['message']}")
                    ]
                    yield event.chain_result(chain)

    async def send_delayed_safe_box(self, event, wait_time, user_id=None, menggong_mode=False, time_multiplier=1.0):
        """异步生成保险箱图片，发送并记录到数据库"""
        try:
            await asyncio.sleep(wait_time)

            if user_id is None:
                user_id = event.get_sender_id()

            # 清除等待状态
            if user_id in self.waiting_users:
                del self.waiting_users[user_id]
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                return None, None

            # 检查猛攻状态
            current_time = int(time.time())
            if economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]:
                menggong_mode = True

            loop = asyncio.get_running_loop()

            # 默认使用用户当前的格子大小
            used_grid_size = economy_data["grid_size"]

            # 检查是否需要使用特殊模式（系统补偿局事件使用六套模式概率）
            use_menggong_probability = menggong_mode

            # 传递自定义概率参数
            custom_normal = self.normal_mode_drop_rates if self.experimental_custom_drop_rates else None
            custom_menggong = self.menggong_mode_drop_rates if self.experimental_custom_drop_rates else None
            delayed_event_message = None

            safe_image_path, placed_items = await loop.run_in_executor(
                None, generate_safe_image, use_menggong_probability, used_grid_size, time_multiplier, 0.7, False, self.enable_static_image,
                custom_normal, custom_menggong
            )

            if not safe_image_path or not os.path.exists(safe_image_path):
                return {
                    'success': False,
                    'message': "🎁打开时出了点问题！",
                    'image_path': None,
                    'has_event': False
                }, None

            # 计算总价值
            total_value = sum(item["item"].get("value", get_item_value(
                os.path.splitext(os.path.basename(item["item"]["path"]))[0]
            )) for item in placed_items)

            # 检查概率事件（传递猛攻状态）
            event_triggered, event_type, final_items, final_value, event_message, cooldown_multiplier, golden_item_path, event_emoji_path = await self.events.check_random_events(
                event, user_id, placed_items, total_value, is_menggong_active=menggong_mode
            )
            # 如果触发事件，先发送事件消息
            if event_triggered and event_message:
                # 发送事件消息（文字+表情）
                event_chain = []
                event_chain.append(At(qq=event.get_sender_id()))
                event_chain.append(Plain(f"\n{event_message}"))

                if event_emoji_path and os.path.exists(event_emoji_path):
                    event_chain.append(Image.fromFileSystem(event_emoji_path))

                delayed_event_message = event_chain

                # 如果触发系统补偿局事件，需要重新生成图片使用六套模式概率
                if event_triggered and event_type == "system_compensation":
                    # 重新生成图片，使用六套模式概率
                    custom_menggong = self.menggong_mode_drop_rates if self.experimental_custom_drop_rates else None
                    safe_image_path, placed_items = await loop.run_in_executor(
                        None, generate_safe_image, True, used_grid_size, time_multiplier, 0.7, False, self.enable_static_image,
                        None, custom_menggong
                    )

                    # 重新计算总价值
                    final_value = sum(item["item"].get("value", get_item_value(
                        os.path.splitext(os.path.basename(item["item"]["path"]))[0]
                    )) for item in placed_items)
                    final_items = placed_items

                # 如果触发丢包撤离事件，需要重新生成图片只显示小物品
                elif event_triggered and event_type == "hunted_escape":
                    # 使用过滤后的物品重新生成图片
                    def generate_with_filtered_items():
                        from .touchi import load_items, create_safe_layout, render_safe_layout_gif, get_highest_level, load_expressions
                        from PIL import Image
                        import os
                        from datetime import datetime

                        # 加载所有可用物品
                        all_items = load_items()
                        if not all_items:
                            return None, []

                        # 创建包含过滤后物品的特定物品列表
                        specific_items = []

                        # 添加过滤后的物品
                        for filtered_item in final_items:
                            item_name = filtered_item["item"]["base_name"]
                            item_level = filtered_item["item"]["level"]
                            for item in all_items:
                                if item["base_name"] == item_name and item["level"] == item_level:
                                    specific_items.append(item)
                                    break

                        # 使用当前格子大小重新布局
                        from .touchi import place_items
                        placed_items_new = place_items(specific_items, used_grid_size, used_grid_size, used_grid_size)

                        # 生成图片 - 修复返回值接收
                        result = render_safe_layout_gif(placed_items_new, 0, 0, used_grid_size, used_grid_size, used_grid_size)
                        if not result or not result[0]:
                            return None, []

                        # 正确接收返回值：frames 和 total_frames
                        safe_frames, total_frames = result

                        # 加载表情图片
                        expressions = load_expressions()
                        if not expressions:
                            return None, []

                        highest_level = get_highest_level(placed_items_new)
                        eating_path = expressions.get("eating")
                        expression_map = {"gold": "happy", "red": "eat"}
                        final_expression = expression_map.get(highest_level, "cry")
                        final_expr_path = expressions.get(final_expression)

                        if not eating_path or not final_expr_path:
                            return None, []

                        # 生成最终图片
                        expression_size = used_grid_size * 100

                        # 加载eating.gif帧
                        eating_frames = []
                        with Image.open(eating_path) as eating_gif:
                            for frame_idx in range(eating_gif.n_frames):
                                eating_gif.seek(frame_idx)
                                eating_frame = eating_gif.convert("RGBA")
                                eating_frame = eating_frame.resize((expression_size, expression_size), Image.LANCZOS)
                                eating_frames.append(eating_frame.copy())

                        # 加载最终表情
                        with Image.open(final_expr_path).convert("RGBA") as final_expr_img:
                            final_expr_img = final_expr_img.resize((expression_size, expression_size), Image.LANCZOS)

                            # 生成最终帧
                            final_frames = []
                            for frame_idx, safe_frame in enumerate(safe_frames):
                                # 修复：检查 safe_frame 是否是列表，如果是则取第一帧
                                if isinstance(safe_frame, list):
                                    if safe_frame:
                                        safe_frame = safe_frame[0]
                                    else:
                                        continue

                                final_img = Image.new("RGB", (expression_size + safe_frame.width, safe_frame.height), (50, 50, 50))

                                if frame_idx == 0:
                                    current_expr = final_expr_img
                                else:
                                    eating_frame_idx = (frame_idx - 1) % len(eating_frames)
                                    current_expr = eating_frames[eating_frame_idx]

                                if current_expr.mode == 'RGBA':
                                    final_img.paste(current_expr, (0, 0), current_expr)
                                else:
                                    final_img.paste(current_expr, (0, 0))

                                final_img.paste(safe_frame, (expression_size, 0))

                                # 应用缩放
                                new_width = int(final_img.width * 0.7)
                                new_height = int(final_img.height * 0.7)
                                final_img = final_img.resize((new_width, new_height), Image.LANCZOS)

                                final_frames.append(final_img)

                        # 保存GIF
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        from .touchi import output_dir
                        output_path = os.path.join(output_dir, f"safe_{timestamp}.gif")

                        if final_frames:
                            final_frames[0].save(
                                output_path,
                                save_all=True,
                                append_images=final_frames[1:],
                                duration=150,
                                loop=0
                            )
                            return output_path, placed_items_new
                        else:
                            return None, placed_items_new

                    try:
                        safe_image_path, placed_items = await loop.run_in_executor(None, generate_with_filtered_items)
                    except Exception as e:
                        logger.error(f"重新生成丢包撤离事件图片时出错: {e}")
                        # 如果重新生成失败，使用原始图片
                        pass

                # 如果路人鼠鼠事件触发且有金色物品，添加金色物品并重新生成图片
                if golden_item_path and event_type == "passerby_mouse":
                    # 添加金色物品到物品列表开头，使用正确的格式
                    golden_base_name, golden_price, golden_item_name = self._split_item_filename(golden_item_path)
                    golden_item_value = golden_price if golden_price is not None else get_item_value(golden_base_name)
                    golden_item = {
                        "item": {
                            "name": golden_item_name,
                            "path": golden_item_path,
                            "level": "gold",
                            "base_name": golden_base_name,
                            "value": golden_item_value
                        }
                    }
                    # 将金色物品添加到final_items开头
                    final_items.insert(0, golden_item)

                    # 使用最大格子重新生成图片，创建一个特殊的生成函数
                    def generate_with_specific_items():
                        from .touchi import load_items, create_safe_layout, render_safe_layout_gif, get_highest_level, load_expressions
                        from PIL import Image
                        import os
                        from datetime import datetime

                        # 加载所有可用物品
                        all_items = load_items()
                        if not all_items:
                            return None, []

                        # 创建包含金色物品的特定物品列表
                        specific_items = []

                        # 添加金色物品
                        for item in all_items:
                            if item["base_name"] == golden_base_name and item["level"] == "gold":
                                specific_items.append(item)
                                break

                        # 添加其他已放置的物品
                        for placed_item in placed_items:
                            item_name = placed_item["item"]["base_name"]
                            item_level = placed_item["item"]["level"]
                            for item in all_items:
                                if item["base_name"] == item_name and item["level"] == item_level:
                                    specific_items.append(item)
                                    break

                        # 使用最大格子(7x7)重新布局
                        from .touchi import place_items
                        placed_items_new = place_items(specific_items, 7, 7, 7)

                        # 生成图片
                        result = render_safe_layout_gif(placed_items_new, 0, 0, 7, 7, 7)
                        if not result or not result[0]:
                            return None, []

                        # 正确接收返回值：frames 和 total_frames
                        safe_frames, total_frames = result

                        # 加载表情图片
                        expressions = load_expressions()
                        if not expressions:
                            return None, []

                        highest_level = get_highest_level(placed_items_new)
                        eating_path = expressions.get("eating")
                        expression_map = {"gold": "happy", "red": "eat"}
                        final_expression = expression_map.get(highest_level, "cry")
                        final_expr_path = expressions.get(final_expression)

                        if not eating_path or not final_expr_path:
                            return None, []

                        # 生成最终图片
                        expression_size = 7 * 100  # 7x7格子

                        # 加载eating.gif帧
                        eating_frames = []
                        with Image.open(eating_path) as eating_gif:
                            for frame_idx in range(eating_gif.n_frames):
                                eating_gif.seek(frame_idx)
                                eating_frame = eating_gif.convert("RGBA")
                                eating_frame = eating_frame.resize((expression_size, expression_size), Image.LANCZOS)
                                eating_frames.append(eating_frame.copy())

                        # 加载最终表情
                        with Image.open(final_expr_path).convert("RGBA") as final_expr_img:
                            final_expr_img = final_expr_img.resize((expression_size, expression_size), Image.LANCZOS)

                            # 生成最终帧
                            final_frames = []
                            for frame_idx, safe_frame in enumerate(safe_frames):
                                # 修复：检查 safe_frame 是否是列表，如果是则取第一帧
                                if isinstance(safe_frame, list):
                                    if safe_frame:
                                        safe_frame = safe_frame[0]
                                    else:
                                        continue

                                final_img = Image.new("RGB", (expression_size + safe_frame.width, safe_frame.height), (50, 50, 50))

                                if frame_idx == 0:
                                    current_expr = final_expr_img
                                else:
                                    eating_frame_idx = (frame_idx - 1) % len(eating_frames)
                                    current_expr = eating_frames[eating_frame_idx]

                                if current_expr.mode == 'RGBA':
                                    final_img.paste(current_expr, (0, 0), current_expr)
                                else:
                                    final_img.paste(current_expr, (0, 0))

                                final_img.paste(safe_frame, (expression_size, 0))

                                # 应用缩放
                                new_width = int(final_img.width * 0.7)
                                new_height = int(final_img.height * 0.7)
                                final_img = final_img.resize((new_width, new_height), Image.LANCZOS)

                                final_frames.append(final_img)

                        # 保存GIF
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        from .touchi import output_dir
                        output_path = os.path.join(output_dir, f"safe_{timestamp}.gif")

                        if final_frames:
                            final_frames[0].save(
                                output_path,
                                save_all=True,
                                append_images=final_frames[1:],
                                duration=150,
                                loop=0
                            )
                            return output_path, placed_items_new
                        else:
                            return None, placed_items_new

                    try:
                        safe_image_path, placed_items = await loop.run_in_executor(None, generate_with_specific_items)
                    except Exception as e:
                        logger.error(f"重新生成路人鼠鼠事件图片时出错: {e}")
                        # 如果重新生成失败，使用原始图片
                        pass

                    # 重新计算总价值（包含金色物品）
                    final_value = 0
                    for item in final_items:
                        if "item" in item:
                            # 标准格式的物品
                            item_data = item["item"]
                            item_name = os.path.splitext(os.path.basename(item_data["path"]))[0]
                            item_value = item_data.get("value", get_item_value(item_name))
                        else:
                            # 兼容旧格式
                            item_name = os.path.splitext(os.path.basename(item.get("image_path", item.get("path", ""))))[0]
                            item_value = item.get("value", get_item_value(item_name))
                        final_value += item_value

                # Persist the event outcome exactly once.
                settled_value = final_value
                chixiao_loot_value = 0
                chixiao_reward_value = 0
                if event_type == "genius_fine":
                    await self.add_items_to_collection_without_value_update(user_id, final_items)
                elif event_type == "genius_kick":
                    pass
                elif event_type == "chixiao_battle":
                    chixiao_reward_value = final_value
                    if chixiao_reward_value > 0:
                        chixiao_loot_value = total_value
                        await self.add_items_to_collection(user_id, placed_items)
                        await self._add_warehouse_value(user_id, chixiao_reward_value)
                    settled_value = chixiao_loot_value + chixiao_reward_value
                else:
                    await self.add_items_to_collection(user_id, final_items)

                if cooldown_multiplier and cooldown_multiplier != 1.0:
                    self.next_touchi_wait_multipliers[user_id] = cooldown_multiplier
                    # Store the multiplier for the next safe-box wait.

                # 构建基础消息
                message = "鼠鼠偷吃到了" if not menggong_mode else "鼠鼠猛攻获得了"
                base_message = f"{message}\n总价值: {final_value:,}"


                # 检查是否触发洲了个洲游戏
                if event_type == "chixiao_battle" and chixiao_reward_value > 0:
                    base_message = (
                        f"{message}\n"
                        f"\u672c\u6b21\u7269\u54c1\u4ef7\u503c: {chixiao_loot_value:,}\n"
                        f"\u8d64\u9704\u5956\u52b1: {chixiao_reward_value:,}\n"
                        f"\u603b\u4ef7\u503c: {settled_value:,}"
                    )

                zhou_triggered = False
                zhou_message = ""
                if random.random() < 0.02:  # 2%概率
                    zhou_triggered = True
                    zhou_message = "\n\n🎮 特殊事件触发！洲了个洲游戏开始！\n💰 游戏获胜可获得100万哈夫币奖励！\n📝 使用 '洲了个洲' 指令开始游戏"

                    # 记录触发事件到数据库（用于后续奖励发放）
                    try:
                        async with aiosqlite.connect(self.db_path) as db:
                            # 创建洲游戏触发记录表（如果不存在）
                            await db.execute("""
                                CREATE TABLE IF NOT EXISTS zhou_trigger_events (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    user_id TEXT NOT NULL,
                                    trigger_time INTEGER NOT NULL,
                                    reward_claimed INTEGER DEFAULT 0
                                )
                            """)

                            # 记录触发事件
                            await db.execute(
                                "INSERT INTO zhou_trigger_events (user_id, trigger_time) VALUES (?, ?)",
                                (user_id, int(time.time()))
                            )
                            await db.commit()
                    except Exception as e:
                        logger.error(f"记录洲游戏触发事件时出错: {e}")

                # 构建最终消息
                final_message = base_message
                if event_triggered:
                    # 如果有赤枢对抗事件，消息已经在事件中发送了，不需要额外添加
                    if event_type == "chixiao_battle":
                        # 赤枢对抗：物品已添加到收藏（价值为0），不需要额外处理
                        pass
                    else:
                        final_message += f"\n{event_message}"

                if zhou_triggered:
                    final_message += zhou_message

                return {
                    'success': True,
                    'message': final_message,
                    'image_path': safe_image_path if safe_image_path and os.path.exists(safe_image_path) else None,
                    'combined': True,
                    'zhou_triggered': zhou_triggered,
                    'has_event': event_triggered  # 标记是否有事件触发
                }, delayed_event_message
            else:
               # 无事件：自己拼消息
               prefix = "鼠鼠猛攻获得了" if menggong_mode else "鼠鼠偷吃到了"
               final_message = f"{prefix}\n总价值: {final_value:,}"

               # 🔧 修复：确保无事件时也更新仓库价值
               await self.add_items_to_collection(user_id, placed_items)

               # 洲了个洲彩蛋（2%概率）
               if random.random() < 0.02:
                   final_message += "\n\n🎮 特殊事件触发！洲了个洲游戏开始！\n💰 游戏获胜可获得100万哈夫币奖励！\n📝 使用 '洲了个洲' 指令开始游戏"
                   try:
                       async with aiosqlite.connect(self.db_path) as db:
                           await db.execute("""
                               CREATE TABLE IF NOT EXISTS zhou_trigger_events (
                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                   user_id TEXT NOT NULL,
                                   trigger_time INTEGER NOT NULL,
                                   reward_claimed INTEGER DEFAULT 0
                               )
                           """)
                           await db.execute(
                               "INSERT INTO zhou_trigger_events (user_id, trigger_time) VALUES (?, ?)",
                               (user_id, int(time.time()))
                           )
                           await db.commit()
                   except Exception as e:
                       logger.error(f"记录洲游戏触发事件时出错: {e}")

               return {
                   'success': True,
                   'message': final_message,
                   'image_path': safe_image_path if safe_image_path and os.path.exists(safe_image_path) else None,
                   'has_event': False
               }, None

        except Exception as e:
            logger.error(f"执行偷吃代码或发送结果时出错: {e}")
            return {
                'success': False,
                'message': "🎁打开时出了点问题！",
                'image_path': None,
                'has_event': False
            }, None

    async def menggong_attack(self, event, custom_duration=None):
        """六套猛攻功能"""
        user_id = event.get_sender_id()

        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return

            # 检查仓库价值是否足够
            if economy_data["warehouse_value"] < 3000000:
                yield event.plain_result(f"哈夫币不足！当前: {economy_data['warehouse_value']:,}，需要: 3,000,000")
                return

            # 检查是否已经在猛攻状态
            current_time = int(time.time())
            if economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]:
                remaining_time = economy_data["menggong_end_time"] - current_time
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)
                if minutes > 0:
                    yield event.plain_result(f"刘涛状态进行中，剩余时间: {minutes}分{seconds}秒")
                else:
                    yield event.plain_result(f"刘涛状态进行中，剩余时间: {seconds}秒")
                return

            # 获取时间倍率
            time_multiplier = await self.get_menggong_time_multiplier()

            # 使用自定义时长或默认2分钟，然后应用倍率
            base_duration = custom_duration * 60 if custom_duration else 120
            duration_seconds = int(base_duration * time_multiplier)
            menggong_end_time = current_time + duration_seconds

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value - 3000000, menggong_active = 1, menggong_end_time = ? WHERE user_id = ?",
                    (menggong_end_time, user_id)
                )
                await db.commit()

            # 发送猛攻消息和图片
            duration_minutes = duration_seconds // 60
            duration_remainder = duration_seconds % 60
            if duration_remainder > 0:
                duration_text = f"{duration_minutes}分{duration_remainder}秒"
            else:
                duration_text = f"{duration_minutes}分钟"
            base_message = f"🔥 六套猛攻激活！{duration_text}内提高红色和金色物品概率，不出现蓝色物品！\n消耗哈夫币: 3,000,000"

            # 发送猛攻激活专用gif图片
            menggongzhong_image_path = os.path.join(self.biaoqing_dir, "menggongzhong.gif")
            if os.path.exists(menggongzhong_image_path):
                chain = [
                    Plain(base_message),
                    Image.fromFileSystem(menggongzhong_image_path)
                ]
                yield event.chain_result(chain)
            else:
                yield event.plain_result(base_message)

            # 自动关闭猛攻状态
            asyncio.create_task(self._disable_menggong_after_delay(user_id, duration_seconds))

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

    async def set_menggong_time_all(self, duration_minutes):
        """为所有用户设置六套时间（管理员功能）"""
        try:
            current_time = int(time.time())
            duration_seconds = duration_minutes * 60
            menggong_end_time = current_time + duration_seconds

            async with aiosqlite.connect(self.db_path) as db:
                # 获取所有用户ID
                cursor = await db.execute("SELECT user_id FROM user_economy")
                user_ids = await cursor.fetchall()

                if not user_ids:
                    return "❌ 没有找到任何用户数据"

                # 为所有用户设置六套时间
                await db.execute(
                    "UPDATE user_economy SET menggong_active = 1, menggong_end_time = ?",
                    (menggong_end_time,)
                )
                await db.commit()

            # 为所有用户创建自动关闭任务
            for user_row in user_ids:
                user_id = user_row[0]
                asyncio.create_task(self._disable_menggong_after_delay(user_id, duration_seconds))

            user_count = len(user_ids)
            return f"✅ 已为所有用户({user_count}人)设置 {duration_minutes} 分钟的六套时间"

        except Exception as e:
            logger.error(f"设置全体六套时间时出错: {e}")
            return f"❌ 设置六套时间失败: {str(e)}"

    async def set_menggong_time_multiplier(self, multiplier):
        """设置六套时间倍率（管理员功能）"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 更新系统配置中的时间倍率
                await db.execute(
                    "INSERT OR REPLACE INTO system_config (config_key, config_value) VALUES ('menggong_time_multiplier', ?)",
                    (str(multiplier),)
                )
                await db.commit()

            return f"✅ 已设置六套时间倍率为 {multiplier}x\n💡 新用户激活六套时间时将使用此倍率"

        except Exception as e:
            logger.error(f"设置六套时间倍率时出错: {e}")
            return f"❌ 设置六套时间倍率失败: {str(e)}"

    async def get_menggong_time_multiplier(self):
        """获取当前六套时间倍率"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT config_value FROM system_config WHERE config_key = 'menggong_time_multiplier'"
                )
                result = await cursor.fetchone()
                if result:
                    return float(result[0])
                else:
                    return 1.0  # 默认倍率
        except Exception as e:
            logger.error(f"获取六套时间倍率时出错: {e}")
            return 1.0  # 默认倍率

    async def upgrade_teqin(self, event):
        """特勤处升级功能"""
        user_id = event.get_sender_id()

        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return

            current_level = economy_data["teqin_level"]
            current_grid_size = economy_data["grid_size"]

            # 数据兼容性检查和修复
            expected_grid_size = 2 + current_level if current_level > 0 else 2

            # 检测到数据不一致（可能是版本更新导致的问题）
            if current_grid_size != expected_grid_size:
                # 如果当前格子大小大于预期（旧版本数据），需要进行兼容性处理
                if current_grid_size > expected_grid_size:
                    # 计算应该退回的哈夫币（基于格子大小差异）
                    level_diff = current_grid_size - expected_grid_size

                    # 升级费用（对应0->1, 1->2, 2->3, 3->4, 4->5级的升级）
                    upgrade_costs = [640000, 3200000, 25600000, 64800000, 102400000]

                    # 计算需要退回的费用
                    refund_amount = 0
                    for i in range(level_diff):
                        if current_level + i < len(upgrade_costs):
                            refund_amount += upgrade_costs[current_level + i]

                    # 修复数据并退回哈夫币
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE user_economy SET warehouse_value = warehouse_value + ?, grid_size = ? WHERE user_id = ?",
                            (refund_amount, expected_grid_size, user_id)
                        )
                        await db.commit()

                    yield event.plain_result(
                        f"🔧 检测到数据不一致，已自动修复！\n"
                        f"格子大小: {current_grid_size}x{current_grid_size} → {expected_grid_size}x{expected_grid_size}\n"
                        f"退回哈夫币: {refund_amount:,}\n"
                        f"请重新尝试升级特勤处。"
                    )
                    return
                else:
                    # 如果当前格子大小小于预期，直接修复到正确大小
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute(
                            "UPDATE user_economy SET grid_size = ? WHERE user_id = ?",
                            (expected_grid_size, user_id)
                        )
                        await db.commit()

                    yield event.plain_result(
                        f"🔧 检测到数据不一致，已自动修复！\n"
                        f"格子大小: {current_grid_size}x{current_grid_size} → {expected_grid_size}x{expected_grid_size}\n"
                        f"请重新尝试升级特勤处。"
                    )
                    return

            # 升级费用（对应0->1, 1->2, 2->3, 3->4, 4->5级的升级）
            upgrade_costs = [640000, 3200000, 25600000, 64800000, 102400000]

            # 等级限制检查
            if current_level >= 5:
                yield event.plain_result("特勤处已达到最高等级（5级）！")
                return

            # 获取升级费用
            if current_level < len(upgrade_costs):
                upgrade_cost = upgrade_costs[current_level]
            else:
                yield event.plain_result("升级费用配置错误！")
                return

            # 检查仓库价值是否足够
            if economy_data["warehouse_value"] < upgrade_cost:
                yield event.plain_result(f"哈夫币不足！当前价值: {economy_data['warehouse_value']:,}，升级到{current_level + 1}级需要: {upgrade_cost:,}")
                return

            # 执行升级
            new_level = current_level + 1
            # 计算新的格子大小：0级=2x2, 1级=3x3, 2级=4x4, 3级=5x5, 4级=6x6, 5级=7x7
            new_grid_size = 2 + new_level if new_level > 0 else 2

            # 二次检查：确保不会出现反向升级
            if new_grid_size <= current_grid_size:
                yield event.plain_result(
                    f"❌ 升级异常：新格子大小({new_grid_size}x{new_grid_size})不大于当前大小({current_grid_size}x{current_grid_size})！\n"
                    f"请联系管理员检查数据。"
                )
                return

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value - ?, teqin_level = ?, grid_size = ? WHERE user_id = ?",
                    (upgrade_cost, new_level, new_grid_size, user_id)
                )
                await db.commit()

            yield event.plain_result(
                f"🎉 特勤处升级成功！\n"
                f"等级: {current_level} → {new_level}\n"
                f"格子大小: {current_grid_size}x{current_grid_size} → {new_grid_size}x{new_grid_size}\n"
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
                minutes = int(remaining_time // 60)
                seconds = int(remaining_time % 60)
                if minutes > 0:
                    menggong_status = f"\n🔥 刘涛状态: 激活中 (剩余 {minutes}分{seconds}秒)"
                else:
                    menggong_status = f"\n🔥 刘涛状态: 激活中 (剩余 {seconds}秒)"
            else:
                menggong_status = "\n🔥 刘涛状态: 未激活"

            # 下一级升级费用
            upgrade_costs = [640000, 3200000, 25600000, 64800000, 102400000]

            next_upgrade_info = ""
            if economy_data["teqin_level"] < 5:
                if economy_data["teqin_level"] < len(upgrade_costs):
                    next_cost = upgrade_costs[economy_data["teqin_level"]]
                    next_upgrade_info = f"\n📈 下级升级费用: {next_cost:,}"
                else:
                    next_upgrade_info = "\n📈 升级费用配置错误"
            else:
                next_upgrade_info = "\n📈 已达最高等级"

            info_text = (
                f"💰 哈夫币: {economy_data['warehouse_value']:,}\n"
                f"🏢 特勤处等级: {economy_data['teqin_level']}级\n"
                f"📦 格子大小: {economy_data['grid_size']}x{economy_data['grid_size']}"
                f"{next_upgrade_info}"
                f"{menggong_status}"
            )

            yield event.plain_result(info_text)

        except Exception as e:
            logger.error(f"查看仓库信息功能出错: {e}")
            yield event.plain_result("查看仓库信息功能出错，请重试")

    async def get_leaderboard(self, event):
        """获取图鉴数量榜和仓库价值榜前五位"""
        try:
            # 获取群ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("此功能仅支持群聊使用")
                return

            # 获取群成员昵称映射
            nickname_map = await self._get_group_member_nicknames(event, group_id)

            async with aiosqlite.connect(self.db_path) as db:
                # 图鉴数量榜
                cursor = await db.execute("""
                    SELECT user_id, COUNT(*) as item_count
                    FROM user_touchi_collection
                    GROUP BY user_id
                    ORDER BY item_count DESC
                    LIMIT 5
                """)
                collection_top = await cursor.fetchall()

                # 仓库价值榜
                cursor = await db.execute("""
                    SELECT user_id, warehouse_value
                    FROM user_economy
                    WHERE warehouse_value > 0
                    ORDER BY warehouse_value DESC
                    LIMIT 5
                """)
                warehouse_top = await cursor.fetchall()

                # 构建排行榜消息
                message = "🏆 鼠鼠榜 🏆\n\n"

                # 图鉴数量榜
                message += "📚 图鉴数量榜 TOP5:\n"
                for i, (user_id, count) in enumerate(collection_top, 1):
                    nickname = nickname_map.get(user_id, f"用户{user_id[:6]}")
                    message += f"{i}. {nickname} - {count}个物品\n"

                message += "\n💰 仓库价值榜 TOP5:\n"
                for i, (user_id, value) in enumerate(warehouse_top, 1):
                    nickname = nickname_map.get(user_id, f"用户{user_id[:6]}")
                    message += f"{i}. {nickname} - {value}哈夫币\n"

                yield event.plain_result(message)

        except Exception as e:
            logger.error(f"获取排行榜时出错: {str(e)}")
            yield event.plain_result("获取排行榜失败，请稍后再试")

    async def start_auto_touchi(self, event):
        """开启自动偷吃功能"""
        user_id = event.get_sender_id()

        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return

            # 检查是否已经在自动偷吃状态
            if economy_data["auto_touchi_active"]:
                if self._is_auto_touchi_task_running(user_id):
                    start_time = economy_data["auto_touchi_start_time"]
                    elapsed_time = int(time.time()) - start_time
                    minutes = int(elapsed_time // 60)
                    seconds = int(elapsed_time % 60)
                    if minutes > 0:
                        yield event.plain_result(f"自动偷吃已经在进行中，已运行 {minutes}分{seconds}秒")
                    else:
                        yield event.plain_result(f"自动偷吃已经在进行中，已运行 {seconds}秒")
                    return
                await self._clear_stale_auto_touchi_state(user_id)
                economy_data["auto_touchi_active"] = 0
                logger.warning(f"用户 {user_id} 的自动偷吃状态存在但后台任务不存在，已自动清理")

            # 开启自动偷吃
            current_time = int(time.time())
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET auto_touchi_active = 1, auto_touchi_start_time = ? WHERE user_id = ?",
                    (current_time, user_id)
                )
                await db.commit()

            # 初始化自动偷吃数据
            self.auto_touchi_data[user_id] = {
                "red_items_count": 0,
                "start_time": current_time
            }

            # 启动自动偷吃任务
            task = asyncio.create_task(self._auto_touchi_loop(user_id, event))
            self.auto_touchi_tasks[user_id] = task

            # 计算实际间隔时间
            actual_interval = 600 / self.multiplier  # 基础10分钟除以倍率
            interval_minutes = round(actual_interval / 60, 1)

            yield event.plain_result(f"🤖 自动偷吃已开启！\n⏰ 每{interval_minutes}分钟自动偷吃\n🎯 金红概率降低\n📊 只记录数据，不输出图片\n⏱️ 4小时后自动停止")

        except Exception as e:
            logger.error(f"开启自动偷吃时出错: {e}")
            yield event.plain_result("开启自动偷吃失败，请重试")

    async def stop_auto_touchi(self, event):
        """关闭自动偷吃功能"""
        user_id = event.get_sender_id()

        try:
            economy_data = await self.get_user_economy_data(user_id)
            if not economy_data:
                yield event.plain_result("获取用户数据失败！")
                return

            # 检查是否在自动偷吃状态
            if not economy_data["auto_touchi_active"]:
                yield event.plain_result("自动偷吃未开启")
                return

            result_text = await self._stop_auto_touchi_internal(user_id)
            yield event.plain_result(result_text)

        except Exception as e:
            logger.error(f"关闭自动偷吃时出错: {e}")
            yield event.plain_result("关闭自动偷吃失败，请重试")

    async def _stop_auto_touchi_internal(self, user_id):
        """内部停止自动偷吃方法"""
        try:
            # 停止自动偷吃任务
            if user_id in self.auto_touchi_tasks:
                task = self.auto_touchi_tasks.pop(user_id)
                if task is not asyncio.current_task():
                    task.cancel()

            # 更新数据库状态
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE user_economy SET auto_touchi_active = 0, auto_touchi_start_time = 0 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()

            # 统计结果
            auto_data = self.auto_touchi_data.get(user_id, {})
            red_count = auto_data.get("red_items_count", 0)
            start_time = auto_data.get("start_time", int(time.time()))
            duration = int(time.time()) - start_time

            # 清理数据
            if user_id in self.auto_touchi_data:
                del self.auto_touchi_data[user_id]

            result_text = (
                f"🛑 自动偷吃已关闭\n"
                f"⏱️ 运行时长: {duration // 60}分{duration % 60}秒\n"
                f"🔴 获得红色物品数量: {red_count}个"
            )

            return result_text

        except Exception as e:
            logger.error(f"内部停止自动偷吃时出错: {e}")
            return "关闭自动偷吃失败，请重试"

    async def _auto_touchi_loop(self, user_id, event):
        """自动偷吃循环任务"""
        try:
            start_time = time.time()
            max_duration = 4 * 3600  # 4小时 = 14400秒 - 🔧 修复：应该是3600而不是3600
            base_interval = 600  # 基础间隔10分钟 = 600秒
            interval = base_interval / self.multiplier  # 应用冷却倍率

            while True:
                # 检查是否超过4小时
                if time.time() - start_time >= max_duration:
                    logger.info(f"用户 {user_id} 的自动偷吃已运行4小时，自动停止")
                    await self._stop_auto_touchi_internal(user_id)
                    # 注意：这里不能发送消息，因为这是后台任务
                    break

                await asyncio.sleep(interval)

                # 检查用户是否还在自动偷吃状态
                economy_data = await self.get_user_economy_data(user_id)
                if not economy_data or not economy_data["auto_touchi_active"]:
                    break

                # 执行自动偷吃
                await self._perform_auto_touchi(user_id, economy_data)

        except asyncio.CancelledError:
            logger.info(f"用户 {user_id} 的自动偷吃任务被取消")
        except Exception as e:
            logger.error(f"自动偷吃循环出错: {e}")
        finally:
            if self.auto_touchi_tasks.get(user_id) is asyncio.current_task():
                self.auto_touchi_tasks.pop(user_id, None)

    async def _perform_auto_touchi(self, user_id, economy_data):
        """执行一次自动偷吃"""
        try:
            from .touchi import load_items, create_safe_layout

            # 加载物品
            items = load_items()
            if not items:
                return

            # 检查猛攻状态
            current_time = int(time.time())
            menggong_mode = economy_data["menggong_active"] and current_time < economy_data["menggong_end_time"]

            # 创建保险箱布局（自动模式下概率调整）
            # 自动偷吃不使用自定义概率，使用默认概率
            placed_items, _, _, _, _ = create_safe_layout(items, menggong_mode, economy_data["grid_size"], auto_mode=True, time_multiplier=1.0,
                                                            custom_normal_rates=None, custom_menggong_rates=None)

            if placed_items:
                # 记录到数据库
                await self.add_items_to_collection(user_id, placed_items)

                # 统计红色物品
                red_items = [item for item in placed_items if item["item"]["level"] == "red"]
                if user_id in self.auto_touchi_data:
                    self.auto_touchi_data[user_id]["red_items_count"] += len(red_items)

                logger.info(f"用户 {user_id} 自动偷吃获得 {len(placed_items)} 个物品，其中红色 {len(red_items)} 个")

        except Exception as e:
            logger.error(f"执行自动偷吃时出错: {e}")

    async def set_base_teqin_level(self, level: int):
        """设置特勤处基础等级"""
        try:
            # 计算对应的grid_size
            if level == 0:
                grid_size = 2  # 0级对应2x2
            else:
                grid_size = 2 + level  # 1级=3x3, 2级=4x4, 3级=5x5, 4级=6x6, 5级=7x7

            async with aiosqlite.connect(self.db_path) as db:
                # 更新系统配置
                await db.execute(
                    "UPDATE system_config SET config_value = ? WHERE config_key = 'base_teqin_level'",
                    (str(level),)
                )

                await db.commit()

                # 获取当前用户数量
                cursor = await db.execute("SELECT COUNT(*) FROM user_economy")
                user_count = (await cursor.fetchone())[0]

            return (
                f"✅ 特勤处基础等级设置成功！\n"
                f"基础等级: {level}级\n"
                f"对应格子大小: {grid_size}x{grid_size}\n"
                f"此设置将影响新注册的用户\n"
                f"当前已有 {user_count} 个用户（不受影响）"
            )

        except Exception as e:
            logger.error(f"设置特勤处基础等级时出错: {e}")
            return f"❌ 设置失败: {str(e)}"

    async def jianshi_items(self, event):
        """检视最后一次偷吃的物品"""
        user_id = event.get_sender_id()

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取用户最后一次偷吃的物品记录
                cursor = await db.execute(
                    "SELECT items_json, jianshi_index FROM user_last_touchi WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    yield event.plain_result("🐭 你还没有偷吃过任何物品，无法检视")
                    return

                items_json, current_index = result
                import json
                items_list = json.loads(items_json)

                if not items_list:
                    yield event.plain_result("🐭 没有可检视的物品或检视资源没有完整下载")
                    return

                # 筛选出有对应检视gif的物品
                jianshi_items = []
                for item in items_list:
                    unique_id = item['unique_id']
                    gif_path = os.path.join(self.jianshi_dir, f"{unique_id}.gif")
                    if os.path.exists(gif_path):
                        jianshi_items.append({
                            'item_name': item['item_name'],
                            'unique_id': unique_id,
                            'item_level': item['item_level'],
                            'gif_path': gif_path
                        })

                if not jianshi_items:
                    yield event.plain_result("🐭 最后一次偷吃的物品中没有可检视的物品，或检查检视资源是否完整下载")
                    return

                # 获取当前要检视的物品（按顺序轮流）
                item_to_show = jianshi_items[current_index % len(jianshi_items)]

                # 更新检视索引，准备下次检视
                next_index = (current_index + 1) % len(jianshi_items)
                await db.execute(
                    "UPDATE user_last_touchi SET jianshi_index = ? WHERE user_id = ?",
                    (next_index, user_id)
                )
                await db.commit()

                # 发送检视gif（仅发送gif，不附带文字）
                yield event.image_result(item_to_show['gif_path'])

        except Exception as e:
            logger.error(f"检视物品时出错: {e}")
            yield event.plain_result("🐭 检视失败，请检查检视资源是否完整下载")
