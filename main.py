import os
import asyncio
import aiosqlite  
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import command
from .core.chixiao import ChixiaoSystem
from .core.touchi_tools import TouchiTools
from .core.tujian import TujianTools
from .core.zhou import ZhouGame



@register("astrbot_plugin_touchi", "touchi", "这是一个为 AstrBot 开发的三角洲鼠鼠偷吃群娱插件，增加了鼠鼠榜每日密码猛攻转盘", "2.8.3")
class Main(Star):
    @classmethod
    def info(cls):
        return {
            "name": "astrbot_plugin_touchi",
            "version": "2.8.3",
            "description": "这是一个为 AstrBot 开发的三角洲鼠鼠偷吃群娱插件，增加了鼠鼠榜每日密码猛攻转盘等多种功能",
            "author": "sa1guu"
        }
    


    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        
        self.config = config or {}
        self.enable_touchi = self.config.get("enable_touchi", True)
        self.enable_beauty_pic = self.config.get("enable_beauty_pic", True)
        
        # 读取群聊白名单配置
        self.enable_group_whitelist = self.config.get("enable_group_whitelist", False)
        self.group_whitelist = self.config.get("group_whitelist", [])
        
        # 读取时间限制配置
        self.enable_time_limit = self.config.get("enable_time_limit", False)
        self.time_limit_start = self.config.get("time_limit_start", "09:00:00")
        self.time_limit_end = self.config.get("time_limit_end", "22:00:00")
        
        # 读取静态图片配置
        self.enable_static_image = self.config.get("enable_static_image", False)
        
        # 读取实验性概率调节配置（从 AstrBot 配置系统）
        self.experimental_custom_drop_rates = self.config.get("enable_custom_drop_rates", False)
        self.normal_mode_drop_rates = self.config.get("normal_mode_drop_rates", {
            "blue": 0.25,
            "purple": 0.42,
            "gold": 0.28,
            "red": 0.05
        })
        self.menggong_mode_drop_rates = self.config.get("menggong_mode_drop_rates", {
            "purple": 0.45,
            "gold": 0.45,
            "red": 0.10
        })
        
        # 验证概率配置的有效性
        if self.experimental_custom_drop_rates:
            # 验证正常模式概率
            normal_sum = sum(self.normal_mode_drop_rates.values())
            if abs(normal_sum - 1.0) > 0.01:
                logger.warning(f"⚠️ 正常模式概率配置总和不为1.0（当前: {normal_sum:.2f}），已禁用自定义概率功能")
                self.experimental_custom_drop_rates = False
            
            # 验证猛攻模式概率
            menggong_sum = sum(self.menggong_mode_drop_rates.values())
            if abs(menggong_sum - 1.0) > 0.01:
                logger.warning(f"⚠️ 猛攻模式概率配置总和不为1.0（当前: {menggong_sum:.2f}），已禁用自定义概率功能")
                self.experimental_custom_drop_rates = False
            else:
                logger.info("✅ 自定义概率配置已启用")
        
        # Define path for the plugin's private database in its data directory
        # 使用相对路径，避免硬编码绝对路径
        # 获取AstrBot根目录，然后构建数据目录路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        astrbot_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        data_dir = os.path.join(astrbot_root, "data", "plugin_data", "astrbot_plugin_touchi")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "collection.db")
        
        # Initialize the database table
        asyncio.create_task(self._initialize_database())
        
        # # 初始化转盘工具 - 改为独立调用
        # self.roulette_tools = RouletteTools(output_dir)
        
        # 初始化赤枢系统（必须在TouchiTools之前初始化）
        biaoqing_dir = os.path.join(os.path.dirname(__file__), "core", "biaoqing")
        self.chixiao_system = ChixiaoSystem(self.db_path, biaoqing_dir)
        asyncio.create_task(self.chixiao_system.initialize_database())
        
        # Pass the database file PATH to the tools
        self.touchi_tools = TouchiTools(
            enable_touchi=self.enable_touchi,
            enable_beauty_pic=self.enable_beauty_pic,
            cd=5,
            db_path=self.db_path,
            enable_static_image=self.enable_static_image,
            experimental_custom_drop_rates=self.experimental_custom_drop_rates,
            normal_mode_drop_rates=self.normal_mode_drop_rates,
            menggong_mode_drop_rates=self.menggong_mode_drop_rates,
            chixiao_system=self.chixiao_system  # 传递赤枢系统
        )

        self.tujian_tools = TujianTools(db_path=self.db_path)
        
        # 初始化洲了个洲游戏
        items_dir = os.path.join(os.path.dirname(__file__), "core", "items")
        output_dir = os.path.join(os.path.dirname(__file__), "core", "output")
        self.zhou_game = ZhouGame(self.db_path, items_dir, output_dir)

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
                
                # 添加六套时间倍率配置
                await db.execute("""
                    INSERT OR IGNORE INTO system_config (config_key, config_value) 
                    VALUES ('menggong_time_multiplier', '1.0')
                """)
                
                # 添加冷却倍率配置
                await db.execute("""
                    INSERT OR IGNORE INTO system_config (config_key, config_value) 
                    VALUES ('touchi_cooldown_multiplier', '1.0')
                """)
                
                # 添加用户最后一次偷吃记录表
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS user_last_touchi (
                        user_id TEXT PRIMARY KEY,
                        items_json TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        jianshi_index INTEGER DEFAULT 0
                    );
                """)
                
                await db.commit()
            
            # 初始化洲了个洲游戏表
            await self.zhou_game.init_game_tables()
            
            logger.info("偷吃插件数据库[collection.db]初始化成功。")
        except Exception as e:
            logger.error(f"初始化偷吃插件数据库[collection.db]时出错: {e}")
    
    def _check_group_permission(self, message_event):
        """
        检查群聊白名单权限
        返回: 是否允许
        """
        # 如果未启用白名单功能，直接允许
        if not self.enable_group_whitelist:
            return True
        
        # 私聊始终允许
        if message_event.session_id.startswith("person_"):
            return True
        
        # 获取群号
        group_id = message_event.session_id.replace("group_", "")
        
        # 检查是否在白名单中（支持字符串和数字类型的群号）
        # 将群号转换为字符串进行比较，同时也检查数字类型
        group_id_str = str(group_id)
        try:
            group_id_int = int(group_id)
        except ValueError:
            group_id_int = None
        
        for whitelist_group in self.group_whitelist:
            # 支持字符串比较
            if str(whitelist_group) == group_id_str:
                return True
            # 支持数字比较
            if group_id_int is not None and whitelist_group == group_id_int:
                return True
        
        # 非白名单群聊禁用
        return False
    
    def _check_time_permission(self):
        """
        检查时间限制权限
        返回: 是否允许
        """
        # 如果未启用时间限制功能，直接允许
        if not self.enable_time_limit:
            return True
        
        # 获取当前时间
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 检查是否在允许的时间范围内
        if self.time_limit_start <= self.time_limit_end:
            # 正常时间范围（如 09:00:00 到 22:00:00）
            return self.time_limit_start <= current_time <= self.time_limit_end
        else:
            # 跨日时间范围（如 22:00:00 到 09:00:00）
            return current_time >= self.time_limit_start or current_time <= self.time_limit_end
    
    def _check_all_permissions(self, message_event):
        """
        检查所有权限（群聊白名单 + 时间限制）
        返回: (是否允许, 错误信息)
        """
        # 检查群聊权限
        if not self._check_group_permission(message_event):
            return False, "🐭 此群聊未在白名单中，无法使用鼠鼠功能"
        
        # 检查时间权限
        if not self._check_time_permission():
            # 时间限制失败时返回提示信息
            time_range = f"{self.time_limit_start} - {self.time_limit_end}"
            return False, f"🐭 鼠鼠休息中 {time_range} 可偷吃"
        
        return True, None

    @command("偷吃")
    async def touchi(self, event: AstrMessageEvent):
        """盲盒功能"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.get_touchi(event):
            yield result

    @command("鼠鼠图鉴")
    async def tujian(self, event: AstrMessageEvent):
        """显示用户稀有物品图鉴（金色和红色）"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
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
        
           # 尝试转换为浮点数
           try:
               multiplier = float(args[1])
           except ValueError:
               yield event.plain_result(f"❌ 无法解析倍率值: '{args[1]}'\n💡 倍率必须是数字，例如: 0.5, 1.0, 2.0, 100")
               return
           
           if multiplier < 0.01 or multiplier > 100:
               yield event.plain_result("❌ 倍率必须在0.01到100之间")
               return
            
           msg = await self.touchi_tools.set_multiplier(multiplier)
           yield event.plain_result(msg)
        
       except Exception as e:
           logger.error(f"设置倍率时出错: {e}")
           yield event.plain_result("❌ 设置倍率失败，请重试")

    @command("六套猛攻")
    async def menggong(self, event: AstrMessageEvent):
        """六套猛攻功能"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.menggong_attack(event):
            yield result

    @command("特勤处升级")
    async def upgrade_teqin(self, event: AstrMessageEvent):
        """特勤处升级功能"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.upgrade_teqin(event):
            yield result

    @command("鼠鼠仓库")
    async def warehouse_value(self, event: AstrMessageEvent):
        """查看仓库价值"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.get_warehouse_info(event):
            yield result

    @command("鼠鼠榜")
    async def leaderboard(self, event: AstrMessageEvent):
        """显示图鉴数量榜和仓库价值榜前五位"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.get_leaderboard(event):
            yield result

    @command("开启自动偷吃")
    async def start_auto_touchi(self, event: AstrMessageEvent):
        """开启自动偷吃功能"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.start_auto_touchi(event):
            yield result

    @command("关闭自动偷吃")
    async def stop_auto_touchi(self, event: AstrMessageEvent):
        """关闭自动偷吃功能"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
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

    @command("鼠鼠限时")
    async def set_time_limit(self, event: AstrMessageEvent):
        """设置插件使用时间限制"""
        # 管理员权限检查
        if not event.is_admin():
            yield event.plain_result("❌ 此功能仅限管理员使用")
            return
        
        try:
            args = event.get_message_str().strip().split()
            
            if len(args) == 1:  # 只有命令，显示当前设置
                status = "启用" if self.enable_time_limit else "禁用"
                yield event.plain_result(f"🕐 当前时间限制状态: {status}\n⏰ 允许使用时间: {self.time_limit_start} - {self.time_limit_end}")
                return
            
            if len(args) == 2:  # 启用/禁用
                action = args[1]
                if action == "启用":
                    self.enable_time_limit = True
                    yield event.plain_result(f"✅ 已启用时间限制功能\n⏰ 允许使用时间: {self.time_limit_start} - {self.time_limit_end}")
                elif action == "禁用":
                    self.enable_time_limit = False
                    yield event.plain_result("✅ 已禁用时间限制功能")
                else:
                    yield event.plain_result("❌ 参数错误，请使用: 鼠鼠限时 [启用/禁用] 或 鼠鼠限时 [开始时间] [结束时间]")
                return
            
            if len(args) == 3:  # 设置时间范围
                start_time = args[1]
                end_time = args[2]
                
                # 验证时间格式
                try:
                    datetime.strptime(start_time, "%H:%M:%S")
                    datetime.strptime(end_time, "%H:%M:%S")
                except ValueError:
                    yield event.plain_result("❌ 时间格式错误，请使用 HH:MM:SS 格式（如: 09:00:00）")
                    return
                
                self.time_limit_start = start_time
                self.time_limit_end = end_time
                self.enable_time_limit = True
                yield event.plain_result(f"✅ 已设置时间限制\n⏰ 允许使用时间: {start_time} - {end_time}")
                return
            
            yield event.plain_result("❌ 参数错误\n\n📖 使用说明:\n• 鼠鼠限时 - 查看当前设置\n• 鼠鼠限时 启用/禁用 - 启用或禁用时间限制\n• 鼠鼠限时 [开始时间] [结束时间] - 设置时间范围\n\n⏰ 时间格式: HH:MM:SS（如: 09:00:00 22:00:00）")
            
        except Exception as e:
            logger.error(f"设置时间限制时出错: {e}")
            yield event.plain_result("❌ 设置时间限制失败，请重试")

    @command("touchi")
    async def help_command(self, event: AstrMessageEvent):
        """显示所有可用指令的帮助信息"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        help_text = """🐭 鼠鼠偷吃插件 - 指令帮助 🐭

