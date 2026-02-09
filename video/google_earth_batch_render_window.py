"""
Google Earth 批量视频渲染自动化脚本 - 窗口锁定版本
功能：锁定特定窗口，避免其他窗口干扰
特性：窗口句柄锁定、图像识别、随机鼠标轨迹
"""

import pyautogui
import time
import random
import numpy as np
from pathlib import Path
import cv2
import logging
import pygetwindow as gw
import win32gui
import win32con
import win32api

# 尝试导入 pyperclip，如果没有则使用备用方案
try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False
    logging.warning("未安装 pyperclip，将使用备用输入方案")

# 导入配置文件
try:
    import config
except ImportError:
    print("⚠️ 未找到 config.py，使用默认配置")
    config = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_render.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class WindowLockedRenderer:
    def __init__(self, esp_folder, button_images_folder='button_templates'):
        """
        初始化窗口锁定渲染器
        :param esp_folder: ESP 文件所在文件夹
        :param button_images_folder: 按钮模板图片文件夹
        """
        self.esp_folder = Path(esp_folder)
        self.button_images_folder = Path(button_images_folder)
        self.target_window = None
        self.window_handle = None
        
        # 设置 PyAutoGUI 安全参数
        if config:
            pyautogui.PAUSE = config.PYAUTOGUI_PAUSE
            pyautogui.FAILSAFE = config.PYAUTOGUI_FAILSAFE
        else:
            pyautogui.PAUSE = 0.5
            pyautogui.FAILSAFE = True
        
        logging.info(f"初始化完成，ESP 文件夹: {self.esp_folder}")
    
    def find_earth_studio_window(self):
        """
        查找 Google Earth Studio 窗口
        :return: 窗口对象或 None
        """
        logging.info("正在查找 Google Earth Studio 窗口...")
        
        # 可能的窗口标题关键词
        keywords = [
            'Earth Studio',
            'Google Earth Studio',
            'earth studio',
            'Chrome',  # 如果是在浏览器中运行
            'Edge',
            'Firefox'
        ]
        
        all_windows = gw.getAllWindows()
        
        print("\n找到的所有窗口：")
        valid_windows = []
        for i, window in enumerate(all_windows):
            if window.title and len(window.title) > 0:  # 只显示有标题的窗口
                print(f"{i + 1}. {window.title}")
                valid_windows.append(window)
        
        # 自动查找匹配的窗口
        matched_windows = []
        for window in valid_windows:
            for keyword in keywords:
                if keyword.lower() in window.title.lower():
                    matched_windows.append(window)
                    break
        
        if matched_windows:
            print(f"\n自动找到 {len(matched_windows)} 个可能的窗口：")
            for i, window in enumerate(matched_windows):
                print(f"{i + 1}. {window.title}")
            
            choice = input(f"\n选择窗口编号 (1-{len(matched_windows)}，默认1): ").strip()
            idx = int(choice) - 1 if choice else 0
            
            if 0 <= idx < len(matched_windows):
                self.target_window = matched_windows[idx]
                try:
                    self.window_handle = self.target_window._hWnd
                    logging.info(f"已锁定窗口: {self.target_window.title}")
                    logging.info(f"窗口句柄: {self.window_handle}")
                    return self.target_window
                except Exception as e:
                    logging.error(f"获取窗口句柄失败: {e}")
                    return None
        
        # 手动选择
        print("\n未找到匹配的窗口，请手动选择")
        choice = input(f"输入窗口编号 (1-{len(valid_windows)}): ").strip()
        
        if choice:
            idx = int(choice) - 1
            if 0 <= idx < len(valid_windows):
                self.target_window = valid_windows[idx]
                try:
                    self.window_handle = self.target_window._hWnd
                    logging.info(f"已锁定窗口: {self.target_window.title}")
                    logging.info(f"窗口句柄: {self.window_handle}")
                    return self.target_window
                except Exception as e:
                    logging.error(f"获取窗口句柄失败: {e}")
                    return None
        
        logging.error("未选择窗口")
        return None
    
    def activate_window(self):
        """激活并置顶目标窗口"""
        if not self.target_window:
            logging.error("未设置目标窗口")
            return False
        
        try:
            # 重新获取窗口句柄（防止句柄失效）
            try:
                self.window_handle = self.target_window._hWnd
            except:
                # 如果获取失败，尝试重新查找窗口
                logging.warning("窗口句柄失效，尝试重新查找窗口...")
                all_windows = gw.getAllWindows()
                for window in all_windows:
                    if window.title == self.target_window.title:
                        self.target_window = window
                        self.window_handle = window._hWnd
                        logging.info("已重新找到窗口")
                        break
                else:
                    logging.error("无法重新找到窗口")
                    return False
            
            # 如果窗口最小化，先恢复
            try:
                if self.target_window.isMinimized:
                    self.target_window.restore()
                    time.sleep(0.5)
            except:
                pass
            
            # 激活窗口
            try:
                self.target_window.activate()
                time.sleep(0.3)
            except Exception as e:
                logging.warning(f"activate() 失败: {e}，尝试使用 Windows API")
            
            # 使用 Windows API 确保窗口在前台
            try:
                # 先尝试显示窗口
                win32gui.ShowWindow(self.window_handle, win32con.SW_RESTORE)
                time.sleep(0.2)
                
                # 再设置为前台窗口
                win32gui.SetForegroundWindow(self.window_handle)
                time.sleep(0.2)
            except Exception as e:
                logging.warning(f"Windows API 激活失败: {e}")
                # 尝试备用方法：点击窗口
                try:
                    region = self.get_window_region()
                    if region:
                        # 点击窗口中心
                        center_x = region[0] + region[2] // 2
                        center_y = region[1] + region[3] // 2
                        pyautogui.click(center_x, center_y)
                        time.sleep(0.3)
                        logging.info("通过点击激活窗口")
                except Exception as e2:
                    logging.error(f"点击激活也失败: {e2}")
                    return False
            
            logging.info("窗口已激活并置顶")
            return True
        
        except Exception as e:
            logging.error(f"激活窗口失败: {e}")
            return False
    
    def ensure_window_active(self):
        """确保窗口处于激活状态"""
        try:
            # 检查窗口是否仍然存在
            if not self.target_window or not self.window_handle:
                logging.error("窗口对象或句柄丢失")
                return False
            
            # 尝试获取前台窗口
            try:
                foreground = win32gui.GetForegroundWindow()
                if foreground != self.window_handle:
                    logging.warning("窗口失去焦点，重新激活...")
                    return self.activate_window()
            except Exception as e:
                logging.warning(f"检查前台窗口失败: {e}，尝试重新激活")
                return self.activate_window()
            
            return True
        
        except Exception as e:
            logging.error(f"检查窗口状态失败: {e}")
            # 尝试重新激活
            return self.activate_window()
    
    def get_window_region(self):
        """
        获取窗口区域坐标
        :return: (left, top, width, height)
        """
        if not self.target_window:
            return None
        
        try:
            # 尝试刷新窗口信息
            try:
                # 重新获取窗口对象
                all_windows = gw.getAllWindows()
                for window in all_windows:
                    if window._hWnd == self.window_handle:
                        self.target_window = window
                        break
            except:
                pass
            
            return (
                self.target_window.left,
                self.target_window.top,
                self.target_window.width,
                self.target_window.height
            )
        except Exception as e:
            logging.error(f"获取窗口区域失败: {e}")
            return None
    
    def get_esp_files(self):
        """获取所有 ESP 文件并排序"""
        esp_files = sorted(self.esp_folder.glob('*.esp'))
        logging.info(f"找到 {len(esp_files)} 个 ESP 文件")
        return esp_files
    
    def random_mouse_move(self, target_x, target_y, duration=None):
        """
        随机贝塞尔曲线鼠标移动
        :param target_x: 目标 X 坐标
        :param target_y: 目标 Y 坐标
        :param duration: 移动持续时间（秒），从 config 读取
        """
        if duration is None:
            if config:
                duration = random.uniform(config.MOUSE_MOVE_DURATION_MIN, config.MOUSE_MOVE_DURATION_MAX)
            else:
                # 默认快速移动：0.2-0.4秒
                duration = random.uniform(0.2, 0.4)
        
        current_x, current_y = pyautogui.position()
        
        # 使用缓动函数模拟自然移动
        steps = int(duration * 100)
        for i in range(steps):
            t = i / steps
            eased_t = self._ease_in_out_quad(t)
            
            x = current_x + (target_x - current_x) * eased_t
            y = current_y + (target_y - current_y) * eased_t
            
            # 添加微小随机抖动
            jitter = config.MOUSE_JITTER_RANGE if config else 2
            x += random.uniform(-jitter, jitter)
            y += random.uniform(-jitter, jitter)
            pyautogui.moveTo(x, y, duration=0)
            time.sleep(duration / steps)
        
        # 确保最终到达目标位置（使用极短时间）
        pyautogui.moveTo(target_x, target_y, duration=0)
    
    def _ease_in_out_quad(self, t):
        """二次缓动函数"""
        if t < 0.5:
            return 2 * t * t
        else:
            return -1 + (4 - 2 * t) * t
    
    def find_button_in_window(self, button_template_path, confidence=None):
        """
        在锁定的窗口中查找按钮
        :param button_template_path: 按钮模板图片路径
        :param confidence: 匹配置信度 (0-1)
        :return: 按钮中心坐标 (x, y) 或 None
        """
        if confidence is None:
            confidence = config.BUTTON_CONFIDENCE if config else 0.8
        
        # 确保窗口激活
        self.ensure_window_active()
        
        try:
            # 获取窗口区域
            region = self.get_window_region()
            
            if region:
                # 只在窗口区域内搜索
                location = pyautogui.locateOnScreen(
                    str(button_template_path),
                    confidence=confidence,
                    region=region
                )
            else:
                # 如果无法获取窗口区域，在全屏搜索
                location = pyautogui.locateOnScreen(
                    str(button_template_path),
                    confidence=confidence
                )
            
            if location:
                center = pyautogui.center(location)
                logging.info(f"找到按钮: {button_template_path.name} at ({center.x}, {center.y})")
                return center.x, center.y
            else:
                logging.warning(f"未找到按钮: {button_template_path.name}")
                return None
        
        except Exception as e:
            logging.error(f"查找按钮时出错: {e}")
            return None
    
    def click_button(self, button_name, max_retries=10):
        """
        点击指定按钮
        :param button_name: 按钮名称
        :param max_retries: 最大重试次数（默认10次）
        :return: 是否成功点击
        """
        # 确保窗口激活
        self.ensure_window_active()
        
        button_template = self.button_images_folder / f"{button_name}.png"
        
        if not button_template.exists():
            logging.error(f"按钮模板不存在: {button_template}")
            return False
        
        for attempt in range(max_retries):
            # 检查安全模式：鼠标在左上角则停止
            mouse_x, mouse_y = pyautogui.position()
            if mouse_x == 0 and mouse_y == 0:
                logging.warning("⚠️ 检测到鼠标在左上角，触发安全停止！")
                raise pyautogui.FailSafeException("用户触发安全停止")
            
            logging.info(f"尝试点击按钮 '{button_name}' (第 {attempt + 1}/{max_retries} 次)")
            
            # 每次都重新识别按钮位置
            position = self.find_button_in_window(button_template)
            
            if position:
                x, y = position
                # 添加小范围随机偏移
                offset = config.CLICK_OFFSET_RANGE if config else 5
                x += random.randint(-offset, offset)
                y += random.randint(-offset, offset)
                
                # 每次都执行鼠标滑动
                self.random_mouse_move(x, y)
                
                # 点击前的停顿
                if config:
                    pause = random.uniform(config.MOUSE_CLICK_PAUSE_MIN, config.MOUSE_CLICK_PAUSE_MAX)
                else:
                    pause = random.uniform(0.1, 0.3)
                time.sleep(pause)
                
                pyautogui.click()
                logging.info(f"✅ 成功点击按钮 '{button_name}'")
                return True
            
            # 未找到按钮，渐进式等待后重试
            # 第1次等1秒，第2次等2秒...第10次等10秒
            if attempt < max_retries - 1:  # 最后一次不需要等待
                retry_wait = min(attempt + 1, 10)
                logging.info(f"未找到按钮，等待 {retry_wait} 秒后重试...")
                time.sleep(retry_wait)
        
        logging.error(f"❌ 无法找到或点击按钮 '{button_name}'，已重试 {max_retries} 次")
        return False
    
    def import_esp_file(self, esp_file_path):
        """
        导入 ESP 文件
        完整流程：文件菜单 → 导入 → Earth Studio项目 → 直接输入路径 → Alt+O打开
        :param esp_file_path: ESP 文件路径
        :return: 是否成功导入
        """
        logging.info(f"开始导入文件: {esp_file_path.name}")
        
        # 确保窗口激活
        self.ensure_window_active()
        
        # 1. 点击"文件"菜单
        logging.info("步骤 1/5: 点击文件菜单")
        if not self.click_button('file_menu'):
            return False
        if config:
            time.sleep(random.uniform(config.WAIT_AFTER_FILE_MENU_MIN, config.WAIT_AFTER_FILE_MENU_MAX))
        else:
            time.sleep(random.uniform(0.5, 1.0))
        
        # 2. 点击"导入"
        logging.info("步骤 2/5: 点击导入选项")
        if not self.click_button('import_menu_item'):
            return False
        if config:
            time.sleep(random.uniform(config.WAIT_AFTER_IMPORT_MIN, config.WAIT_AFTER_IMPORT_MAX))
        else:
            time.sleep(random.uniform(0.5, 1.0))
        
        # 3. 点击"Earth Studio项目"
        logging.info("步骤 3/5: 点击 Earth Studio 项目")
        if not self.click_button('earth_studio_project'):
            return False
        if config:
            time.sleep(random.uniform(config.WAIT_AFTER_ESP_CLICK_MIN, config.WAIT_AFTER_ESP_CLICK_MAX))
        else:
            time.sleep(random.uniform(1.0, 1.5))
        
        # 4. 文件对话框弹出后，直接输入文件路径
        logging.info("步骤 4/5: 输入文件路径")
        file_path_str = str(esp_file_path.absolute())
        logging.info(f"文件路径: {file_path_str}")
        
        # 使用剪贴板粘贴路径（每次都重新复制）
        if HAS_PYPERCLIP:
            # 每次都重新复制到剪贴板
            pyperclip.copy(file_path_str)
            time.sleep(0.2)
            
            # 粘贴
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.3)
            
            logging.info("✅ 路径已粘贴")
        else:
            logging.error("❌ 未安装 pyperclip，无法输入路径")
            return False
        
        if config:
            time.sleep(random.uniform(config.WAIT_AFTER_PATH_INPUT_MIN, config.WAIT_AFTER_PATH_INPUT_MAX))
        else:
            time.sleep(random.uniform(0.5, 0.8))
        
        # 5. 点击"打开"按钮
        logging.info("步骤 5/5: 点击打开按钮")
        if not self.click_button('open_button'):
            logging.warning("未找到打开按钮，尝试按 Enter 键")
            pyautogui.press('enter')
        
        # 等待文件加载
        if config:
            wait_time = random.uniform(config.WAIT_AFTER_FILE_CONFIRM_MIN, config.WAIT_AFTER_FILE_CONFIRM_MAX)
        else:
            wait_time = random.uniform(2.0, 3.0)
        
        logging.info(f"等待文件加载 {wait_time:.1f} 秒...")
        time.sleep(wait_time)
        
        logging.info(f"✅ 文件导入完成: {esp_file_path.name}")
        return True
    
    def render_video(self):
        """点击渲染按钮"""
        logging.info("点击渲染按钮")
        self.ensure_window_active()
        
        if not self.click_button('render_button'):
            return False
        
        if config:
            time.sleep(random.uniform(config.WAIT_AFTER_RENDER_MIN, config.WAIT_AFTER_RENDER_MAX))
        else:
            time.sleep(random.uniform(1.0, 2.0))
        return True
    
    def submit_render(self):
        """在渲染窗口中点击 Submit"""
        logging.info("点击 Submit 按钮")
        self.ensure_window_active()
        
        if not self.click_button('submit_button'):
            return False
        
        if config:
            wait_time = random.uniform(config.WAIT_AFTER_SUBMIT_MIN, config.WAIT_AFTER_SUBMIT_MAX)
        else:
            wait_time = random.uniform(3.0, 5.0)
        
        logging.info(f"等待 {wait_time:.1f} 秒返回主界面...")
        time.sleep(wait_time)
        
        return True
    
    def process_single_esp(self, esp_file):
        """处理单个 ESP 文件"""
        logging.info(f"\n{'='*60}")
        logging.info(f"处理文件: {esp_file.name}")
        logging.info(f"{'='*60}")
        
        try:
            # 确保窗口激活
            self.ensure_window_active()
            
            # 1. 导入
            logging.info("步骤 1/3: 导入 ESP 文件")
            if not self.import_esp_file(esp_file):
                logging.error(f"❌ 导入失败: {esp_file.name}")
                return False
            
            # 2. 渲染
            logging.info("步骤 2/3: 点击渲染按钮")
            if not self.render_video():
                logging.error(f"❌ 渲染失败: {esp_file.name}")
                return False
            
            # 3. 提交
            logging.info("步骤 3/3: 提交渲染任务")
            if not self.submit_render():
                logging.error(f"❌ 提交失败: {esp_file.name}")
                return False
            
            logging.info(f"✅ 成功处理: {esp_file.name}")
            return True
        
        except Exception as e:
            logging.error(f"❌ 处理文件时出错 {esp_file.name}: {e}")
            return False
    
    def batch_process(self, start_index=0, end_index=None, wait_between=True):
        """批量处理 ESP 文件"""
        esp_files = self.get_esp_files()
        
        if not esp_files:
            logging.error("未找到 ESP 文件")
            return
        
        if end_index is None:
            end_index = len(esp_files)
        
        esp_files = esp_files[start_index:end_index]
        
        logging.info(f"\n开始批量处理 {len(esp_files)} 个文件")
        logging.info(f"从索引 {start_index} 到 {end_index - 1}")
        
        success_count = 0
        fail_count = 0
        
        for i, esp_file in enumerate(esp_files, start=start_index):
            logging.info(f"\n进度: {i - start_index + 1}/{len(esp_files)}")
            
            if self.process_single_esp(esp_file):
                success_count += 1
            else:
                fail_count += 1
                user_input = input("处理失败，是否继续？(y/n): ")
                if user_input.lower() != 'y':
                    break
            
            # 文件之间的等待
            if wait_between and i < end_index - 1:
                if config:
                    wait_time = random.uniform(config.WAIT_BETWEEN_FILES_MIN, config.WAIT_BETWEEN_FILES_MAX)
                else:
                    wait_time = random.uniform(3.0, 6.0)
                logging.info(f"等待 {wait_time:.1f} 秒后处理下一个文件...")
                time.sleep(wait_time)
        
        logging.info(f"\n{'='*60}")
        logging.info(f"批量处理完成")
        logging.info(f"成功: {success_count} 个")
        logging.info(f"失败: {fail_count} 个")
        logging.info(f"{'='*60}")


