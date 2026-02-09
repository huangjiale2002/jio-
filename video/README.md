# Google Earth Studio 批量渲染工具

自动化批量导入 ESP 文件并提交渲染任务的 Python 脚本。

## 功能特性

- 🎯 **窗口锁定**：锁定特定窗口，避免其他窗口干扰
- 🖼️ **图像识别**：基于按钮模板图像识别，自动点击操作
- 🖱️ **智能鼠标**：随机贝塞尔曲线轨迹，模拟真实操作
- 🔄 **智能重试**：按钮识别失败时自动重试，等待时间递增（1秒→10秒，共10次）
- 🛡️ **安全模式**：鼠标移到屏幕左上角可紧急停止
- 📝 **详细日志**：记录所有操作过程，便于调试

## 环境要求

### Python 版本
- Python 3.7+

### 依赖库
```bash
pip install pyautogui opencv-python numpy pygetwindow pywin32 pyperclip
```

### 系统要求
- Windows 操作系统
- Google Earth Studio（浏览器版或桌面版）

## 文件结构

```
.
├── google_earth_batch_render_window.py  # 主程序
├── config.py                            # 配置文件（可选）
├── esp/                                 # ESP 文件目录
│   ├── 191.esp
│   ├── 192.esp
│   └── ...
├── button_templates/                    # 按钮模板图片
│   ├── file_menu.png
│   ├── import_menu_item.png
│   ├── earth_studio_project.png
│   ├── open_button.png
│   ├── render_button.png
│   └── submit_button.png
├── batch_render.log                     # 运行日志
└── README.md                            # 本文件
```

## 使用方法

### 1. 准备按钮模板图片

在 `button_templates/` 目录下准备以下按钮的截图：

- `file_menu.png` - "文件"菜单按钮
- `import_menu_item.png` - "导入"菜单项
- `earth_studio_project.png` - "Earth Studio 项目"选项
- `open_button.png` - 文件对话框的"打开"按钮
- `render_button.png` - "渲染"按钮
- `submit_button.png` - 渲染窗口的"Submit"按钮

**截图要求**：
- 清晰、完整地包含按钮
- 建议使用相同的屏幕分辨率和缩放比例
- PNG 格式

### 2. 准备 ESP 文件

将所有 ESP 文件放在 `esp/` 目录下，文件名建议使用数字编号（如 191.esp, 192.esp...）。

### 3. 运行脚本

```bash
python google_earth_batch_render_window.py
```

### 4. 按照提示操作

1. **输入 ESP 文件夹路径**（默认：esp）
2. **选择目标窗口**：从列表中选择 Google Earth Studio 窗口
3. **设置处理范围**：
   - 起始索引（默认：0）
   - 结束索引（默认：全部）
4. **确认开始**：按回车或输入倒计时秒数

### 5. 运行中

- ✅ 脚本会自动执行：导入 ESP → 点击渲染 → 提交任务
- ⚠️ **紧急停止**：将鼠标移到屏幕左上角
- 📝 查看 `batch_render.log` 了解详细执行情况

## 工作流程

每个 ESP 文件的处理流程：

1. **导入文件**
   - 点击"文件"菜单
   - 点击"导入"
   - 点击"Earth Studio 项目"
   - 输入文件路径
   - 点击"打开"

2. **渲染视频**
   - 点击"渲染"按钮

3. **提交任务**
   - 点击"Submit"按钮
   - 等待返回主界面

## 配置说明

可以创建 `config.py` 文件自定义参数：