📦 基础功能：
• 偷吃 - 开启偷吃盲盒，获得随机物品
• 检视 - 查看最后一次偷吃的物品
• 鼠鼠图鉴 - 查看你收集的稀有物品图鉴
• 鼠鼠仓库 - 查看仓库总价值和统计信息
• 鼠鼠转盘 - 启动转盘，随机选择地图、难度、装备和武器
• touchi - 查看本帮助

⚡ 养成与事件：
• 六套猛攻 - 消耗哈夫币进入猛攻模式
• 特勤处升级 - 升级特勤处等级，扩大仓库容量
• 偷吃事件 - 查看偷吃概率事件统计和说明

🤖 自动功能：
• 开启自动偷吃 - 启动自动偷吃模式(每10分钟，最多4小时)
• 关闭自动偷吃 - 停止自动偷吃模式并查看本轮统计

🎮 洲了个洲：
• 洲了个洲 - 开始一局洲了个洲
• 拿 [编号...] - 拿取指定编号卡牌，如：拿 1 2 3
• 撤回 - 使用撤回道具
• 洗牌 - 使用洗牌道具
• 移出卡槽 - 使用移出卡槽道具
• 洲统计 - 查看洲了个洲游戏统计

🦅 赤枭巡猎：
• 赤枭巡猎 [装备价值] - 成为或更新赤枭，默认200000
• 取消赤枭 - 取消赤枭状态
• 赤枭榜 - 查看赤枭排行榜