def main():
    """主函数"""
    print("Google Earth 批量视频渲染工具 - 窗口锁定版")
    print("="*60)
    
    # 配置参数
    esp_folder = input("请输入 ESP 文件夹路径 (默认: esp): ").strip()
    if not esp_folder:
        esp_folder = "esp"
    
    # 创建渲染器
    renderer = WindowLockedRenderer(esp_folder)
    
    # 查找并锁定窗口
    print("\n" + "="*60)
    print("步骤 1: 选择要锁定的窗口")
    print("="*60)
    
    if not renderer.find_earth_studio_window():
        print("❌ 未选择窗口，退出")
        return
    
    print(f"\n✅ 已锁定窗口: {renderer.target_window.title}")
    
    # 激活窗口
    print("\n激活窗口...")
    renderer.activate_window()
    time.sleep(1)
    
    # 获取处理范围
    esp_files = renderer.get_esp_files()
    print(f"\n找到 {len(esp_files)} 个 ESP 文件")
    
    start_idx = input(f"起始索引 (0-{len(esp_files)-1}, 默认 0): ").strip()
    start_idx = int(start_idx) if start_idx else 0
    
    end_idx = input(f"结束索引 (1-{len(esp_files)}, 默认全部): ").strip()
    end_idx = int(end_idx) if end_idx else None
    
    print("\n" + "="*60)
    print("准备开始批量处理...")
    print("="*60)
    print("✅ 窗口已锁定，不会受其他窗口干扰")
    print("⚠️ 将鼠标移到屏幕左上角可紧急停止")
    print("⚠️ 处理过程中请不要最小化目标窗口")
    
    countdown = input("\n按回车开始，或输入倒计时秒数: ").strip()
    countdown = int(countdown) if countdown else 5
    
    for i in range(countdown, 0, -1):
        print(f"倒计时: {i} 秒...")
        time.sleep(1)
    
    print("\n开始执行！\n")
    
    # 开始批量处理
    renderer.batch_process(start_index=start_idx, end_index=end_idx)


if __name__ == "__main__":
    main()
