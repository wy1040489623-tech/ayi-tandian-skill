# -*- coding: utf-8 -*-
"""环境自检：逐项检查运行这套流程需要的东西，缺什么直接说缺什么。"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
problems = []
warnings = []


def ok(msg):
    print(f"[OK]   {msg}")


def bad(msg, fix):
    print(f"[!!]   {msg}")
    problems.append(fix)


def warn(msg, fix):
    print(f"[--]   {msg}")
    warnings.append(fix)


print("=" * 56)
print("大众点评探店笔记生产线 V4 · 环境自检")
print("=" * 56)

# 1. Python
v = sys.version_info
if v >= (3, 8):
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    bad(
        f"Python {v.major}.{v.minor}.{v.micro}，需要 3.8 以上",
        "装一个 Python 3.9 或更新版本，安装时勾选 Add to PATH",
    )

# 2. 必需依赖
for mod, pkg in [
    ("PIL", "pillow"),
    ("requests", "requests"),
    ("websocket", "websocket-client"),
    ("numpy", "numpy"),
    ("cv2", "opencv-python"),
]:
    if importlib.util.find_spec(mod):
        ok(f"依赖 {pkg}")
    else:
        bad(f"缺依赖 {pkg}", "双击 一键安装依赖环境.bat")

# 3. 可选依赖
optional_missing = []
for mod, pkg in [("rapidocr_onnxruntime", "文字/截图过滤"), ("ultralytics", "人像过滤")]:
    if not importlib.util.find_spec(mod):
        optional_missing.append(pkg)
if optional_missing:
    warn(
        f"没装可选组件：{'、'.join(optional_missing)}，采集能跑但这两层过滤会跳过",
        "",
    )
else:
    ok("可选过滤组件齐全")

# 3. Chrome
chrome_paths = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]
if any(os.path.exists(p) for p in chrome_paths):
    ok("Chrome 已安装")
else:
    bad("没找到 Chrome", "装一个 Google Chrome，采集图片依赖它")

# 4. 字体
font_dir = os.path.join(HERE, "ayi-store-note-cover-generator-v4")
fonts = [
    "ZCOOLQingKeHuangYou-Regular.ttf",
    "ZCOOLKuaiLe-Regular.ttf",
    "ZCOOLXiaoWei-Regular.ttf",
    "LongCang-Regular.ttf",
]
missing = [f for f in fonts if not os.path.exists(os.path.join(font_dir, f))]
if not missing:
    ok("封面字体 4/4 齐全")
else:
    bad(f"缺字体 {len(missing)} 个：{', '.join(missing)}", "重新解压压缩包，字体文件被删了")

# 5. 公共素材
if os.path.isdir(os.path.join(HERE, "assets", "ayi_img")):
    ok("公共素材齐")
else:
    warn("assets/ayi_img 不见了，去重和拼图的遮罩会缺失", "重新解压压缩包")

# 6. 脚本
scripts = [
    "xhs_downloader_v4.py",
    "image_dedup_processor_v4.py",
    "food_collage_generator_v4.py",
    "store_note_cover_generator_v4.py",
]
missing = [s for s in scripts if not os.path.exists(os.path.join(HERE, s))]
if not missing:
    ok("核心脚本 4/4 齐全")
else:
    bad(f"缺脚本：{', '.join(missing)}", "重新解压压缩包")

# 7. 目录可写
try:
    probe = os.path.join(HERE, "input")
    os.makedirs(probe, exist_ok=True)
    test_file = os.path.join(probe, ".write_test")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("ok")
    os.remove(test_file)
    ok("目录可写")
except OSError as e:
    bad(f"目录不可写：{e}", "把整个文件夹挪到非系统目录（比如 D 盘）再试")

# 8. 9222 端口
import socket

s = socket.socket()
s.settimeout(0.5)
port_open = s.connect_ex(("127.0.0.1", 9222)) == 0
s.close()
if port_open:
    ok("Chrome 调试端口 9222 已在运行")
else:
    warn("采集前记得双击 启动Chrome调试模式.bat，并登录小红书", "")

print("-" * 56)
if problems:
    print(f"有 {len(problems)} 个问题要先解决：")
    for i, p in enumerate(problems, 1):
        print(f"  {i}. {p}")
    print("\n解决后重新双击 自检.bat。")
    sys.exit(1)

if warnings:
    print("环境可用，但有两件事要注意：")
    for w in warnings:
        print(f"  - {w}")

print("环境没问题，可以开始跑了。")
print("下一步：把店铺截图放进 input/，然后看 快速开始.md")
