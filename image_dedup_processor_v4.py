"""
探店笔记 V4 级高阶图像全自动去重引擎 (image_dedup_processor_v4.py)
核心特性：
1. 几何微形变：随机 2°~12° 微倾斜 + 最大无黑边内切矩形裁剪。
2. 色彩空间微抖动：微观亮度/对比度/饱和度 ±1%~2% 扰动，丰富食欲感并重构色彩直方图。
3. 动态网格遮罩：lines.png 动态微缩放与微位移 + 2% 极低透明度全图覆盖（破坏全局 DCT 频域哈希）。
4. 隐形品类 Icon：根据商铺品类智能选取 1~2 个线条图标，微缩至 12~24px，1.5%~3% 极低透明度随机置于角落（注入局部特征指纹）。
5. 商铺级设备指纹锁定：同一商铺/批次固定绑定同款热门旗舰机型（如 iPhone 15 Pro 或 Xiaomi 14），注入连贯拍摄时间戳 EXIF，模拟真实连贯实拍。
"""

import os
import sys
import math
import random
import hashlib
import datetime
import re
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageEnhance

sys.stdout.reconfigure(encoding='utf-8')

# 基础资源路径 (支持动态自适应定位 lines.png 与 ico 图标库，无论是整包分发还是项目根目录运行均可秒级定位)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_asset_paths() -> Tuple[str, str]:
    candidate_dirs = [
        os.path.join(CURRENT_DIR, "assets", "ayi_img"),
        os.path.join(CURRENT_DIR, "..", "assets", "ayi_img"),
        os.path.join(CURRENT_DIR, "..", "..", "assets", "ayi_img"),
        os.path.join(CURRENT_DIR, "ayi_img"),
        os.path.join(CURRENT_DIR, "..", "ayi_img"),
        os.path.join(CURRENT_DIR, "..", "..", "ayi_img"),
    ]
    for d in candidate_dirs:
        norm_d = os.path.normpath(d)
        lines_f = os.path.join(norm_d, "lines.png")
        ico_d = os.path.join(norm_d, "ico")
        if os.path.exists(lines_f) and os.path.exists(ico_d):
            return lines_f, ico_d
    return os.path.join(CURRENT_DIR, "lines.png"), os.path.join(CURRENT_DIR, "ico")

DEFAULT_LINES_PATH, DEFAULT_ICO_DIR = get_asset_paths()

