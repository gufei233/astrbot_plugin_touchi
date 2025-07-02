from playwright.async_api import async_playwright
from typing import List, Dict, Optional, Callable, Union
import re
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, time
import json
import os

from astrbot.api import logger
from astrbot.api.star import StarTools


class AcgIceSJZApi:
    """
    acg ice 的api调用
    """

    def __init__(self):
        self.url = {
            "zb_ss": "https://www.acgice.com/sjz/v/zb_ss",
            "index": "https://www.acgice.com/sjz/v/index",
            "item_list": "https://www.acgice.com/sjz/v/%s",
        }
        self.p = async_playwright()

    async def jz_zb(self):
        async with self.p as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 导航到目标页面并获取完整HTML内容
            await page.goto(self.url["zb_ss"])
            await page.wait_for_load_state("networkidle")  # 等待网络空闲
            html_content = await page.content()  # 获取完整HTML
            await browser.close()

        # 使用BeautifulSoup解析HTML内容
        soup = BeautifulSoup(html_content, "html.parser")

        results = []

        kzb_blocks = soup.find_all("div", class_="m-2")
        # 这里可以添加更多解析逻辑
        return results

    async def map_pwd_daily(self):
        captured_data = {}
        async with self.p as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 导航到首页
            await page.goto(self.url["index"])
            await page.wait_for_selector(".stats.bg-base-500", timeout=10000)

            # 提取地图密码数据
            map_data = {}
            map_stats = await page.query_selector_all(".stats.bg-base-500 .stat")

            for stat in map_stats:
                # 提取地图名称
                title_element = await stat.query_selector(".stat-title")
                map_name = (
                    await title_element.inner_text() if title_element else "未知地图"
                )

                # 提取密码
                value_element = await stat.query_selector(".stat-value")
                password = (
                    await value_element.inner_text() if value_element else "未知密码"
                )

                # 提取日期
                date_element = await stat.query_selector(".stat-desc")
                date = await date_element.inner_text() if date_element else "未知日期"

                # 存储到结果字典
                map_data[map_name] = {"password": password, "date": date}

            captured_data["map_pwd"] = map_data
            await browser.close()

        return captured_data.get("map_pwd", {})


class MimaCache:
    """
    密码缓存管理类，实现缓存到晚上12点自动丢弃的逻辑
    """

    def __init__(self):
        # 获取插件数据目录
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_touchi")
        os.makedirs(self.data_dir, exist_ok=True)
        self.cache_file = os.path.join(self.data_dir, "mima_cache.json")
        self.api = AcgIceSJZApi()

    def _is_cache_expired(self, cache_time: str) -> bool:
        """
        检查缓存是否已过期（是否已过晚上12点）
        学习鼠鼠限时的获取时间信息逻辑
        """
        try:
            # 解析缓存时间
            cache_datetime = datetime.fromisoformat(cache_time)
            current_datetime = datetime.now()
            
            # 如果缓存时间和当前时间不是同一天，说明已过12点
            if cache_datetime.date() != current_datetime.date():
                return True
            
            # 如果是同一天，检查是否已过晚上12点
            midnight = datetime.combine(current_datetime.date(), time(0, 0, 0))
            if current_datetime >= midnight and cache_datetime < midnight:
                return True
                
            return False
        except Exception as e:
            logger.error(f"检查缓存过期时间出错: {e}")
            return True  # 出错时认为已过期

    def _load_cache(self) -> Optional[Dict]:
        """
        加载缓存数据
        """
        try:
            if not os.path.exists(self.cache_file):
                return None
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # 检查缓存是否过期
            if self._is_cache_expired(cache_data.get('cache_time', '')):
                logger.info("密码缓存已过期，将重新获取")
                self._clear_cache()
                return None
                
            return cache_data
        except Exception as e:
            logger.error(f"加载密码缓存出错: {e}")
            return None

    def _save_cache(self, data: Dict) -> None:
        """
        保存缓存数据
        """
        try:
            cache_data = {
                'cache_time': datetime.now().isoformat(),
                'data': data
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
            logger.info("密码缓存已保存")
        except Exception as e:
            logger.error(f"保存密码缓存出错: {e}")

    def _clear_cache(self) -> None:
        """
        清除缓存文件
        """
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                logger.info("密码缓存已清除")
        except Exception as e:
            logger.error(f"清除密码缓存出错: {e}")

    async def get_passwords(self) -> Dict:
        """
        获取密码数据，优先从缓存获取，缓存过期则重新获取
        """
        # 尝试从缓存加载
        cache_data = self._load_cache()
        if cache_data and cache_data.get('data'):
            logger.info("从缓存获取密码数据")
            return cache_data['data']
        
        # 缓存不存在或已过期，重新获取
        try:
            logger.info("正在从网络获取密码数据...")
            password_data = await self.api.map_pwd_daily()
            
            if password_data:
                # 保存到缓存
                self._save_cache(password_data)
                logger.info("密码数据获取成功并已缓存")
                return password_data
            else:
                logger.warning("获取到的密码数据为空")
                return {}
                
        except Exception as e:
            logger.error(f"获取密码数据出错: {e}")
            return {}

    def format_password_message(self, password_data: Dict) -> str:
        """
        格式化密码信息为用户友好的消息
        """
        if not password_data:
            return "🐭 暂时无法获取密码信息，请稍后再试"
        
        message_lines = ["🗝️ 鼠鼠密码 🗝️"]
        message_lines.append("")
        
        for map_name, info in password_data.items():
            password = info.get('password', '未知密码')
            date = info.get('date', '未知日期')
            message_lines.append(f"📍 {map_name}")
            message_lines.append(f"🔑 密码: {password}")
            message_lines.append(f"📅 日期: {date}")
            message_lines.append("")
        
        # 添加缓存提示
        current_time = datetime.now().strftime("%H:%M:%S")
        message_lines.append(f"⏰ 获取时间: {current_time}")
        message_lines.append("💡 密码缓存至晚上12点自动更新")
        
        return "\n".join(message_lines)


class MimaTools:
    """
    鼠鼠密码工具类
    """

    def __init__(self):
        self.cache = MimaCache()

    async def get_mima_info(self) -> str:
        """
        获取密码信息
        """
        try:
            password_data = await self.cache.get_passwords()
            return self.cache.format_password_message(password_data)
        except Exception as e:
            logger.error(f"获取密码信息出错: {e}")
            return "🐭 获取密码信息时发生错误，请稍后再试"

    async def refresh_mima_cache(self) -> str:
        """
        强制刷新密码缓存
        """
        try:
            # 清除现有缓存
            self.cache._clear_cache()
            
            # 重新获取
            password_data = await self.cache.get_passwords()
            
            if password_data:
                return "🔄 密码缓存已刷新\n\n" + self.cache.format_password_message(password_data)
            else:
                return "🐭 刷新密码缓存失败，请稍后再试"
                
        except Exception as e:
            logger.error(f"刷新密码缓存出错: {e}")
            return "🐭 刷新密码缓存时发生错误，请稍后再试"