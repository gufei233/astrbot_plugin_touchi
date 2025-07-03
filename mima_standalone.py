from playwright.async_api import async_playwright
from typing import List, Dict, Optional, Callable, Union
import re
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, time
import json
import os
import sys
import logging

# 独立运行的日志配置
class Logger:
    def __init__(self):
        self.logger = logging.getLogger('mima_standalone')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, msg):
        self.logger.info(msg)
    
    def error(self, msg):
        self.logger.error(msg)
    
    def warning(self, msg):
        self.logger.warning(msg)

# 全局日志实例
logger = Logger()

class AcgIceSJZApi:

    def __init__(self):
        self.url = {
            "zb_ss": "https://www.acgice.com/sjz/v/zb_ss",
            "index": "https://www.acgice.com/sjz/v/index",
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
        browser = None
        try:
            async with self.p as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 导航到首页
                await page.goto(self.url["index"], timeout=30000)
                await page.wait_for_selector(".stats.bg-base-500", timeout=15000)

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

        except ImportError as e:
            logger.error(f"Playwright模块导入失败: {e}")
            raise ImportError("需要安装playwright依赖: pip install playwright && playwright install chromium")
        except Exception as e:
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout', 'dns']):
                logger.error(f"网络连接错误: {e}")
                raise Exception("网络连接失败，请检查网络连接后重试")
            elif any(keyword in error_msg for keyword in ['browser', 'chromium', 'playwright']):
                logger.error(f"浏览器相关错误: {e}")
                raise Exception("浏览器启动失败，请重新安装playwright: pip install playwright && playwright install chromium")
            else:
                logger.error(f"获取密码数据时出错: {e}")
                raise

        return captured_data.get("map_pwd", {})


class MimaCache:
    """
    密码缓存管理类，实现缓存到晚上12点自动丢弃的逻辑
    """

    def __init__(self):
        # 使用当前目录下的 data 文件夹
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, "data", "mima_standalone")
        os.makedirs(self.data_dir, exist_ok=True)
        self.cache_file = os.path.join(self.data_dir, "mima_cache.json")
        
        # TXT文件保存路径
        self.output_dir = os.path.join(current_dir, "core", "output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.txt_file = os.path.join(self.output_dir, "mima_passwords.txt")
        
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
                
            # 同时保存到TXT文件
            self._save_txt_file(data)
                
            logger.info("密码缓存已保存")
        except Exception as e:
            logger.error(f"保存密码缓存出错: {e}")
    
    def _save_txt_file(self, data: Dict) -> None:
        """
        保存密码数据到TXT文件
        """
        try:
            # 清理过期的TXT文件
            self._cleanup_old_txt_files()
            
            current_time = datetime.now()
            txt_content = []
            txt_content.append(f"# 鼠鼠密码数据")
            txt_content.append(f"# 生成时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            txt_content.append(f"# 有效期至: {current_time.strftime('%Y-%m-%d')} 23:59:59")
            txt_content.append("")
            
            for map_name, info in data.items():
                password = info.get('password', '未知密码')
                date = info.get('date', '未知日期')
                txt_content.append(f"地图: {map_name}")
                txt_content.append(f"密码: {password}")
                txt_content.append(f"日期: {date}")
                txt_content.append("---")
            
            with open(self.txt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(txt_content))
                
            logger.info(f"密码TXT文件已保存到: {self.txt_file}")
        except Exception as e:
            logger.error(f"保存密码TXT文件出错: {e}")
    
    def _cleanup_old_txt_files(self) -> None:
        """
        清理过期的TXT文件（第二天删除）
        """
        try:
            if os.path.exists(self.txt_file):
                # 获取文件修改时间
                file_mtime = os.path.getmtime(self.txt_file)
                file_date = datetime.fromtimestamp(file_mtime).date()
                current_date = datetime.now().date()
                
                # 如果文件不是今天创建的，删除它
                if file_date < current_date:
                    os.remove(self.txt_file)
                    logger.info("已删除过期的密码TXT文件")
        except Exception as e:
            logger.error(f"清理过期TXT文件出错: {e}")

    def _clear_cache(self) -> None:
        """
        清除缓存文件
        """
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                logger.info("密码缓存已清除")
            if os.path.exists(self.txt_file):
                os.remove(self.txt_file)
                logger.info("密码TXT文件已清除")
        except Exception as e:
            logger.error(f"清除密码缓存出错: {e}")
    
    def read_txt_file(self) -> Optional[str]:
        """
        读取TXT文件内容，供main.py调用
        """
        try:
            # 先清理过期文件
            self._cleanup_old_txt_files()
            
            if os.path.exists(self.txt_file):
                with open(self.txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info("从TXT文件读取密码数据")
                return content
            else:
                logger.warning("TXT文件不存在")
                return None
        except Exception as e:
            logger.error(f"读取TXT文件出错: {e}")
            return None

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
                
        except ImportError as e:
            logger.error(f"Playwright依赖缺失: {e}")
            raise ImportError("需要安装playwright依赖")
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                logger.error(f"网络连接错误: {e}")
                raise Exception("网络连接失败，请检查网络连接")
            elif any(keyword in error_msg for keyword in ['playwright', 'browser', 'chromium']):
                logger.error(f"浏览器相关错误: {e}")
                raise Exception("浏览器相关错误，请重新安装playwright依赖")
            else:
                logger.error(f"获取密码数据出错: {e}")
                raise

    def format_password_message(self, password_data: Dict, error_context: str = None) -> str:
        """
        格式化密码信息为用户友好的消息
        """
        if not password_data:
            if error_context:
                return f"🐭 {error_context}"
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
        except ImportError as e:
            logger.error(f"Playwright依赖缺失: {e}")
            return "🐭 获取密码功能需要playwright依赖\n\n🔧 解决方案:\n1. 检查网络连接\n2. 重新安装playwright:\n   pip install playwright\n   playwright install chromium"
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"获取密码信息出错: {e}")
            
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                return "🐭 获取密码信息失败\n\n🔧 可能的解决方案:\n1. 检查网络连接是否正常\n2. 稍后再试\n3. 如果问题持续，请重新安装playwright依赖"
            elif any(keyword in error_msg for keyword in ['playwright', 'browser', 'chromium']):
                return "🐭 浏览器相关错误\n\n🔧 解决方案:\n1. 重新安装playwright:\n   pip install playwright\n   playwright install chromium\n2. 检查系统是否支持chromium浏览器"
            else:
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
                
        except ImportError as e:
            logger.error(f"Playwright依赖缺失: {e}")
            return "🐭 刷新密码功能需要playwright依赖\n\n🔧 解决方案:\n1. 检查网络连接\n2. 重新安装playwright:\n   pip install playwright\n   playwright install chromium"
        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"刷新密码缓存出错: {e}")
            
            if any(keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
                return "🐭 刷新密码缓存失败\n\n🔧 可能的解决方案:\n1. 检查网络连接是否正常\n2. 稍后再试\n3. 如果问题持续，请重新安装playwright依赖"
            elif any(keyword in error_msg for keyword in ['playwright', 'browser', 'chromium']):
                return "🐭 浏览器相关错误\n\n🔧 解决方案:\n1. 重新安装playwright:\n   pip install playwright\n   playwright install chromium\n2. 检查系统是否支持chromium浏览器"
            else:
                return "🐭 刷新密码缓存时发生错误，请稍后再试"


# 独立调用接口
async def get_mima_async():
    """
    异步版本的密码获取函数，供其他模块调用
    """
    mima_tools = MimaTools()
    return await mima_tools.get_mima_info()


def get_mima_sync():
    """
    同步版本的密码获取函数，供其他模块调用
    """
    try:
        loop = asyncio.get_running_loop()
        # 如果已有事件循环在运行，创建一个任务
        task = loop.create_task(get_mima_async())
        return task
    except RuntimeError:
        # 没有事件循环，直接运行
        return asyncio.run(get_mima_async())


def get_mima_from_txt() -> Optional[str]:
    """
    从TXT文件读取密码信息，供main.py调用
    """
    try:
        cache = MimaCache()
        txt_content = cache.read_txt_file()
        
        if txt_content:
            # 解析TXT内容并格式化为用户友好的消息
            lines = txt_content.split('\n')
            message_lines = ["🗝️ 鼠鼠密码 🗝️"]
            message_lines.append("")
            
            current_map = None
            current_password = None
            current_date = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('地图: '):
                    current_map = line.replace('地图: ', '')
                elif line.startswith('密码: '):
                    current_password = line.replace('密码: ', '')
                elif line.startswith('日期: '):
                    current_date = line.replace('日期: ', '')
                elif line == '---' and current_map and current_password:
                    message_lines.append(f"📍 {current_map}")
                    message_lines.append(f"🔑 密码: {current_password}")
                    message_lines.append(f"📅 日期: {current_date}")
                    message_lines.append("")
                    current_map = current_password = current_date = None
            
            # 添加提示信息
            current_time = datetime.now().strftime("%H:%M:%S")
            message_lines.append(f"⏰ 读取时间: {current_time}")
            message_lines.append("💡 密码数据来自TXT文件缓存")
            
            return "\n".join(message_lines)
        else:
            return None
    except Exception as e:
        logger.error(f"从TXT文件获取密码信息出错: {e}")
        return None


async def main():
    """
    独立运行的主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='鼠鼠密码获取工具（完全独立版本）')
    parser.add_argument('--refresh', action='store_true', help='强制刷新缓存')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--raw', action='store_true', help='输出原始数据')
    
    args = parser.parse_args()
    
    logger.info("完全独立运行模式")
    
    try:
        mima_tools = MimaTools()
        
        if args.refresh:
            result = await mima_tools.refresh_mima_cache()
        else:
            result = await mima_tools.get_mima_info()
        
        if args.raw and args.json:
            # 输出原始JSON数据
            password_data = await mima_tools.cache.get_passwords()
            print(json.dumps(password_data, ensure_ascii=False, indent=2))
        elif args.json:
            # 输出格式化的JSON
            print(json.dumps({"message": result}, ensure_ascii=False, indent=2))
        else:
            # 输出格式化文本
            print(result)
            
    except Exception as e:
        logger.error(f"运行出错: {e}")
        print("🐭 程序运行出错，请检查网络连接或稍后再试")


if __name__ == "__main__":
    asyncio.run(main())