# 真实主流旗舰手机 EXIF 设备池 (支持指定机型与模糊匹配)
DEVICE_PROFILES = [
    # 苹果 Apple 系列
    {
        "id": "iphone-15-pro-max",
        "name": "Apple iPhone 15 Pro Max",
        "make": "Apple",
        "model": "iPhone 15 Pro Max",
        "software": "17.4.1",
        "lens": "iPhone 15 Pro Max back triple camera 6.86mm f/1.78",
        "aliases": ["iphone 15 pro max", "iphone15promax", "苹果15promax", "15promax", "15 pro max"]
    },
    {
        "id": "iphone-15-pro",
        "name": "Apple iPhone 15 Pro",
        "make": "Apple",
        "model": "iPhone 15 Pro",
        "software": "17.4.1",
        "lens": "iPhone 15 Pro back triple camera 6.86mm f/1.78",
        "aliases": ["iphone 15 pro", "iphone15pro", "苹果15pro", "15pro", "15 pro"]
    },
    {
        "id": "iphone-15",
        "name": "Apple iPhone 15",
        "make": "Apple",
        "model": "iPhone 15",
        "software": "17.4.1",
        "lens": "iPhone 15 back dual camera 5.96mm f/1.6",
        "aliases": ["iphone 15", "iphone15", "苹果15", "15"]
    },
    {
        "id": "iphone-14-pro-max",
        "name": "Apple iPhone 14 Pro Max",
        "make": "Apple",
        "model": "iPhone 14 Pro Max",
        "software": "17.3.1",
        "lens": "iPhone 14 Pro Max back triple camera 6.86mm f/1.78",
        "aliases": ["iphone 14 pro max", "iphone14promax", "苹果14promax", "14promax", "14 pro max"]
    },
    {
        "id": "iphone-14-pro",
        "name": "Apple iPhone 14 Pro",
        "make": "Apple",
        "model": "iPhone 14 Pro",
        "software": "17.3.1",
        "lens": "iPhone 14 Pro back triple camera 6.86mm f/1.78",
        "aliases": ["iphone 14 pro", "iphone14pro", "苹果14pro", "14pro", "14 pro"]
    },
    {
        "id": "iphone-13-pro",
        "name": "Apple iPhone 13 Pro",
        "make": "Apple",
        "model": "iPhone 13 Pro",
        "software": "16.6.1",
        "lens": "iPhone 13 Pro back triple camera 5.7mm f/1.5",
        "aliases": ["iphone 13 pro", "iphone13pro", "苹果13pro", "13pro", "13 pro", "iphone 13", "苹果13"]
    },
    # 小米 Xiaomi 系列
    {
        "id": "xiaomi-14-ultra",
        "name": "Xiaomi 14 Ultra",
        "make": "Xiaomi",
        "model": "Xiaomi 14 Ultra",
        "software": "HyperOS 1.0.30.0",
        "lens": "Leica Summilux 23mm f/1.63",
        "aliases": ["xiaomi 14 ultra", "xiaomi14ultra", "小米14ultra", "14ultra", "14 ultra"]
    },
    {
        "id": "xiaomi-14-pro",
        "name": "Xiaomi 14 Pro",
        "make": "Xiaomi",
        "model": "Xiaomi 14 Pro",
        "software": "HyperOS 1.0.28.0",
        "lens": "Leica Summilux 23mm f/1.42",
        "aliases": ["xiaomi 14 pro", "xiaomi14pro", "小米14pro"]
    },
    {
        "id": "xiaomi-14",
        "name": "Xiaomi 14",
        "make": "Xiaomi",
        "model": "Xiaomi 14",
        "software": "HyperOS 1.0.28.0",
        "lens": "Leica Summilux 23mm f/1.6",
        "aliases": ["xiaomi 14", "xiaomi14", "小米14", "小米 14"]
    },
    {
        "id": "xiaomi-13-pro",
        "name": "Xiaomi 13 Pro",
        "make": "Xiaomi",
        "model": "Xiaomi 13 Pro",
        "software": "MIUI 14.0.31",
        "lens": "Leica 23mm f/1.9",
        "aliases": ["xiaomi 13 pro", "xiaomi13pro", "小米13pro"]
    },
    {
        "id": "xiaomi-13",
        "name": "Xiaomi 13",
        "make": "Xiaomi",
        "model": "Xiaomi 13",
        "software": "MIUI 14.0.27",
        "lens": "Leica 23mm f/1.8",
        "aliases": ["xiaomi 13", "xiaomi13", "小米13", "小米 13"]
    },
    # 华为 HUAWEI 系列
    {
        "id": "huawei-mate-60-pro",
        "name": "HUAWEI Mate 60 Pro",
        "make": "HUAWEI",
        "model": "HUAWEI Mate 60 Pro",
        "software": "HarmonyOS 4.0.0",
        "lens": "Ultra Aperture XMAGE 24mm f/1.4",
        "aliases": ["huawei mate 60 pro", "mate 60 pro", "mate60pro", "华为mate60pro", "mate60 pro", "华为mate60 pro"]
    },
    {
        "id": "huawei-mate-60",
        "name": "HUAWEI Mate 60",
        "make": "HUAWEI",
        "model": "HUAWEI Mate 60",
        "software": "HarmonyOS 4.0.0",
        "lens": "Ultra Aperture XMAGE 24mm f/1.4",
        "aliases": ["huawei mate 60", "mate 60", "mate60", "华为mate60", "华为 mate 60"]
    },
    {
        "id": "huawei-pura-70-pro",
        "name": "HUAWEI Pura 70 Pro",
        "make": "HUAWEI",
        "model": "HUAWEI Pura 70 Pro",
        "software": "HarmonyOS 4.2.0",
        "lens": "Ultra Lighting XMAGE 24.5mm f/1.4",
        "aliases": ["huawei pura 70 pro", "pura 70 pro", "pura70pro", "华为pura70pro", "pura70", "华为pura70"]
    },
    {
        "id": "huawei-p60-pro",
        "name": "HUAWEI P60 Pro",
        "make": "HUAWEI",
        "model": "HUAWEI P60 Pro",
        "software": "HarmonyOS 3.1.0",
        "lens": "Ultra Lighting XMAGE 24.5mm f/1.4",
        "aliases": ["huawei p60 pro", "p60 pro", "p60pro", "华为p60pro", "华为p60", "p60"]
    },
    # vivo 系列
    {
        "id": "vivo-x100-pro",
        "name": "vivo X100 Pro",
        "make": "vivo",
        "model": "vivo X100 Pro",
        "software": "OriginOS 4",
        "lens": "ZEISS APO 50mm f/1.75",
        "aliases": ["vivo x100 pro", "vivox100pro", "x100pro", "x100 pro"]
    },
    {
        "id": "vivo-x100",
        "name": "vivo X100",
        "make": "vivo",
        "model": "vivo X100",
        "software": "OriginOS 4",
        "lens": "ZEISS 23mm f/1.57",
        "aliases": ["vivo x100", "vivox100", "x100"]
    },
    {
        "id": "vivo-x90-pro-plus",
        "name": "vivo X90 Pro+",
        "make": "vivo",
        "model": "vivo X90 Pro+",
        "software": "OriginOS 3",
        "lens": "ZEISS 1-inch 23mm f/1.75",
        "aliases": ["vivo x90 pro+", "vivox90pro+", "x90pro+", "x90 pro+", "vivo x90 pro", "x90pro", "x90"]
    },
    # OPPO 系列
    {
        "id": "oppo-find-x7-ultra",
        "name": "OPPO Find X7 Ultra",
        "make": "OPPO",
        "model": "OPPO Find X7 Ultra",
        "software": "ColorOS 14",
        "lens": "Hasselblad Mobile Camera 23mm f/1.8",
        "aliases": ["oppo find x7 ultra", "find x7 ultra", "findx7ultra", "x7ultra"]
    },
    {
        "id": "oppo-find-x7",
        "name": "OPPO Find X7",
        "make": "OPPO",
        "model": "OPPO Find X7",
        "software": "ColorOS 14",
        "lens": "Hasselblad Mobile Camera 23mm f/1.6",
        "aliases": ["oppo find x7", "find x7", "findx7", "x7"]
    },
    {
        "id": "oppo-find-x6-pro",
        "name": "OPPO Find X6 Pro",
        "make": "OPPO",
        "model": "OPPO Find X6 Pro",
        "software": "ColorOS 13.1",
        "lens": "Hasselblad Mobile Camera 23mm f/1.8",
        "aliases": ["oppo find x6 pro", "find x6 pro", "findx6pro", "x6pro"]
    },
    # 荣耀 Honor 系列
    {
        "id": "honor-magic6-pro",
        "name": "Honor Magic6 Pro",
        "make": "HONOR",
        "model": "HONOR BVL-AN16",
        "software": "MagicOS 8.0",
        "lens": "Ultra Wide Aperture 27mm f/1.4-f/2.0",
        "aliases": ["honor magic6 pro", "magic6 pro", "magic6pro", "荣耀magic6pro", "荣耀magic6", "magic6"]
    },
    {
        "id": "honor-magic5-pro",
        "name": "Honor Magic5 Pro",
        "make": "HONOR",
        "model": "HONOR PGT-AN10",
        "software": "MagicOS 7.1",
        "lens": "Wide Aperture 23mm f/1.6",
        "aliases": ["honor magic5 pro", "magic5 pro", "magic5pro", "荣耀magic5pro", "magic5"]
    }
]