🏆 排行榜：
• 鼠鼠榜 - 查看图鉴数量榜和仓库价值榜

🗝️ 密码功能：
• 鼠鼠密码 - 获取地图密码信息
• 每日密码 - 获取每日地图密码信息

⚙️ 管理员功能：
• 鼠鼠冷却倍率 [数值] - 设置偷吃冷却倍率(0.01-100)
• 鼠鼠库清除 - 清除所有用户数据
• 特勤处等级 [等级] - 设置新用户的初始特勤处等级(0-5)
• 鼠鼠限时 [开始] [结束] - 设置插件使用时间范围，如：09:00:00 22:00:00
• 刷新密码 - 强制刷新密码缓存
• 六套时间倍率 [倍率] - 设置六套时间倍率(0.1-10.0)

💡 提示：
• 配置文件中可设置群聊启用白名单
• 自动偷吃期间无法手动偷吃
• 偷吃时有概率触发特殊事件，详见"偷吃事件"指令
• 首次使用请先输入"偷吃"开始游戏！"""
        yield event.plain_result(help_text)

    @command("鼠鼠密码")
    async def mima(self, event: AstrMessageEvent):
        """获取地图密码信息"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            # 导入相关函数
            from .mima_standalone import get_mima_from_txt, get_mima_async, get_mima_images
            
            # 尝试从TXT文件读取密码信息
            txt_result = get_mima_from_txt()
            if txt_result:
                yield event.plain_result(txt_result)
                return
            
            # TXT文件不存在或读取失败，从网络获取
            logger.info("TXT文件不存在或读取失败，正在从网络获取密码信息")
            result = await get_mima_async()
            yield event.plain_result(result)
            
        except ImportError as e:
            logger.error(f"导入模块失败: {e}")
            yield event.plain_result("🐭 获取密码功能需要必要的依赖\n\n🔧 解决方案:\n1. 检查网络连接\n2. 重新安装必要的依赖包")
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"获取密码信息时出错: {e}")
            
            # 检查是否为网络相关错误
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                yield event.plain_result("🐭 获取密码信息失败\n\n🔧 可能的解决方案:\n1. 检查网络连接是否正常\n2. 稍后再试")
            else:
                yield event.plain_result("🐭 获取密码信息时发生错误，请稍后再试")

    @command("每日密码")
    async def daily_mima(self, event: AstrMessageEvent):
        """获取每日地图密码信息（与鼠鼠密码功能相同）"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            # 导入相关函数
            from .mima_standalone import get_mima_from_txt, get_mima_async, get_mima_images
            
            # 尝试从TXT文件读取密码信息
            txt_result = get_mima_from_txt()
            if txt_result:
                yield event.plain_result(txt_result)
                return
            
            # TXT文件不存在或读取失败，从网络获取
            logger.info("TXT文件不存在或读取失败，正在从网络获取密码信息")
            result = await get_mima_async()
            yield event.plain_result(result)
            
        except ImportError as e:
            logger.error(f"导入模块失败: {e}")
            yield event.plain_result("🐭 获取每日密码功能需要必要的依赖\n\n🔧 解决方案:\n1. 检查网络连接\n2. 重新安装必要的依赖包")
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"获取每日密码信息时出错: {e}")
            
            # 检查是否为网络相关错误
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                yield event.plain_result("🐭 获取每日密码信息失败\n\n🔧 可能的解决方案:\n1. 检查网络连接是否正常\n2. 稍后再试")
            else:
                yield event.plain_result("🐭 获取每日密码信息时发生错误，请稍后再试")

    @command("刷新密码")
    async def refresh_mima(self, event: AstrMessageEvent):
        """强制刷新密码缓存（仅管理员）"""
        # 检查用户是否为管理员
        if event.role != "admin":
            yield event.plain_result("❌ 此指令仅限管理员使用")
            return
        
        try:
            # 调用完全独立的 mima_standalone.py
            from .mima_standalone import MimaTools
            mima_tools = MimaTools()
            result = await mima_tools.refresh_mima_cache()
            yield event.plain_result(result)
        except ImportError as e:
            logger.error(f"导入模块失败: {e}")
            yield event.plain_result("🐭 刷新密码功能需要必要的依赖\n\n🔧 解决方案:\n1. 检查网络连接\n2. 重新安装必要的依赖包")
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"刷新密码缓存时出错: {e}")
            
            # 检查是否为网络相关错误
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                yield event.plain_result("🐭 刷新密码缓存失败\n\n🔧 可能的解决方案:\n1. 检查网络连接是否正常\n2. 稍后再试")
            else:
                yield event.plain_result("🐭 刷新密码缓存时发生错误，请稍后再试")

    @command("六套时间倍率")
    async def set_menggong_time_multiplier(self, event: AstrMessageEvent):
        """设置六套时间倍率（仅管理员）"""
        # 检查用户是否为管理员
        if event.role != "admin":
            yield event.plain_result("❌ 此指令仅限管理员使用")
            return
        
        try:
            plain_text = event.message_str.strip()
            args = plain_text.split()
            
            if len(args) < 2:
                yield event.plain_result("❌ 参数不足\n\n📖 使用说明:\n• 六套时间倍率 [倍率] - 设置六套时间倍率\n\n💡 示例:\n• 六套时间倍率 2.0 - 设置2倍时长倍率\n• 六套时间倍率 0.5 - 设置0.5倍时长倍率")
                return
            
            try:
                time_multiplier = float(args[1])
            except ValueError:
                yield event.plain_result("❌ 倍率必须是数字")
                return
            
            if time_multiplier <= 0:
                yield event.plain_result("❌ 倍率必须大于0")
                return
            
            if time_multiplier > 10.0:
                yield event.plain_result("❌ 倍率不能超过10.0")
                return
            
            if time_multiplier < 0.1:
                yield event.plain_result("❌ 倍率不能小于0.1")
                return
            
            result = await self.touchi_tools.set_menggong_time_multiplier(time_multiplier)
            yield event.plain_result(result)
            
        except Exception as e:
            logger.error(f"设置六套时间时出错: {e}")
            yield event.plain_result("❌ 设置六套时间失败，请重试")

    @command("检视")
    async def jianshi(self, event: AstrMessageEvent):
        """检视最后一次偷吃的物品"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        async for result in self.touchi_tools.jianshi_items(event):
            yield result
    
    @command("偷吃事件")
    async def touchi_events_info(self, event: AstrMessageEvent):
        """查看偷吃概率事件信息"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            stats = self.touchi_tools.events.get_event_statistics()
            
            event_info = f"""🎲 偷吃概率事件统计 🎲

