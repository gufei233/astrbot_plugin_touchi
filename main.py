import os
import asyncio
import aiosqlite  # Import the standard SQLite library
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import command
from .core.touchi_tools import TouchiTools
from .core.tujian import TujianTools

@register("astrbot_plugin_touchi", "touchi", "这是一个为 AstrBot 开发的鼠鼠偷吃插件，增加了图鉴功能", "2.2.3")
class Main(Star):
    @classmethod
    def info(cls):
        return {
            "name": "astrbot_plugin_touchi",
            "version": "2.2.3",
            "description": "这是一个为 AstrBot 开发的鼠鼠偷吃插件，增加了图鉴特勤处刘涛功能",
            "author": "sa1guu"
        }

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        
        self.config = config or {}
        self.enable_touchi = self.config.get("enable_touchi", True)
        self.enable_beauty_pic = self.config.get("enable_beauty_pic", True)
        
        # Define path for the plugin's private database in its data directory
        data_dir = StarTools.get_data_dir("astrbot_plugin_touchi")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "collection.db")
        
        # Initialize the database table
        asyncio.create_task(self._initialize_database())
        
        # Pass the database file PATH to the tools
        self.touchi_tools = TouchiTools(
            enable_touchi=self.enable_touchi,
            enable_beauty_pic=self.enable_beauty_pic,
            cd=5,
            db_path=self.db_path
        )

        self.tujian_tools = TujianTools(db_path=self.db_path)

    async def _initialize_database(self):
        """Initializes the database and creates the table if it doesn't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_touchi_collection (
                        user_id TEXT NOT NULL,
                        item_name TEXT NOT NULL,
                        item_level TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, item_name)
                    );
                """)
                # 新增经济系统表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_economy (
                        user_id TEXT PRIMARY KEY,
                        warehouse_value INTEGER DEFAULT 0,
                        teqin_level INTEGER DEFAULT 0,
                        grid_size INTEGER DEFAULT 2,
                        menggong_active INTEGER DEFAULT 0,
                        menggong_end_time REAL DEFAULT 0,
                        auto_touchi_active INTEGER DEFAULT 0,
                        auto_touchi_start_time REAL DEFAULT 0
                    );
                """)
                
                # 新增系统配置表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS system_config (
                        config_key TEXT PRIMARY KEY,
                        config_value TEXT NOT NULL
                    );
                """)
                
                # 初始化基础等级配置
                await db.execute("""
                    INSERT OR IGNORE INTO system_config (config_key, config_value) 
                    VALUES ('base_teqin_level', '0')
                """)
                
                # 添加新字段（如果不存在）
                try:
                    await db.execute("ALTER TABLE user_economy ADD COLUMN auto_touchi_active INTEGER DEFAULT 0")
                except:
                    pass  # 字段已存在
                
                try:
                    await db.execute("ALTER TABLE user_economy ADD COLUMN auto_touchi_start_time REAL DEFAULT 0")
                except:
                    pass  # 字段已存在
                await db.commit()
            logger.info("偷吃插件数据库[collection.db]初始化成功。")
        except Exception as e:
            logger.error(f"初始化偷吃插件数据库[collection.db]时出错: {e}")

    @command("偷吃")
    async def touchi(self, event: AstrMessageEvent):
        """盲盒功能"""
        async for result in self.touchi_tools.get_touchi(event):
            yield result

    @command("鼠鼠图鉴")
    async def tujian(self, event: AstrMessageEvent):
        """显示用户稀有物品图鉴（金色和红色）"""
        try:
            user_id = event.get_sender_id()
            result_path_or_msg = await self.tujian_tools.generate_tujian(user_id)
            
            if os.path.exists(result_path_or_msg):
                yield event.image_result(result_path_or_msg)
            else:
                yield event.plain_result(result_path_or_msg)
        except Exception as e:
            logger.error(f"生成图鉴时出错: {e}")
            yield event.plain_result("生成图鉴时发生内部错误，请联系管理员。")

    @command("鼠鼠冷却倍率")
    async def set_multiplier(self, event: AstrMessageEvent):
       """设置偷吃和猛攻的速度倍率（仅管理员）"""
       # 检查用户是否为管理员
       if event.role != "admin":
           yield event.plain_result("❌ 此指令仅限管理员使用")
           return
           
       try:
           plain_text = event.message_str.strip()
           args = plain_text.split()
           
           if len(args) < 2:
               yield event.plain_result("请提供倍率值，例如：鼠鼠冷却倍率 0.5")
               return
        
           multiplier = float(args[1])
           if multiplier < 0.01 or multiplier > 100:
               yield event.plain_result("倍率必须在0.01到100之间")
               return
            
           msg = self.touchi_tools.set_multiplier(multiplier)
           yield event.plain_result(msg)
        
       except ValueError:
           yield event.plain_result("倍率必须是数字")
       except Exception as e:
           logger.error(f"设置倍率时出错: {e}")
           yield event.plain_result("设置倍率失败，请重试")

    @command("六套猛攻")
    async def menggong(self, event: AstrMessageEvent):
        """六套猛攻功能"""
        async for result in self.touchi_tools.menggong_attack(event):
            yield result

    @command("特勤处升级")
    async def upgrade_teqin(self, event: AstrMessageEvent):
        """特勤处升级功能"""
        async for result in self.touchi_tools.upgrade_teqin(event):
            yield result

    @command("鼠鼠仓库")
    async def warehouse_value(self, event: AstrMessageEvent):
        """查看仓库价值"""
        async for result in self.touchi_tools.get_warehouse_info(event):
            yield result

    @command("鼠鼠榜")
    async def leaderboard(self, event: AstrMessageEvent):
        """显示图鉴数量榜和仓库价值榜前五位"""
        async for result in self.touchi_tools.get_leaderboard(event):
            yield result

    @command("开启自动偷吃")
    async def start_auto_touchi(self, event: AstrMessageEvent):
        """开启自动偷吃功能"""
        async for result in self.touchi_tools.start_auto_touchi(event):
            yield result

    @command("关闭自动偷吃")
    async def stop_auto_touchi(self, event: AstrMessageEvent):
        """关闭自动偷吃功能"""
        async for result in self.touchi_tools.stop_auto_touchi(event):
            yield result

    @command("鼠鼠库清除")
    async def clear_user_data(self, event: AstrMessageEvent):
        """清除用户数据（仅管理员）"""
        # 检查用户是否为管理员
        if event.role != "admin":
            yield event.plain_result("❌ 此指令仅限管理员使用")
            return
        
        try:
            plain_text = event.message_str.strip()
            args = plain_text.split()
            
            if len(args) == 1:
                # 清除所有用户数据
                result = await self.touchi_tools.clear_user_data()
                yield event.plain_result(f"⚠️ {result}")
            elif len(args) == 2:
                # 清除指定用户数据
                target_user_id = args[1]
                result = await self.touchi_tools.clear_user_data(target_user_id)
                yield event.plain_result(f"⚠️ {result}")
            else:
                yield event.plain_result("用法：\n鼠鼠库清除 - 清除所有用户数据\n鼠鼠库清除 [用户ID] - 清除指定用户数据")
                
        except Exception as e:
            logger.error(f"清除用户数据时出错: {e}")
            yield event.plain_result("清除数据失败，请重试")

    @command("特勤处等级")
    async def set_base_teqin_level(self, event: AstrMessageEvent):
        """设置特勤处基础等级（仅管理员）"""
        # 检查用户是否为管理员
        if event.role != "admin":
            yield event.plain_result("❌ 此指令仅限管理员使用")
            return
            
        try:
            plain_text = event.message_str.strip()
            args = plain_text.split()
            
            if len(args) < 2:
                yield event.plain_result("请提供等级值，例如：设置特勤处基础等级 2")
                return
        
            level = int(args[1])
            if level < 0 or level > 5:
                yield event.plain_result("特勤处基础等级必须在0到5之间")
                return
            
            result = await self.touchi_tools.set_base_teqin_level(level)
            yield event.plain_result(result)
        
        except ValueError:
            yield event.plain_result("等级必须是整数")
        except Exception as e:
            logger.error(f"设置特勤处基础等级时出错: {e}")
            yield event.plain_result("设置特勤处基础等级失败，请重试")

    @command("touchi")
    async def help_command(self, event: AstrMessageEvent):
        """显示所有可用指令的帮助信息"""
        help_text = """🐭 鼠鼠偷吃插件 - 指令帮助 🐭

📦 基础功能：
• 偷吃 - 开启偷吃盲盒，获得随机物品
• 鼠鼠图鉴 - 查看你收集的稀有物品图鉴
• 鼠鼠仓库 - 查看仓库总价值和统计信息

⚡ 高级功能：
• 六套猛攻 - 消耗哈夫币进行猛攻模式
• 特勤处升级 - 升级特勤处等级，扩大仓库容量

🏆 排行榜：
• 鼠鼠榜 - 查看图鉴数量榜和仓库价值榜前五名

🤖 自动功能：
• 开启自动偷吃 - 启动自动偷吃模式(每10分钟，最多4小时)
• 关闭自动偷吃 - 停止自动偷吃模式

⚙️ 管理员功能：
• 鼠鼠冷却倍率 [数值] - 设置偷吃冷却倍率(0.01-100)
• 鼠鼠库清除 - 清除所有用户数据
• 特勤处等级 [等级] - 设置新用户的初始特勤处等级(0-5)


💡 提示：
• 自动偷吃期间无法手动偷吃
• 首次使用请先输入"偷吃"开始游戏！"""
        yield event.plain_result(help_text)