# 餐饮品类关键词与对应 Icon 映射字典 (智能路由)
CATEGORY_ICON_MAP = {
    "火锅": ["火锅.png", "辣椒.png", "肉丸串.png", "香肠串.png", "青菜.png", "贡丸串.png", "辣酱罐.png"],
    "串串": ["肉丸串.png", "香肠串.png", "贡丸串.png", "脆皮烤肠.png", "辣椒.png"],
    "烧烤": ["烤肉.png", "铁板鱿鱼.png", "脆皮烤肠.png", "香肠串.png", "铁板豆腐.png", "螺旋烤肠.png", "啤酒.png"],
    "烤肉": ["烤肉.png", "肉卷.png", "牛排.png", "铁板鱿鱼.png", "生菜.png"],
    "日料": ["寿司.png", "拉面.png", "紫菜包饭.png", "豆腐味噌汤.png", "清酒.png", "饭碗.png"],
    "西餐": ["牛排.png", "披萨.png", "餐刀.png", "红酒杯.png", "红酒杯_2.png", "蔬菜沙拉.png", "意面.png"],
    "牛排": ["牛排.png", "餐刀.png", "红酒杯.png", "蔬菜沙拉.png", "餐叉.png"],
    "披萨": ["披萨.png", "可乐.png", "炸鸡.png", "番茄酱.png"],
    "咖啡": ["咖啡.png", "马克杯.png", "高脚杯.png", "纸杯蛋糕.png", "蛋糕卷.png"],
    "奶茶": ["咖啡.png", "马克杯.png", "冰淇淋.png", "果汁.png", "纸杯蛋糕.png"],
    "甜品": ["蛋糕卷.png", "蛋挞.png", "纸杯蛋糕.png", "糯米糍.png", "草莓.png", "苹果.png", "布丁.png"],
    "面包": ["长面包.png", "蛋挞.png", "蛋糕卷.png", "纸袋.png"],
    "面馆": ["拉面.png", "饭碗.png", "荷包蛋.png", "辣椒.png", "青菜.png"],
    "中餐": ["饭碗.png", "餐盘.png", "蒸笼.png", "蒸包.png", "蛋炒饭.png", "蒸饺.png", "茶壶.png", "青菜.png"],
    "海鲜": ["鱼.png", "铁板鱿鱼.png", "柠檬.png", "餐盘.png", "啤酒.png"],
    "快餐": ["汉堡.png", "鸡蛋汉堡.png", "鸡肉卷.png", "鸡腿.png", "脆皮烤肠.png", "可乐.png"]
}

