"""
配置文件 - 调整鼠标移动速度和等待时间
修改这个文件中的参数来优化脚本性能
"""

# ==================== 鼠标移动配置 ====================

# 鼠标移动速度（秒）- 极速模式
MOUSE_MOVE_DURATION_MIN = 0.05   # 最快移动时间（0.1秒）
MOUSE_MOVE_DURATION_MAX = 0.1   # 最慢移动时间（0.2秒）
# 说明：使用 pyautogui 内置移动，速度最快

# 鼠标点击前的停顿（秒）
MOUSE_CLICK_PAUSE_MIN = 0.02  # 极短停顿
MOUSE_CLICK_PAUSE_MAX = 0.05  # 极短停顿
# 说明：鼠标移动到按钮后，点击前的等待时间
# 说明：鼠标移动到按钮后，点击前的等待时间

# 鼠标移动随机抖动范围（像素）
MOUSE_JITTER_RANGE = 2
# 说明：移动过程中的随机抖动，模拟真人操作

# 点击位置随机偏移范围（像素）
CLICK_OFFSET_RANGE = 5
# 说明：在按钮中心附近随机偏移，避免每次点击同一位置


# ==================== 等待时间配置 ====================

# 点击"文件"菜单后的等待时间（秒）
WAIT_AFTER_FILE_MENU_MIN = 0.1
WAIT_AFTER_FILE_MENU_MAX = 0.2
# 说明：等待下拉菜单完全展开

# 点击"导入"后的等待时间（秒）
WAIT_AFTER_IMPORT_MIN = 0.1
WAIT_AFTER_IMPORT_MAX = 0.2
# 说明：等待右侧子菜单展开

# 点击"Earth Studio项目"后的等待时间（秒）
WAIT_AFTER_ESP_CLICK_MIN = 0.5
WAIT_AFTER_ESP_CLICK_MAX = 1
# 说明：等待文件选择对话框打开

# 输入文件路径后的等待时间（秒）
WAIT_AFTER_PATH_INPUT_MIN = 0.3
WAIT_AFTER_PATH_INPUT_MAX = 0.6
# 说明：等待输入完成

# 按回车确认后的等待时间（秒）
WAIT_AFTER_FILE_CONFIRM_MIN = 2.0
WAIT_AFTER_FILE_CONFIRM_MAX = 3.0
# 说明：等待文件加载完成，如果电脑慢可以增加

# 点击渲染按钮后的等待时间（秒）
WAIT_AFTER_RENDER_MIN = 2
WAIT_AFTER_RENDER_MAX = 3
# 说明：等待渲染窗口弹出

# 点击Submit后的等待时间（秒）
WAIT_AFTER_SUBMIT_MIN = 3.0
WAIT_AFTER_SUBMIT_MAX = 5.0
# 说明：等待返回主界面

# 文件之间的等待时间（秒）
WAIT_BETWEEN_FILES_MIN = 3.0
WAIT_BETWEEN_FILES_MAX = 6.0
# 说明：处理完一个文件后，开始下一个文件前的等待


# ==================== 识别配置 ====================

# 按钮识别置信度（0-1）
BUTTON_CONFIDENCE = 0.8
# 说明：数值越高要求匹配越精确，如果找不到按钮可以降低到 0.7 或 0.6

# 按钮查找最大重试次数
MAX_BUTTON_RETRIES = 3
# 说明：找不到按钮时的重试次数

# 重试之间的等待时间（秒）
RETRY_WAIT_TIME = 1.0
# 说明：每次重试之间的等待时间


# ==================== 输入配置 ====================

# 文件路径输入速度（秒/字符）
PATH_INPUT_INTERVAL = 0.05
# 说明：每个字符之间的间隔，数值越小输入越快


# ==================== PyAutoGUI 基础配置 ====================

# 每个 PyAutoGUI 操作后的默认暂停时间（秒）
PYAUTOGUI_PAUSE = 0.05  # 极小暂停，加快速度
# 说明：全局暂停时间，影响所有操作，设置过大会严重拖慢速度

# 是否启用安全模式（鼠标移到左上角停止）
PYAUTOGUI_FAILSAFE = True
# 说明：True 启用，False 禁用




# ==================== 使用说明 ====================

"""
如何使用这个配置文件：

1. 直接修改上面的参数值
2. 或者在脚本开始时调用预设：
   
   from config import apply_preset
   apply_preset('fast')  # 快速模式
   apply_preset('slow')  # 慢速模式

3. 参数调整建议：
   
   - 如果操作太快导致失败 → 增加等待时间
   - 如果操作太慢浪费时间 → 减少等待时间
   - 如果找不到按钮 → 降低 BUTTON_CONFIDENCE
   - 如果误识别按钮 → 提高 BUTTON_CONFIDENCE

4. 常见问题：
   
   问题：文件加载失败
   解决：增加 WAIT_AFTER_FILE_CONFIRM_MIN/MAX
   
   问题：菜单未展开就点击
   解决：增加 WAIT_AFTER_FILE_MENU_MIN/MAX
   
   问题：渲染窗口未弹出就操作
   解决：增加 WAIT_AFTER_RENDER_MIN/MAX
   
   问题：处理速度太慢
   解决：使用 apply_preset('fast')

5. 推荐配置：
   
   - 高性能电脑：apply_preset('fast')
   - 普通电脑：默认配置（normal）
   - 低性能电脑：apply_preset('slow')
   - 网络延迟高：apply_preset('very_slow')
"""
