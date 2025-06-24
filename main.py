import os
import asyncio
import aiosqlite  # Import the standard SQLite library
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import command
from .core.touchi_tools import TouchiTools
from .core.tujian import TujianTools

@register("astrbot_plugin_touchi", "touchi", "这是一个为 AstrBot 开发的鼠鼠偷吃插件，增加了图鉴功能", "1.2.0")
class Main(Star):
    @classmethod
    def info(cls):
        return {
            "name": "astrbot_plugin_touchi",
            "version": "1.2.0",
            "description": "这是一个为 AstrBot 开发的鼠鼠偷吃插件，增加了图鉴功能",
            "author": "touchi & Gemini"
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
                await db.commit()
            logger.info("偷吃插件数据库[collection.db]初始化成功。")
        except Exception as e:
            logger.error(f"初始化偷吃插件数据库[collection.db]时出错: {e}")

    @command("touchi")
    async def touchi(self, event: AstrMessageEvent):
        """盲盒功能"""
        async for result in self.touchi_tools.get_touchi(event):
            yield result

    @command("tujian")
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
       """设置偷吃和猛攻的速度倍率"""
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