# 通用餐饮兜底 Icon 池
FALLBACK_ICONS = ["餐盘.png", "饭碗.png", "餐刀.png", "茶壶.png", "苹果.png", "荷包蛋.png"]


def get_store_device_profile(store_identifier: str) -> Dict[str, str]:
    """
    根据商铺唯一标识（商铺名或文件夹路径）固定哈希选择一个设备 Profile，
    确保同一家商铺的所有相片严格使用完全同一款机型拍摄。
    """
    hash_int = int(hashlib.md5(store_identifier.encode('utf-8')).hexdigest(), 16)
    idx = hash_int % len(DEVICE_PROFILES)
    return DEVICE_PROFILES[idx]


def resolve_device_profile(specified_device: Optional[str], store_identifier: str) -> Tuple[Dict[str, str], bool]:
    """
    解析设备配置：
    - 若用户指定了手机型号（如 --device "iPhone 15 Pro" 或 "小米14"），进行模糊/别名匹配。
    - 若匹配成功，返回 (该设备Profile, True)
    - 若指定了但未匹配到，输出提示警告并自动回退到商铺哈希绑定设备，返回 (设备Profile, False)
    - 若未指定（None 或空字符串），直接根据商铺哈希绑定设备，返回 (设备Profile, False)
    """
    if specified_device and specified_device.strip():
        norm_query = re.sub(r"[\s\-_]+", "", specified_device.strip().lower())
        
        # 1. 精确/别名全等匹配
        for profile in DEVICE_PROFILES:
            for alias in profile.get("aliases", []):
                norm_alias = re.sub(r"[\s\-_]+", "", alias.lower())
                if norm_query == norm_alias:
                    return profile, True
            
            norm_model = re.sub(r"[\s\-_]+", "", profile["model"].lower())
            norm_name = re.sub(r"[\s\-_]+", "", profile.get("name", "").lower())
            if norm_query == norm_model or norm_query == norm_name:
                return profile, True

        # 2. 包含匹配 (优先从长到短)
        matched_profiles = []
        for profile in DEVICE_PROFILES:
            norm_model = re.sub(r"[\s\-_]+", "", profile["model"].lower())
            norm_name = re.sub(r"[\s\-_]+", "", profile.get("name", "").lower())
            if norm_query in norm_model or norm_query in norm_name:
                matched_profiles.append(profile)
                continue
            for alias in profile.get("aliases", []):
                norm_alias = re.sub(r"[\s\-_]+", "", alias.lower())
                if norm_query in norm_alias or norm_alias in norm_query:
                    matched_profiles.append(profile)
                    break
        
        if matched_profiles:
            return matched_profiles[0], True
        
        print(f"⚠️ [提示] 未能识别指定的手机型号: '{specified_device}'，可查看《支持手机列表.txt》。")
        print(f"   已自动为您回退为商铺哈希锁定机型。")

    fallback = get_store_device_profile(store_identifier)
    return fallback, False