```python
# PyAutoGUI 安全设置
PYAUTOGUI_PAUSE = 0.5          # 每次操作后的暂停时间
PYAUTOGUI_FAILSAFE = True      # 启用安全模式（鼠标左上角停止）

# 鼠标移动参数
MOUSE_MOVE_DURATION_MIN = 0.2  # 鼠标移动最短时间（秒）
MOUSE_MOVE_DURATION_MAX = 0.4  # 鼠标移动最长时间（秒）
MOUSE_JITTER_RANGE = 2         # 鼠标抖动范围（像素）

# 点击参数
MOUSE_CLICK_PAUSE_MIN = 0.1    # 点击前最短停顿（秒）
MOUSE_CLICK_PAUSE_MAX = 0.3    # 点击前最长停顿（秒）
CLICK_OFFSET_RANGE = 5         # 点击位置随机偏移范围（像素）

# 按钮识别参数
BUTTON_CONFIDENCE = 0.8        # 图像匹配置信度（0-1）
MAX_BUTTON_RETRIES = 10        # 按钮识别最大重试次数

# 等待时间（秒）
WAIT_AFTER_FILE_MENU_MIN = 0.5
WAIT_AFTER_FILE_MENU_MAX = 1.0
WAIT_AFTER_IMPORT_MIN = 0.5
WAIT_AFTER_IMPORT_MAX = 1.0
WAIT_AFTER_ESP_CLICK_MIN = 1.0
WAIT_AFTER_ESP_CLICK_MAX = 1.5
WAIT_AFTER_PATH_INPUT_MIN = 0.3
WAIT_AFTER_PATH_INPUT_MAX = 0.6
WAIT_AFTER_FILE_CONFIRM_MIN = 2.0
WAIT_AFTER_FILE_CONFIRM_MAX = 3.0
WAIT_AFTER_RENDER_MIN = 1.0
WAIT_AFTER_RENDER_MAX = 2.0
WAIT_AFTER_SUBMIT_MIN = 3.0
WAIT_AFTER_SUBMIT_MAX = 5.0
WAIT_BETWEEN_FILES_MIN = 3.0
WAIT_BETWEEN_FILES_MAX = 6.0

# 路径输入
PATH_INPUT_INTERVAL = 0.02     # 路径输入字符间隔（秒）
```

## 重试机制

当按钮识别失败时，脚本会自动重试：

- **重试次数**：10次
- **等待时间**：递增式等待
  - 第1次失败：等待 1 秒
  - 第2次失败：等待 2 秒
  - 第3次失败：等待 3 秒
  - ...
  - 第10次失败：等待 10 秒

每次重试都会重新进行图像识别和鼠标移动。

## 安全模式

脚本启用了 PyAutoGUI 的安全模式：

- **触发方式**：将鼠标移动到屏幕左上角（坐标 0,0）
- **效果**：立即抛出异常并停止执行
- **用途**：紧急情况下快速停止脚本

## 日志文件

所有操作都会记录在 `batch_render.log` 中，包括：

- 窗口选择和激活
- 按钮识别结果
- 点击操作
- 文件导入过程
- 错误和警告信息

## 常见问题

### 1. 找不到按钮

**原因**：
- 按钮模板图片不匹配
- 屏幕分辨率或缩放比例改变
- 窗口被遮挡

**解决**：
- 重新截取按钮模板图片
- 降低 `BUTTON_CONFIDENCE` 值（如 0.7）
- 确保窗口完全可见

### 2. 路径输入失败

**原因**：
- 剪贴板被其他程序占用
- 文件对话框未正确打开

**解决**：
- 确保安装了 `pyperclip`
- 增加等待时间
- 检查日志查看具体错误

### 3. 窗口失去焦点

**原因**：
- 其他程序弹窗
- 系统通知

**解决**：
- 关闭不必要的程序
- 禁用系统通知
- 脚本会自动尝试重新激活窗口

### 4. 脚本运行太慢

**解决**：
- 调整 `config.py` 中的等待时间
- 减少 `MOUSE_MOVE_DURATION`
- 减少 `WAIT_BETWEEN_FILES`

## 注意事项

1. **运行前准备**
   - 确保 Google Earth Studio 已打开
   - 关闭可能弹窗的程序
   - 不要最小化目标窗口

2. **运行中**
   - 不要移动或最小化目标窗口
   - 不要进行其他鼠标键盘操作
   - 可以查看日志监控进度

3. **性能优化**
   - 建议在性能较好的电脑上运行
   - 关闭不必要的后台程序
   - 确保网络连接稳定

## 许可证

MIT License

## 作者

批量渲染自动化工具

## 更新日志

### v1.0.0
- 初始版本
- 窗口锁定功能
- 图像识别点击
- 智能重试机制（10次，递增等待）
- 安全模式支持