📊 事件触发概率：
• 🎯 正常偷吃: {stats['normal']}
• 💎 获得残缺刘涛: {stats['broken_liutao']}
• 💀 遇到天才少年被踢死: {stats['genius_kick']}
• ⚖️ 排到天才少年被追缴: {stats['genius_fine']}
• 🤦 遇到菜b队友: {stats['noob_teammate']}
• 🏃 被追杀丢包撤离: {stats['hunted_escape']}
• 🐭 遇到路人鼠鼠: {stats['passerby_mouse']}
• 🎲 总事件概率: {stats['total_event']}

📝 事件详细说明：

💎 【残缺刘涛】
• 概率: {stats['broken_liutao']}
• 效果: 额外获得残缺的刘涛
• 奖励: 激活1分钟六套加成时间
• 特殊: 期间红色和金色物品概率大幅提升

💀 【天才少年踢死】
• 概率: {stats['genius_kick']}
• 效果: 展示偷吃结果但不计入数据库
• 惩罚: 清空所有物品和仓库价值
• 提示: 重新开始收集之旅

⚖️ 【天才少年追缴】
• 概率: {stats['genius_fine']}
• 效果: 正常获得物品
• 惩罚: 被追缴30万哈夫币
• 备注: 哈夫币可以为负数

🤦 【菜b队友】
• 概率: {stats['noob_teammate']}
• 效果: 正常获得物品
• 惩罚: 撤离时间翻倍，下次偷吃冷却时间增加一倍
• 备注: 影响下次偷吃的等待时间