def get_max_inner_rect(W: int, H: int, angle_deg: float) -> Tuple[int, int]:
    """计算旋转后保持原宽高比的最大无黑边内接矩形尺寸"""
    rad = math.radians(abs(angle_deg))
    sin_a = math.sin(rad)
    cos_a = math.cos(rad)
    aspect_max = max(H / W, W / H)
    w = W / (cos_a + aspect_max * sin_a)
    h = w * (H / W)
    return int(w), int(h)


def match_icons_for_store(store_name: str, available_icons: List[str]) -> List[str]:
    """根据商铺名称与品类智能路由选择 1~2 个匹配的图标名称"""
    candidates = []
    for cat_keyword, icons in CATEGORY_ICON_MAP.items():
        if cat_keyword in store_name:
            candidates.extend(icons)

    # 过滤出目录中真实存在的 icon
    valid_candidates = [ico for ico in candidates if ico in available_icons]
    if not valid_candidates:
        valid_candidates = [ico for ico in FALLBACK_ICONS if ico in available_icons]

    if not valid_candidates:
        valid_candidates = available_icons

    if not valid_candidates:
        return []

    count = random.choice([1, 2])
    selected = random.sample(valid_candidates, min(count, len(valid_candidates)))
    return selected


def apply_geometric_rotate(im: Image.Image) -> Tuple[Image.Image, float]:
    """步骤 1：几何随机微倾斜 2°~12° 并内切裁剪消除黑边"""
    orig_w, orig_h = im.size
    direction = random.choice([-1, 1])
    angle = round(random.uniform(2.0, 12.0), 1) * direction

    rotated = im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    crop_w, crop_h = get_max_inner_rect(orig_w, orig_h, angle)
    cx, cy = rotated.width // 2, rotated.height // 2

    crop_box = (
        cx - crop_w // 2,
        cy - crop_h // 2,
        cx + crop_w // 2,
        cy + crop_h // 2
    )
    cropped = rotated.crop(crop_box)
    final_img = cropped.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
    return final_img, angle


def apply_micro_color_jitter(im: Image.Image) -> Image.Image:
    """步骤 2：微观色彩空间微调 (亮度/对比度/饱和度 ±1%~2% 微抖动)"""
    # 亮度微扰
    bright_factor = random.uniform(0.985, 1.015)
    im = ImageEnhance.Brightness(im).enhance(bright_factor)
    # 对比度微扰
    contrast_factor = random.uniform(0.98, 1.02)
    im = ImageEnhance.Contrast(im).enhance(contrast_factor)
    # 饱和度微扰 (略倾向提高一点点食欲鲜艳感)
    color_factor = random.uniform(0.99, 1.03)
    im = ImageEnhance.Color(im).enhance(color_factor)
    return im


