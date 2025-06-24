from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import command
import os
from .core.touchi_tools import TouchiTools

@register("astrbot_plugin_touchi", "touchi", "这是一个为 AstrBot 开发的鼠鼠偷吃插件", "1.0.0")
class Main(Star):
    @classmethod
    def info(cls):
        return {
            "name": "astrbot_plugin_touchi",
            "version": "1.0.0",
            "description": "这是一个为 AstrBot 开发的鼠鼠偷吃插件",
            "author": "touchi"
        }

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        
        # 保存配置
        self.config = config or {}
        self.enable_touchi = self.config.get("enable_touchi", True)
        
        # 初始化数据文件路径
        data_dir = StarTools.get_data_dir("astrbot_plugin_touchi")
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化盲盒工具
        self.touchi_tools = TouchiTools(enable_touchi=self.enable_touchi, cd=5)

    @command("touchi")
    async def touchi(self, event: AstrMessageEvent):
        """盲盒功能"""
        async for result in self.touchi_tools.get_touchi(event):
            yield result

    @command("鼠鼠冷却倍率")
    async def set_multiplier(self, event: AstrMessageEvent):
       """设置偷吃和猛攻的速度倍率"""
    
       try:
           # 使用正确的方法获取纯文本消息 - event.message_str
           plain_text = event.message_str.strip()
           args = plain_text.split()
        
           if len(args) < 2:
               yield event.plain_result("请提供倍率值，例如：鼠鼠冷却倍率 0.5")
               return
        
           multiplier = float(args[1])
           if multiplier < 0.01 or multiplier > 100:
               yield event.plain_result("倍率必须在0.01到100之间")
               return
            
           # 调用工具类方法设置倍率并获取返回消息
           msg = self.touchi_tools.set_multiplier(multiplier)
           yield event.plain_result(msg)
        
       except ValueError:
           yield event.plain_result("倍率必须是数字")
       except Exception as e:
           logger.error(f"设置倍率时出错: {e}")
           yield event.plain_result("设置倍率失败，请重试")  