🏃 【被追杀丢包撤离】
• 概率: {stats['hunted_escape']}
• 效果: 正常获得本次物品
• 惩罚: 只能保留小尺寸物品(1x1,1x2,2x1,1x3,3x1)
• 备注: 删除收藏中的大尺寸物品并重新计算仓库价值

🐭 【路人鼠鼠】
• 概率: {stats['passerby_mouse']}
• 效果: 正常获得物品
• 奖励: 获得金色物品，格子扩展到最大(7x7)
• 备注: 特勤处等级直接提升到最高级

💡 提示：事件在每次偷吃时独立计算概率"""
            
            yield event.plain_result(event_info)
            
        except Exception as e:
            logger.error(f"获取偷吃事件信息时出错: {e}")
            yield event.plain_result("❌ 获取偷吃事件信息失败，请重试")
    
    @command("洲了个洲")
    async def zhou_start_game(self, event: AstrMessageEvent):
        """开始洲了个洲游戏"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if group_id:
                # 群聊中使用群组游戏
                # 检查是否有个人游戏正在进行
                personal_game_status = await self.zhou_game.get_game_stats(user_id)
                if personal_game_status and personal_game_status.get('has_active_game'):
                    yield event.plain_result("❌ 你有个人游戏正在进行中，请先完成或重新开始个人游戏")
                    return
                success, image_path, message = await self.zhou_game.start_group_game(group_id, user_id)
                print(f"[DEBUG] 群聊洲了个洲游戏 - 群组: {group_id}, 用户: {user_id}, 成功: {success}, 图片路径: {image_path}")
            else:
                # 私聊中使用个人游戏（主动发送，is_triggered=False）
                success, image_path, message = await self.zhou_game.start_new_game(user_id, is_triggered=False)
                print(f"[DEBUG] 主动发送洲了个洲游戏 - 用户: {user_id}, 成功: {success}, 图片路径: {image_path}")
            
            if success and image_path:
                # 检查图片文件是否存在
                if os.path.exists(image_path):
                    print(f"[DEBUG] 主动游戏图片文件存在，准备发送: {image_path}")
                    yield event.image_result(image_path)
                    yield event.plain_result(message)
                else:
                    print(f"[DEBUG] 主动游戏图片文件不存在: {image_path}")
                    yield event.plain_result(f"游戏启动成功但图片文件缺失: {message}")
            else:
                print(f"[DEBUG] 主动游戏启动失败或无图片路径")
                yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"开始洲了个洲游戏时出错: {e}")
            yield event.plain_result("❌ 开始游戏失败，请稍后重试")
    
    @command("拿")
    async def zhou_take_cards(self, event: AstrMessageEvent):
        """拿取卡牌"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            plain_text = event.message_str.strip()
            args = plain_text.split()[1:]  # 去掉"拿"指令本身
            
            if not args:
                yield event.plain_result("❌ 请指定要拿取的卡牌编号\n\n💡 示例:\n• 拿 1 2 3 - 拿取编号为1、2、3的卡牌")
                return
            
            # 解析卡牌编号
            card_numbers = []
            for arg in args:
                try:
                    num = int(arg)
                    card_numbers.append(num)
                except ValueError:
                    yield event.plain_result(f"❌ 无效的卡牌编号: {arg}")
                    return
            
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if group_id:
                # 群聊中使用群组游戏逻辑
                success, image_path, message = await self.zhou_game.take_group_cards(group_id, user_id, card_numbers)
            else:
                # 私聊中使用个人游戏逻辑
                success, image_path, message = await self.zhou_game.take_cards(user_id, card_numbers)
            
            if success and image_path:
                yield event.image_result(image_path)
                if message:  # 只有在有消息时才发送文字提示
                    yield event.plain_result(message)
            else:
                if message:  # 确保失败时也有消息
                    yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"拿取卡牌时出错: {e}")
            yield event.plain_result("❌ 拿取卡牌失败，请稍后重试")
    
    @command("撤回")
    async def zhou_undo(self, event: AstrMessageEvent):
        """使用撤回道具"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if group_id:
                # 群聊中使用群组游戏逻辑
                success, image_path, message = await self.zhou_game.use_group_undo(group_id, user_id)
            else:
                # 私聊中使用个人游戏逻辑
                success, image_path, message = await self.zhou_game.use_undo(user_id)
            
            if success and image_path:
                yield event.image_result(image_path)
                if message:  # 只有在有消息时才发送文字提示
                    yield event.plain_result(message)
            else:
                if message:  # 确保失败时也有消息
                    yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"使用撤回道具时出错: {e}")
            yield event.plain_result("❌ 撤回失败，请稍后重试")
    
    @command("洗牌")
    async def zhou_shuffle(self, event: AstrMessageEvent):
        """使用洗牌道具"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if group_id:
                # 群聊中使用群组游戏逻辑
                success, image_path, message = await self.zhou_game.use_group_shuffle(group_id, user_id)
            else:
                # 私聊中使用个人游戏逻辑
                success, image_path, message = await self.zhou_game.use_shuffle(user_id)
            
            if success and image_path:
                yield event.image_result(image_path)
                if message:  # 只有在有消息时才发送文字提示
                    yield event.plain_result(message)
            else:
                if message:  # 确保失败时也有消息
                    yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"使用洗牌道具时出错: {e}")
            yield event.plain_result("❌ 洗牌失败，请稍后重试")
    
    @command("移出卡槽")
    async def zhou_remove_slot(self, event: AstrMessageEvent):
        """使用移出卡槽道具"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            group_id = event.get_group_id()
            user_id = event.get_sender_id()
            
            if group_id:
                # 群聊中使用群组游戏逻辑
                success, image_path, message = await self.zhou_game.use_group_remove_slot(group_id, user_id)
            else:
                # 私聊中使用个人游戏逻辑
                success, image_path, message = await self.zhou_game.use_remove_slot(user_id)
            
            if success and image_path:
                yield event.image_result(image_path)
                if message:  # 只有在有消息时才发送文字提示
                    yield event.plain_result(message)
            else:
                if message:  # 确保失败时也有消息
                    yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"使用移出卡槽道具时出错: {e}")
            yield event.plain_result("❌ 移出卡槽失败，请稍后重试")
    
    @command("洲统计")
    async def zhou_stats(self, event: AstrMessageEvent):
        """查看洲了个洲游戏统计"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            user_id = event.get_sender_id()
            stats = await self.zhou_game.get_game_stats(user_id)
            
            if stats:
                stats_text = f"""🎮 洲了个洲游戏统计 🎮