def apply_dynamic_lines_mask(im: Image.Image, lines_path: str, opacity: float = 0.02) -> Image.Image:
    """步骤 3：动态微缩放与微位移网格遮罩 (默认 2% 极低透明度融合)"""
    if not os.path.exists(lines_path):
        return im

    try:
        w, h = im.size
        with Image.open(lines_path) as lines_im:
            lines_im = lines_im.convert("RGBA")
            # 随机做 102%~106% 的轻微尺寸缩放，避免所有图片的网格完全死板雷同
            scale_factor = random.uniform(1.02, 1.06)
            scaled_w = int(w * scale_factor)
            scaled_h = int(h * scale_factor)
            scaled_lines = lines_im.resize((scaled_w, scaled_h), Image.Resampling.BICUBIC)

            # 随机裁剪回 w, h 尺寸 (产生随机 offset 位移)
            offset_x = random.randint(0, scaled_w - w)
            offset_y = random.randint(0, scaled_h - h)
            cropped_lines = scaled_lines.crop((offset_x, offset_y, offset_x + w, offset_y + h))

            # 调整 Alpha 通道透明度为 2% (255 * 0.02 ≈ 5)
            r, g, b, a = cropped_lines.split()
            target_alpha = max(1, int(255 * opacity))
            a = a.point(lambda p: int(p * (target_alpha / 255.0)))
            adjusted_lines = Image.merge("RGBA", (r, g, b, a))

            # 与原图 Alpha 混合
            base_rgba = im.convert("RGBA")
            blended = Image.alpha_composite(base_rgba, adjusted_lines)
            return blended.convert("RGB")
    except Exception as e:
        print(f"  [警告] 网格遮罩处理异常，保留原图: {e}")
        return im


def apply_corner_micro_icons(
    im: Image.Image,
    store_name: str,
    ico_dir: str,
    min_size: int = 12,
    max_size: int = 24,
    min_opacity: float = 0.015,
    max_opacity: float = 0.03
) -> Tuple[Image.Image, List[str]]:
    """步骤 4：根据品类在角落注入 1~2 个 12~24px 极低透明度 (1.5%~3%) 隐形图标"""
    if not os.path.exists(ico_dir):
        return im, []

    available_icons = [f for f in os.listdir(ico_dir) if f.lower().endswith(".png")]
    if not available_icons:
        return im, []

    selected_icons = match_icons_for_store(store_name, available_icons)
    if not selected_icons:
        return im, []

    w, h = im.size
    base_rgba = im.convert("RGBA")

    # 4 个角落定义 (左上、右上、左下、右下)
    # 每个角保留 5%~12% 的内缩安全边距
    corners = ["top_left", "top_right", "bottom_left", "bottom_right"]
    random.shuffle(corners)

    applied_info = []

    for i, ico_name in enumerate(selected_icons):
        corner = corners[i % len(corners)]
        ico_path = os.path.join(ico_dir, ico_name)
        try:
            with Image.open(ico_path) as ico_im:
                ico_im = ico_im.convert("RGBA")

                # 随机生成微小尺寸 (12px ~ 24px)
                ico_size = random.randint(min_size, max_size)
                ico_resized = ico_im.resize((ico_size, ico_size), Image.Resampling.LANCZOS)

                # 随机生成极低透明度 (1.5% ~ 3.0%)
                opacity = random.uniform(min_opacity, max_opacity)
                target_alpha = max(1, int(255 * opacity))

                r, g, b, a = ico_resized.split()
                a = a.point(lambda p: int(p * (target_alpha / 255.0)))
                ico_adjusted = Image.merge("RGBA", (r, g, b, a))

                # 计算放置位置
                margin_x = random.randint(int(w * 0.05), int(w * 0.12))
                margin_y = random.randint(int(h * 0.05), int(h * 0.12))

                if corner == "top_left":
                    pos = (margin_x, margin_y)
                elif corner == "top_right":
                    pos = (w - margin_x - ico_size, margin_y)
                elif corner == "bottom_left":
                    pos = (margin_x, h - margin_y - ico_size)
                else:  # bottom_right
                    pos = (w - margin_x - ico_size, h - margin_y - ico_size)

                # 创建透明层贴合
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                overlay.paste(ico_adjusted, pos, ico_adjusted)
                base_rgba = Image.alpha_composite(base_rgba, overlay)
                applied_info.append(f"{ico_name.replace('.png','')}({ico_size}px, {opacity*100:.1f}%)")
        except Exception as e:
            continue

    return base_rgba.convert("RGB"), applied_info


