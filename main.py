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

    @command("设置冷却")
    async def set_touchi_cd(self, event: AstrMessageEvent, cd: int):
        '''设置冷却'''
        if not self.enable_touchi:
            yield event.plain_result("盲盒功能已关闭")
            return
        msg = self.touchi_tools.set_cd(cd)
        yield event.plain_result(msg)