👤 玩家: {user_id}
🎯 游戏场次: {stats['games_played']}
🏆 获胜场次: {stats['games_won']}
📊 胜率: {stats['win_rate']:.1f}%
⭐ 最高分数: {stats['best_score']}
💯 总分数: {stats['total_score']}

💡 提示: 使用"洲了个洲"开始新游戏！"""
                yield event.plain_result(stats_text)
            else:
                yield event.plain_result("📊 暂无游戏记录\n\n💡 使用\"洲了个洲\"开始你的第一局游戏！")
                
        except Exception as e:
            logger.error(f"获取游戏统计时出错: {e}")
            yield event.plain_result("❌ 获取统计信息失败，请稍后重试")
    
    @command("赤枭巡猎")
    async def become_chixiao(self, event: AstrMessageEvent):
        """赤枭巡猎 - 成为赤枭"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            user_id = event.get_sender_id()
            
            # 解析参数
            plain_text = event.message_str.strip()
            args = plain_text.split()
            
            # 检查是否指定了装备价值
            if len(args) >= 2:
                # 用户指定了装备价值
                try:
                    equipment_value = int(args[1].replace(',', ''))
                    if equipment_value < 200000:
                        yield event.plain_result("❌ 成为赤枭至少需要200,000装备价值")
                        return
                except ValueError:
                    yield event.plain_result("❌ 装备价值必须是数字")
                    return
            else:
                # 不带参数，默认使用200,000
                equipment_value = 200000
            
            # 检查是否已经是赤枭
            chixiao_info = await self.chixiao_system.get_chixiao_info(user_id)
            if chixiao_info:
                # 已经是赤枭，更新装备价值
                success, message = await self.chixiao_system.become_chixiao(user_id, equipment_value)
                yield event.plain_result(message)
            else:
                # 成为赤枭
                if equipment_value < 200000:
                    yield event.plain_result("❌ 成为赤枭至少需要200,000装备价值")
                    return
                
                success, message = await self.chixiao_system.become_chixiao(user_id, equipment_value)
                yield event.plain_result(message)
                
        except Exception as e:
            logger.error(f"赤枭巡猎时出错: {e}")
            yield event.plain_result("❌ 赤枭巡猎失败，请稍后重试")
    
    @command("取消赤枭")
    async def cancel_chixiao(self, event: AstrMessageEvent):
        """取消赤枭状态"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            user_id = event.get_sender_id()
            success, message = await self.chixiao_system.cancel_chixiao(user_id)
            yield event.plain_result(message)
            
        except Exception as e:
            logger.error(f"取消赤枭状态时出错: {e}")
            yield event.plain_result("❌ 取消赤枭状态失败，请稍后重试")
    
    @command("赤枭榜")
    async def chixiao_leaderboard(self, event: AstrMessageEvent):
        """赤枭排行榜"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            group_id = event.get_group_id()
            
            # 获取群成员昵称映射
            nickname_map = {}
            if group_id:
                nickname_map = await self.touchi_tools._get_group_member_nicknames(event, group_id)
            
            # 获取赤枭排行榜
            leaderboard = await self.chixiao_system.get_leaderboard()
            
            if not leaderboard:
                yield event.plain_result("📊 暂无赤枭玩家\n\n💡 成为赤枭需要装备价值至少200,000\n使用\"赤枭巡猎\"指令成为赤枭")
                return
            
            # 构建排行榜消息
            message = "🏆 赤枭排行榜 🏆\n\n"
            
            for i, chixiao in enumerate(leaderboard, 1):
                user_id = chixiao["user_id"]
                kills = chixiao["total_kills"]
                value = chixiao["equipment_value"]
                
                # 获取昵称
                nickname = nickname_map.get(user_id, f"用户{user_id[:6]}")
                
                # 计算击杀概率
                kill_chance = await self.chixiao_system.calculate_kill_chance(value)
                kill_chance_percent = kill_chance * 100
                
                message += f"{i}. {nickname} - {kills}次击杀 | 价值: {value:,} | 击杀率: {kill_chance_percent:.0f}%\n"
            
            message += "\n💡 成为赤枭需要装备价值至少200,000\n使用\"赤枭巡猎\"指令成为赤枭"
            
            yield event.plain_result(message)
            
        except Exception as e:
            logger.error(f"获取赤枭排行榜时出错: {e}")
            yield event.plain_result("❌ 获取赤枭排行榜失败，请稍后重试")
    
    @command("鼠鼠转盘")
    async def roulette_spin(self, event: AstrMessageEvent):
        """启动鼠鼠转盘游戏 - 独立版本"""
        allowed, error_msg = self._check_all_permissions(event)
        if not allowed:
            if error_msg:
                yield event.plain_result(error_msg)
            return
        
        try:
            # 导入并执行独立转盘文件
            try:
                from .roulette_standalone import generate_roulette
                
                # 生成转盘
                result = generate_roulette()
                
                if result["success"]:
                    # 发送GIF
                    gif_path = result["gif_path"]
                    if os.path.exists(gif_path):
                        yield event.image_result(gif_path)
                        
                        # 成功发送后删除GIF
                        try:
                            os.remove(gif_path)
                            logger.info(f"已删除转盘GIF: {gif_path}")
                        except Exception as e:
                            logger.warning(f"删除GIF文件失败: {e}")
                    else:
                        yield event.plain_result("❌ 转盘GIF文件未找到")
                else:
                    yield event.plain_result(result["message"])
                    
            except ImportError as e:
                if "PIL" in str(e) or "Pillow" in str(e):
                    yield event.plain_result("❌ 转盘功能需要安装PIL依赖\n请运行: pip install Pillow>=8.0.0")
                else:
                    yield event.plain_result(f"❌ 转盘功能导入失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"鼠鼠转盘生成失败: {e}")
            yield event.plain_result("❌ 鼠鼠转盘启动失败，请稍后重试")