def inject_store_exif(im: Image.Image, device_profile: Dict[str, str], photo_index: int = 1) -> Image.Exif:
    """
    步骤 5：注入商铺级统一的手机原相机实拍 EXIF 属性
    - 统一机型 (Make, Model, Software, Lens)
    - 连贯真实拍摄时间戳 (当前日期，每张间隔 25~60 秒)
    """
    exif = im.getexif()

    # 标准 TIFF 标签
    exif[0x010F] = device_profile["make"]      # Make
    exif[0x0110] = device_profile["model"]     # Model
    exif[0x0131] = device_profile["software"]  # Software
    exif[0x0112] = 1                           # Orientation (Normal)

    # 模拟连贯用餐实拍时间戳 (今天或近两天的午/晚餐时段，随序号递增)
    now = datetime.datetime.now()
    base_time = now - datetime.timedelta(hours=random.choice([2, 5, 24]))
    photo_time = base_time + datetime.timedelta(seconds=photo_index * random.randint(25, 60))
    time_str = photo_time.strftime("%Y:%m:%d %H:%M:%S")

    exif[0x0132] = time_str  # DateTime
    exif[0x9003] = time_str  # DateTimeOriginal
    exif[0x9004] = time_str  # DateTimeDigitized

    return exif


def process_dedup_single_image(
    img_path: str,
    output_path: str,
    store_name: str,
    device_profile: Dict[str, str],
    photo_index: int = 1,
    lines_path: str = DEFAULT_LINES_PATH,
    ico_dir: str = DEFAULT_ICO_DIR
) -> Tuple[bool, str]:
    """对单张图片执行完整的 V4 级高阶去重流水线"""
    try:
        with Image.open(img_path) as im:
            if im.mode != "RGB":
                im = im.convert("RGB")

            # 1. 几何微形变
            im_rot, angle = apply_geometric_rotate(im)

            # 2. 微观色彩空间微调
            im_color = apply_micro_color_jitter(im_rot)

            # 3. 动态网格遮罩 (2% 透明度)
            im_masked = apply_dynamic_lines_mask(im_color, lines_path=lines_path, opacity=0.02)

            # 4. 角落品类线条 Icon 注入
            im_final, icons_info = apply_corner_micro_icons(
                im_masked,
                store_name=store_name,
                ico_dir=ico_dir,
                min_size=12,
                max_size=24,
                min_opacity=0.015,
                max_opacity=0.03
            )

            # 5. 注入商铺统一手机原相机 EXIF
            exif_data = inject_store_exif(im_final, device_profile, photo_index=photo_index)

            # 保存为 JPEG 95 高品质
            im_final.save(output_path, format="JPEG", quality=95, exif=exif_data)

            dir_str = "向右" if angle > 0 else "向左"
            icon_str = "+".join(icons_info) if icons_info else "通用去重"
            detail = f"{dir_str}微倾{abs(angle)}° | 2%网格遮罩 | 角落注入[{icon_str}] | 设备[{device_profile['model']}]"
            return True, detail
    except Exception as e:
        return False, str(e)


