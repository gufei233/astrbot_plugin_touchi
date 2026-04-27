import random
import aiosqlite
import os
from datetime import datetime

class ChixiaoSystem:
    """赤枭巡猎PVP系统"""

    def __init__(self, db_path, biaoqing_dir):
        self.db_path = db_path
        self.biaoqing_dir = biaoqing_dir

        # 赤枭配置
        self.base_requirement = 200000  # 基础装备价值要求
        self.base_kill_chance = 0.35  # 基础击杀概率35%
        self.trigger_chance = 0.95  # 触发概率
        self.max_kill_chance = 0.60  # 最大击杀概率60%
        self.value_bonus_threshold = 200000  # 每多出20万增加1%概率
        self.value_bonus_per_threshold = 0.01  # 每多出20万增加1%概率

    async def initialize_database(self):
        """初始化赤枭相关数据表"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 赤枭状态表
                await db.execute("""

                    CREATE TABLE IF NOT EXISTS chixiao_status (
                        user_id TEXT PRIMARY KEY,
                        is_chixiao INTEGER DEFAULT 0,
                        equipment_value INTEGER DEFAULT 0,
                        total_kills INTEGER DEFAULT 0,
                        start_time DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # 赤枭对抗记录表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS chixiao_battles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        battle_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                        chixiao_id TEXT NOT NULL,
                        victim_id TEXT NOT NULL,
                        stolen_value INTEGER DEFAULT 0,
                        chixiao_won INTEGER DEFAULT 1,
                        battle_result TEXT NOT NULL
                    );
                """)

                await db.commit()
                print("[ChixiaoSystem] 数据库初始化成功")
        except Exception as e:
            print(f"[ChixiaoSystem] 初始化数据库时出错: {e}")

    async def become_chixiao(self, user_id, value):
        """成为赤枭

        Args:
            user_id: 用户ID
            value: 投入的装备价值

        Returns:
            tuple: (success, message)
        """
        try:
            # 检查价值是否足够
            if value < self.base_requirement:
                return False, f"❌ 装备价值不足！\n📦 最低要求: {self.base_requirement:,}\n💰 你的价值: {value:,}"

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    "SELECT warehouse_value FROM user_economy WHERE user_id = ?",
                    (user_id,)
                )
                economy_result = await cursor.fetchone()
                warehouse_value = economy_result[0] if economy_result else 0
                if warehouse_value < value:
                    await db.rollback()
                    return False, f"❌ 哈夫币不足！\n💰 当前哈夫币: {warehouse_value:,}\n⚔️ 需要投入: {value:,}"

                # 检查是否已经是赤枭
                cursor = await db.execute(
                    "SELECT is_chixiao, equipment_value, total_kills FROM chixiao_status WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()

                if result and result[0] == 1:
                    current_value = result[1]
                    kills = result[2]
                    # 增加赤枭价值
                    new_value = current_value + value
                    await db.execute(
                        "UPDATE chixiao_status SET equipment_value = ? WHERE user_id = ?",
                        (new_value, user_id)
                    )
                    message = (
                        f"⚔️ 赤枭装备已增强！\n"
                        f"💰 装备价值: {current_value:,} → {new_value:,}\n"
                        f"🎯 总击杀次数: {kills}"
                    )
                else:
                    # 成为新的赤枭
                    await db.execute(
                        """INSERT OR REPLACE INTO chixiao_status
                        (user_id, is_chixiao, equipment_value, total_kills, start_time)
                        VALUES (?, 1, ?, 0, CURRENT_TIMESTAMP)""",
                        (user_id, value)
                    )
                    message = f"🔥 你已成为赤枭！\n⚔️ 赤枭阵营\n💰 装备价值: {value:,}\n🎯 击杀次数: 0"

                await db.execute(
                    "UPDATE user_economy SET warehouse_value = warehouse_value - ? WHERE user_id = ?",
                    (value, user_id)
                )
                await db.commit()
                return True, f"{message}\n💸 投入哈夫币: {value:,}\n💰 剩余哈夫币: {warehouse_value - value:,}"

        except Exception as e:
            print(f"[ChixiaoSystem] 成为赤枭时出错: {e}")
            return False, f"❌ 成为赤枭失败: {str(e)}"

    async def cancel_chixiao(self, user_id):
        """取消赤枭状态

        Args:
            user_id: 用户ID

        Returns:
            tuple: (success, message)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取当前赤枭状态
                cursor = await db.execute(
                    "SELECT equipment_value, total_kills FROM chixiao_status WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()

                if not result or result[0] == 0:
                    return False, "❌ 你不是赤枭"

                value = result[0]
                kills = result[1]

                # 取消赤枭状态
                await db.execute(
                    "UPDATE chixiao_status SET is_chixiao = 0 WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()

                return True, f"🛑 已取消赤枭状态\n⚔️ 赤枭阵营: 退出\n💰 装备价值: {value:,}\n🎯 总击杀次数: {kills}"

        except Exception as e:
            print(f"[ChixiaoSystem] 取消赤枭状态时出错: {e}")
            return False, f"❌ 取消赤枭状态失败: {str(e)}"

    async def get_chixiao_info(self, user_id):
        """获取赤枭信息

        Args:
            user_id: 用户ID

        Returns:
            dict or None: 赤枭信息字典，如果不是赤枭则返回None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT is_chixiao, equipment_value, total_kills, start_time FROM chixiao_status WHERE user_id = ?",
                    (user_id,)
                )
                result = await cursor.fetchone()

                if not result or result[0] == 0:
                    return None

                return {
                    "is_chixiao": True,
                    "equipment_value": result[1],
                    "total_kills": result[2],
                    "start_time": result[3]
                }

        except Exception as e:
            print(f"[ChixiaoSystem] 获取赤枭信息时出错: {e}")
            return None

    async def get_all_chixiao_players(self):
        """获取所有赤枭玩家

        Returns:
            list: 赤枭玩家列表，每个元素是包含user_id和equipment_value的字典
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, equipment_value, total_kills FROM chixiao_status WHERE is_chixiao = 1 ORDER BY equipment_value DESC",
                )
                results = await cursor.fetchall()

                chixiao_list = []
                for row in results:
                    chixiao_list.append({
                        "user_id": row[0],
                        "equipment_value": row[1],
                        "total_kills": row[2]
                    })

                return chixiao_list

        except Exception as e:
            print(f"[ChixiaoSystem] 获取赤枭列表时出错: {e}")
            return []

    async def calculate_kill_chance(self, chixiao_value, is_menggong_active=False):
        """计算赤枭的击杀概率

        Args:
            chixiao_value: 赤枭装备价值
            is_menggong_active: 受害者是否在猛攻状态

        Returns:
            float: 击杀概率（0.0-1.0之间）
        """
        # 猛攻玩家特殊规则：如果赤枭装备价值小于30万，基础击杀概率降为15%
        base_chance = self.base_kill_chance
        if is_menggong_active and chixiao_value < 300000:
            base_chance = 0.15  # 15%基础击杀概率

        # 计算超出基础价值的部分
        excess_value = max(0, chixiao_value - self.base_requirement)

        # 计算增加的概率（每多出20万增加1%）
        bonus_chance = (excess_value // self.value_bonus_threshold) * self.value_bonus_per_threshold

        # 总概率 = 基础概率 + 奖励概率，但不超过最大值
        total_chance = min(base_chance + bonus_chance, self.max_kill_chance)

        return total_chance

    async def check_and_trigger_battle(self, victim_id, stolen_value, is_menggong_active=False):
        """检查并触发赤枭对抗事件

        Args:
            victim_id: 偷吃的玩家ID
            stolen_value: 偷吃获得的价值
            is_menggong_active: 受害者是否在猛攻状态

        Returns:
            tuple: (是否触发, 对战结果, 赤枭ID, 偷走的金额, 赤枭击杀次数)
        """
        try:
            # 触发概率检查（添加调试日志）
            random_value = random.random()
            print(f"[ChixiaoSystem] 赤枭对抗检查 - 受害者: {victim_id}, 偷吃价值: {stolen_value}, 触发概率: {self.trigger_chance}, 随机值: {random_value}")

            if random_value > self.trigger_chance:
                print(f"[ChixiaoSystem] 未触发赤枭对抗（随机值 > 触发概率）")
                return False, None, None, 0, 0

            # 获取所有赤枭玩家
            chixiao_players = await self.get_all_chixiao_players()
            print(f"[ChixiaoSystem] 找到 {len(chixiao_players)} 个赤枭玩家")

            if not chixiao_players:
                return False, None, None, 0, 0

            # 排除受害者自己（如果受害者也是赤枭）
            chixiao_players = [c for c in chixiao_players if c["user_id"] != victim_id]

            if not chixiao_players:
                return False, None, None, 0, 0

            # 轮流触发每个赤枭
            # 这里我们先触发第一个赤枭的对抗
            chixiao = chixiao_players[0]
            chixiao_id = chixiao["user_id"]
            chixiao_value = chixiao["equipment_value"]
            chixiao_kills = chixiao["total_kills"]

            # 计算击杀概率（传递猛攻状态）
            kill_chance = await self.calculate_kill_chance(chixiao_value, is_menggong_active)

            # 判定结果
            if random.random() < kill_chance:
                # 赤枭获胜，夺取价值
                stolen_amount = stolen_value

                # 更新赤枭装备价值
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "UPDATE chixiao_status SET equipment_value = equipment_value + ?, total_kills = total_kills + 1 WHERE user_id = ?",
                        (stolen_amount, chixiao_id)
                    )

                    # 记录战斗
                    await db.execute(
                        """INSERT INTO chixiao_battles
                        (chixiao_id, victim_id, stolen_value, chixiao_won, battle_result)
                        VALUES (?, ?, ?, 1, ?)""",
                        (chixiao_id, victim_id, stolen_amount, 'chixiao_won')
                    )

                    await db.commit()

                # 返回赤枭获胜结果
                return True, "chixiao_won", chixiao_id, stolen_amount, chixiao_kills + 1
            else:
                # 玩家获胜，获得赤枭所有价值
                async with aiosqlite.connect(self.db_path) as db:
                    # 获取赤枭当前价值
                    cursor = await db.execute(
                        "SELECT equipment_value FROM chixiao_status WHERE user_id = ?",
                        (chixiao_id,)
                    )
                    result = await cursor.fetchone()
                    chixao_current_value = result[0] if result else 0

                    # 取消赤枭状态
                    await db.execute(
                        "UPDATE chixiao_status SET is_chixiao = 0, equipment_value = 0 WHERE user_id = ?",
                        (chixiao_id,)
                    )

                    # 记录战斗
                    await db.execute(
                        """INSERT INTO chixiao_battles
                        (chixiao_id, victim_id, stolen_value, chixiao_won, battle_result)
                        VALUES (?, ?, ?, 0, ?)""",
                        (chixiao_id, victim_id, chixao_current_value, 'victim_won')
                    )

                    await db.commit()

                # 返回玩家获胜结果
                return True, "victim_won", chixiao_id, chixao_current_value, chixiao_kills

        except Exception as e:
            print(f"[ChixiaoSystem] 触发赤枭对抗时出错: {e}")
            return False, None, None, 0, 0

    def get_emoji_path(self, result_type):
        """获取对抗结果对应的表情文件路径

        Args:
            result_type: 结果类型 ('chixiao_won' 或 'victim_won')

        Returns:
            str: 表情文件的完整路径，如果文件不存在则返回None
        """
        try:
            if result_type == "chixiao_won":
                emoji_filename = "xianjing.png"  # 玩家被赤枭打死
            elif result_type == "victim_won":
                emoji_filename = "bengfei.png"  # 赤枭被玩家打死
            else:
                return None

            emoji_path = os.path.join(self.biaoqing_dir, emoji_filename)

            if os.path.exists(emoji_path):
                return emoji_path
            else:
                print(f"[ChixiaoSystem] 表情文件不存在: {emoji_path}")
                return None

        except Exception as e:
            print(f"[ChixiaoSystem] 获取表情路径时出错: {e}")
            return None

    async def get_leaderboard(self):
        """获取赤枭排行榜

        Returns:
            list: 赤枭排行榜列表，按击杀次数降序排列
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT user_id, equipment_value, total_kills FROM chixiao_status WHERE is_chixiao = 1 ORDER BY total_kills DESC, equipment_value DESC LIMIT 10",
                )
                results = await cursor.fetchall()

                leaderboard = []
                for row in results:
                    leaderboard.append({
                        "user_id": row[0],
                        "equipment_value": row[1],
                        "total_kills": row[2]
                    })

                return leaderboard

        except Exception as e:
            print(f"[ChixiaoSystem] 获取赤枭排行榜时出错: {e}")
            return []