def is_candidate_for_dedup(filename: str) -> bool:
    """筛选允许去重的原始实拍素材，支持爆款参考封面原图，排除已微调图与各类合成封面拼接图"""
    f_lower = filename.lower()
    if not f_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return False
    if filename.startswith("P_") or filename.startswith("mix_") or filename.startswith("mix9_"):
        return False
    # 优先放行大众点评爆款参考封面原图进入防查重流水线
    if "爆款参考封面原图" in filename:
        return True
    if "封面" in filename or "cover" in f_lower:
        return False
    return True


def batch_dedup_directory(
    target_dir: str,
    store_name: Optional[str] = None,
    lines_path: str = DEFAULT_LINES_PATH,
    ico_dir: str = DEFAULT_ICO_DIR,
    device: Optional[str] = None
) -> int:
    """
    批量对商铺目录下的所有原始实拍图执行 V4 高阶去重
    严格保障：商铺全量相片统一绑定同一台手机设备 Profile 与时间流。
    """
    if not os.path.exists(target_dir):
        print(f"[错误] 目录不存在: {target_dir}")
        return 0

    if not store_name:
        store_name = os.path.basename(os.path.normpath(target_dir))

    # 商铺级设备绑定锁（支持用户指定机型，未指定或未匹配则按商铺哈希锁定）
    device_profile, is_custom = resolve_device_profile(device, store_name)
    mode_desc = "用户指定机型" if is_custom else "商铺哈希锁定"

    files = sorted(os.listdir(target_dir))
    candidate_files = [f for f in files if is_candidate_for_dedup(f)]

    print(f"\n==================================================")
    print(f"🚀 启动 V4 级高阶图像全自动去重引擎")
    print(f"商铺名称: {store_name}")
    print(f"绑定相机设备: [{mode_desc}] {device_profile['make']} {device_profile['model']} ({device_profile['software']})")
    print(f"目标目录: {target_dir}")
    print(f"待处理素材数: {len(candidate_files)} 张")
    print(f"去重技术矩阵: 随机微倾斜 + 2%动态网格 + 隐形品类Icon + 原机EXIF注入")
    print(f"==================================================")

    success_count = 0
    for idx, fname in enumerate(candidate_files, start=1):
        in_path = os.path.join(target_dir, fname)
        out_name = f"P_{fname}"
        out_path = os.path.join(target_dir, out_name)

        ok, msg = process_dedup_single_image(
            img_path=in_path,
            output_path=out_path,
            store_name=store_name,
            device_profile=device_profile,
            photo_index=idx,
            lines_path=lines_path,
            ico_dir=ico_dir
        )
        if ok:
            success_count += 1
            print(f"  [{success_count}/{len(candidate_files)}] ✅ {out_name} -> {msg}")
        else:
            print(f"  [失败] ❌ {fname}: {msg}")

    print(f"--------------------------------------------------")
    print(f"V4 去重处理完毕！成功生成 {success_count} 张 P_ 深度去重图！\n")
    return success_count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="探店笔记 V4 级高阶图像全自动去重处理器")
    parser.add_argument("--folder", "-f", type=str, default=None, help="目标商铺图片目录绝对路径")
    parser.add_argument("--store", "-s", type=str, default=None, help="商铺名称（用于品类识别与设备绑定）")
    parser.add_argument("--device", "-dev", type=str, default=None, help="指定拍摄手机型号（支持模糊匹配，如 iPhone 15 Pro、小米14 等；若不指定则按商铺哈希自动锁定）")
    parser.add_argument("--image", "-i", type=str, default=None, help="单张图片路径")
    parser.add_argument("--output", "-o", type=str, default=None, help="单张输出路径")

    args = parser.parse_args()

    if args.folder:
        batch_dedup_directory(args.folder, store_name=args.store, device=args.device)
    elif args.image and args.output:
        st_name = args.store or "未知商铺"
        dev, _ = resolve_device_profile(args.device, st_name)
        ok, msg = process_dedup_single_image(args.image, args.output, st_name, dev)
        print(f"结果: {ok}, {msg}")
    else:
        parser.print_help()
