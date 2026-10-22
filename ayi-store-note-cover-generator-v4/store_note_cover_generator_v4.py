# -*- coding: utf-8 -*-
"""
阿一商铺笔记封面生成器 V4 (Store Note Cover Generator V4 - 年轻白领松弛网感版)
核心特性：
1. 免费可商用年轻网感字体库自动混搭：
    内置站酷庆科黄油体 (圆润Q弹)、站酷快乐体 (俏皮涂鸦)、站酷小薇体 (文艺杂志)、马善政楷书/龙藏体 (国潮手写)，
    直接从本脚本同级目录 (即本 Skill 目录) 加载，彻底告别刻板的微软雅黑；
2. 年轻白领休闲口语化文案池 + 精准细分菜系识别：
    消灭笼统的“特色美食/品质火锅”，智能识别绍兴菜、湖南菜、潮汕菜、摩登日料、泰北船面、小龙虾、炭烤自助、铁锅炖等，
    搭配“这一口鲜掉眉毛”、“巨下饭！连炫两碗”、“现炒浇头香迷糊了”、“周末约饭漂亮饭”、“按完直接满血复活”等年轻白领口吻；
3. 主次字号错落层次排版 + 多巴胺/奶油系年轻配色：
    地标轻标签秀气精致、核心情绪词放大突出，配合柔和炭黑描边，画面轻松时尚、点击欲拉满；
4. 全局零违禁词 + 商铺哈希与笔记序号双重散列轮换。

【本文件为随 V4 统一技能包分发的自包含版本】
随 Skill 目录自带 4 款开源免费商用中文字体，朋友复制该目录后直接可用。
"""

import os
import sys
import re
import argparse
import subprocess
from typing import Optional, Dict, Any, List, Tuple

# 自动自愈环境依赖：若未安装 Pillow 则自动无感安装
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("⚡ 检测到当前 Python 环境尚未安装 Pillow 图像处理库，正在为您自动无感安装...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        from PIL import Image, ImageDraw, ImageFont
        print("✅ Pillow 图像处理库自动安装成功，继续执行！")
    except Exception as _e:
        print(f"❌ 自动安装 Pillow 失败: {_e}")
        print("请手动在终端运行: pip install Pillow")
        sys.exit(1)

# 强制标准输出使用 UTF-8
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 字体与本脚本同目录（自包含分发：Skill 文件夹里自带 4 款 ttf 字体）
SKILL_V4_DIR = os.path.dirname(os.path.abspath(__file__))


def find_grid_cover_image(store_dir: str) -> Optional[str]:
    """寻找目录下的九宫格拼图底图 (优先 mix9_ 开头)"""
    if not os.path.exists(store_dir):
        return None

    files = sorted(os.listdir(store_dir))
    for f in files:
        if f.startswith("mix9_") and f.lower().endswith((".jpg", ".jpeg", ".png")):
            return os.path.join(store_dir, f)

    for f in files:
        fl = f.lower()
        if ("9格" in fl or "九宫格" in fl or "nine_grid" in fl) and fl.endswith((".jpg", ".jpeg", ".png")):
            return os.path.join(store_dir, f)

    for f in files:
        if f.startswith("mix_") and f.lower().endswith((".jpg", ".jpeg", ".png")):
            return os.path.join(store_dir, f)

    return None


def parse_store_keywords(txt_path: str) -> Dict[str, Any]:
    """解析商铺目录或其父级目录下的 '店铺关键词.txt'"""
    data = {
        "store_name": "",
        "store_address": "",
        "city": "上海",
        "district": "",
        "biz_area": "",
        "mall": "",
        "category": "",
        "raw_category": "",
        "honor": "",
        "rating": "",
        "popularity": "",
        "selling_points": []
    }

    found_file = None
    if os.path.isfile(txt_path) and os.path.exists(txt_path):
        found_file = txt_path
    else:
        search_dir = os.path.dirname(txt_path) if (os.path.isfile(txt_path) or txt_path.endswith(".txt")) else txt_path
        cur_dir = search_dir
        for _ in range(3):
            cand = os.path.join(cur_dir, "店铺关键词.txt")
            if os.path.exists(cand):
                found_file = cand
                break
            parent = os.path.dirname(cur_dir)
            if parent == cur_dir:
                break
            cur_dir = parent

    if not found_file or not os.path.exists(found_file):
        return data

    with open(found_file, "r", encoding="utf-8") as f:
        content = f.read()

    m_name = re.search(r"店铺名称[：:]\s*([^\n\r]+)", content)
    if m_name:
        data["store_name"] = m_name.group(1).strip()

    m_addr = re.search(r"(?:店铺位置|详细地址)[：:]\s*([^\n\r]+)", content)
    if m_addr:
        data["store_address"] = m_addr.group(1).strip()

    m_area = re.search(r"(?:所属商圈|商圈归属)[：:]\s*([^\n\r]+)", content)
    if m_area:
        raw_area = m_area.group(1).strip()
        parts = [p.strip() for p in raw_area.split("/") if p.strip()]
        biz = parts[-1] if parts else raw_area
        biz = re.sub(r"^(?:[^·/]+·)", "", biz).replace("商圈", "").strip()
        data["biz_area"] = biz

    m_mall = re.search(r"(?:所属商场|所在商场)[：:]\s*([^\n\r]+)", content)
    if m_mall:
        mall_val = m_mall.group(1).strip()
        if mall_val not in ["无", "暂无", "-", "None"]:
            data["mall"] = re.sub(r"^上海", "", mall_val).strip()

    m_cat = re.search(r"(?:品类归属|菜系分类|菜系品类)[：:]\s*([^\n\r]+)", content)
    if m_cat:
        raw_cat = m_cat.group(1).strip()
        data["raw_category"] = raw_cat
        cat_parts = [p.strip() for p in raw_cat.split("/") if p.strip()]
        # 优先取斜杠后面的具体细分品类（如 "餐饮美食 / 浙菜" -> "浙菜"）
        if len(cat_parts) >= 2 and cat_parts[0] in ["餐饮美食", "美食", "休闲娱乐", "丽人", "运动健身", "生活服务"]:
            data["category"] = cat_parts[-1]
        else:
            data["category"] = cat_parts[0] if cat_parts else raw_cat

    m_honor = re.search(r"(?:官方榜单|官方荣誉|官方榜单荣誉|榜单排名)[：:]\s*([^\n\r]+)", content)
    if m_honor:
        data["honor"] = m_honor.group(1).strip()

    m_score = re.search(r"综合评分[：:]\s*([^\n\r]+)", content)
    if m_score:
        data["rating"] = m_score.group(1).strip()

    m_pop = re.search(r"(?:人气热度|打卡热度|近期打卡|预订热度)[：:]\s*([^\n\r]+)", content)
    if m_pop:
        data["popularity"] = m_pop.group(1).strip()

    m_tags = re.search(r"(?:核心卖点标签|衍生创作关键词库)[：:]\s*([^\n\r]+)", content)
    if m_tags:
        data["selling_points"] = [t.strip() for t in re.split(r"[、，, ]+", m_tags.group(1)) if t.strip()]

    addr = (data["store_address"] or "") + " " + (data["store_name"] or "") + " " + (data["raw_category"] or "")
    shanghai_districts = ["浦东新区", "闵行区", "徐汇区", "黄浦区", "静安区", "长宁区", "普陀区", "虹口区", "杨浦区", "宝山区", "嘉定区", "青浦区", "松江区"]
    if any(d in addr for d in shanghai_districts) or "上海" in addr:
        data["city"] = "上海"
        for d in ["浦东", "黄浦", "徐汇", "静安", "长宁", "普陀", "虹口", "杨浦", "闵行", "宝山", "嘉定", "青浦", "松江"]:
            if d in addr:
                data["district"] = d
                break
    else:
        for c in ["北京", "广州", "深圳", "杭州", "南京", "成都", "武汉", "苏州", "重庆"]:
            if c in addr:
                data["city"] = c
                break

    return data


def compute_store_hash(store_name: str) -> int:
    """计算稳定的商铺名称确定性哈希值"""
    if not store_name:
        return 0
    return sum(ord(ch) * (idx + 1) for idx, ch in enumerate(store_name))


def resolve_fine_category(store_name: str, cat: str, combo_text: str) -> Tuple[str, str]:
    """
    智能解析具体的细分菜系名称 (sub_cat) 与宏观大类 (macro_type)，
    彻底告别千篇一律的“特色美食”和“品质火锅”。
    """
    # 1. 非餐饮业态优先判定
    if any(k in combo_text for k in ["spa", "养生", "采耳", "足道", "足浴", "推拿", "按摩", "头疗", "艾灸"]):
        if "推拿" in store_name or "艾灸" in store_name:
            return "推拿艾灸", "spa"
        if "足道" in store_name or "足浴" in store_name:
            return "解压足道", "spa"
        if "采耳" in store_name:
            return "采耳SPA", "spa"
        return "养生SPA", "spa"

    if any(k in combo_text for k in ["茶室", "茶馆", "茶空间", "品茗"]):
        return "静谧茶室", "tea"

    if any(k in combo_text for k in ["搏击", "健身", "拳击", "普拉提", "瑜伽", "运动馆"]):
        return "燃脂健身", "gym"

    if any(k in combo_text for k in ["酒店", "客栈", "民宿", "商旅", "宾馆", "全季", "汉庭", "亚朵", "和颐", "青旅", "度假村"]):
        return "宝藏酒店", "hotel"

    if any(k in combo_text for k in ["全屋定制", "室内设计", "家装"]):
        return "美学定制", "custom"

    if any(k in combo_text for k in ["美发", "理发", "造型", "美甲", "美睫", "美容"]):
        return "质感沙龙", "beauty"

    if any(k in combo_text for k in ["ktv", "密室", "剧本杀", "桌游", "轰趴"]):
        return "周末潮玩", "recreation"

    # 2. 餐饮细分品类精准识别（优先从店名和细分品类中提取最具食欲的词）
    if "脆鲩鱼" in store_name or "鱼火锅" in store_name or "鱼捞" in store_name:
        return "鲜鱼火锅", "hotpot"
    if "野生菌" in store_name or "菌火锅" in store_name or "腊排骨" in store_name:
        return "野生菌锅", "hotpot"
    if "豆米火锅" in store_name or "贵州" in store_name:
        return "贵州火锅", "hotpot"
    if "铜锅" in store_name or "涮肉" in store_name:
        return "铜锅涮肉", "hotpot"
    if "打边炉" in store_name or "牛腩煲" in store_name:
        return "港式打边炉", "hotpot"
    if "牛肉火锅" in store_name or "鲜活牛肉" in store_name or "潮汕牛肉" in combo_text:
        return "鲜牛肉锅", "hotpot"
    if any(k in combo_text for k in ["火锅", "涮锅", "羊蝎子"]):
        return "人气火锅", "hotpot"

    if "自助" in store_name and ("烤" in store_name or "料理" in store_name):
        return "烤肉自助", "bbq"
    if "鳗" in store_name and "烤肉" in store_name:
        return "鲜鳗烤肉", "bbq"
    if "烧烤" in store_name or "串" in store_name:
        return "炭火烧烤", "bbq"
    if "烤肉" in combo_text:
        return "人气烤肉", "bbq"

    if "小龙虾" in store_name:
        return "招牌小龙虾", "seafood"
    if "醉鸡煲" in store_name or "小海鲜" in store_name or "大排档" in store_name:
        return "海鲜大排档", "seafood"
    if any(k in combo_text for k in ["海鲜", "江鲜", "鱼头"]):
        return "鲜活海鲜", "seafood"

    if "拌川" in store_name:
        return "杭州拌川", "noodle"
    if "浇头面" in store_name or "面王" in store_name or "面馆" in store_name or "本帮面" in combo_text:
        return "现炒浇头面", "noodle"
    if "船面" in store_name or "泰" in store_name or "泰" in cat:
        return "泰国料理", "exotic"
    if "日料" in store_name or "日料" in cat or "居酒屋" in combo_text:
        return "摩登日料", "exotic"
    if "耶里夏丽" in store_name or "新疆" in combo_text:
        return "新疆美食", "regional"
    if "铁锅" in store_name or "铁锅炖" in combo_text:
        return "东北铁锅炖", "regional"
    if "绍兴" in store_name or "越稽" in store_name:
        return "地道绍兴菜", "regional"
    if "湖南菜" in store_name or "湘菜" in combo_text:
        return "山野湖南菜", "regional"
    if "潮" in store_name or "潮汕" in combo_text:
        return "精致潮汕菜", "regional"
    if "台州" in store_name or "江浙" in store_name or "本帮" in combo_text or "浙菜" in cat:
        return "本帮江浙菜", "regional"
    if any(k in combo_text for k in ["西餐", "牛排", "bistro", "简餐", "麦科淇", "guui"]):
        return "约会漂亮饭", "exotic"
    if any(k in combo_text for k in ["甜品", "酸奶", "咖啡", "烘焙", "下午茶"]):
        return "宝藏下午茶", "dessert"

    # 兜底清理
    cleaned = re.sub(r"(餐饮美食|餐饮|菜系|分类)", "", cat).strip()
    if cleaned and len(cleaned) <= 5:
        return cleaned, "regional"
    return "宝藏美食", "regional"


def build_cover_title_and_decorations(data: Dict[str, Any], note_idx: int = 1) -> Dict[str, Any]:
    """
    生成年轻白领休闲网感风封面文案、配色与字体方案：
    - 零违禁词
    - 商铺哈希 + note_idx 自动错开文案、配色与字体组合
    """
    city = data.get("city", "上海")
    district = data.get("district", "")
    cat = data.get("category", "")
    mall = data.get("mall", "")
    biz_area = data.get("biz_area", "")
    honor = data.get("honor", "")
    store_name = data.get("store_name", "")
    sp_text = " ".join(data.get("selling_points", []))
    combo_text = f"{store_name} {cat} {data.get('raw_category', '')} {sp_text} {honor}".lower()

    # 提取精炼地标词
    sub_loc = None
    branch_match = re.search(r"[(（]([^)）]+)[)）]", store_name)
    if branch_match:
        b_name = branch_match.group(1).replace("店", "").strip()
        b_name = re.sub(r"^(上海|浦东)", "", b_name).strip()
        if b_name not in ["首", "上海首", "旗舰", "总"] and len(b_name) >= 2:
            sub_loc = b_name

    if sub_loc:
        loc_tag = sub_loc
    elif mall:
        loc_tag = mall
    elif biz_area:
        loc_tag = biz_area
    elif district:
        loc_tag = district
    else:
        loc_tag = city

    loc_tag = re.sub(r"[旁附近]+$", "", loc_tag).strip()
    if not loc_tag:
        loc_tag = city

    sub_cat, macro_type = resolve_fine_category(store_name, cat, combo_text)

    store_hash = compute_store_hash(store_name)
    pick_seed = store_hash + max(0, note_idx - 1) * 3

    # 按品类定制年轻白领松弛感短句池 (上行：地标与品类/场景；下行：真香情绪钩子)
    if macro_type == "hotpot":
        emojis = ("🍲", "🔥", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "这一口鲜掉眉毛"),
            (f"{loc_tag}{sub_cat}", "和饭搭子炫三盘"),
            (f"{loc_tag}暖胃热锅", "好吃到想N刷"),
            (f"{loc_tag}{sub_cat}", "滚烫治愈太香了"),
            (f"{loc_tag}{sub_cat}", "盲点完全不踩雷"),
            (f"{loc_tag}宝藏火锅", "吃完还想再来"),
            (f"{loc_tag}{sub_cat}", "下班聚餐心头好"),
            (f"{loc_tag}{sub_cat}", "肉食脑袋狂喜"),
        ]
    elif macro_type == "bbq":
        emojis = ("🥩", "🔥", "🍻")
        pool = [
            (f"{loc_tag}{sub_cat}", "滋滋冒油太香了"),
            (f"{loc_tag}{sub_cat}", "下班微醺好去处"),
            (f"{loc_tag}{sub_cat}", "被我挖到宝了"),
            (f"{loc_tag}{sub_cat}", "和朋友炫到扶墙"),
            (f"{loc_tag}{sub_cat}", "好吃到想N刷"),
            (f"{loc_tag}夜宵快乐屋", "一口肉香超治愈"),
        ]
    elif macro_type == "seafood":
        emojis = ("🦞", "🍲", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "个大饱满超入味"),
            (f"{loc_tag}{sub_cat}", "夜宵聚餐好去处"),
            (f"{loc_tag}{sub_cat}", "鲜到连吮手指头"),
            (f"{loc_tag}{sub_cat}", "被我挖到宝了"),
            (f"{loc_tag}{sub_cat}", "和闺蜜连炫两锅"),
            (f"{loc_tag}{sub_cat}", "好吃到想N刷"),
        ]
    elif macro_type == "noodle":
        emojis = ("🍜", "🥢", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "现炒浇头香迷糊"),
            (f"{loc_tag}碳水快乐屋", "打工人午餐私藏"),
            (f"{loc_tag}{sub_cat}", "我愿意反复吃"),
            (f"{loc_tag}{sub_cat}", "锅气十足太香了"),
            (f"{loc_tag}宝藏面馆", "连汤都喝光光"),
            (f"{loc_tag}{sub_cat}", "好吃到想N刷"),
        ]
    elif macro_type == "exotic":
        emojis = ("🍱", "🥂", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "周末约会漂亮饭"),
            (f"{loc_tag}{sub_cat}", "好吃又好拍"),
            (f"{loc_tag}{sub_cat}", "被我挖到宝了"),
            (f"{loc_tag}{sub_cat}", "一口沦陷太正了"),
            (f"{loc_tag}{sub_cat}", "盲点完全不踩雷"),
            (f"{loc_tag}{sub_cat}", "和闺蜜二刷好店"),
        ]
    elif macro_type == "spa":
        emojis = ("💆‍♀️", "🍃", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "按完满血复活"),
            (f"{loc_tag}打工人回血", "全身通体舒畅"),
            (f"{loc_tag}{sub_cat}", "周末放空好去处"),
            (f"{loc_tag}{sub_cat}", "手法专业超解乏"),
        ]
    elif macro_type == "hotel":
        emojis = ("🛏️", "🌙", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "双层隔音太安心了"),
            (f"{loc_tag}{sub_cat}", "一觉睡到大天亮"),
            (f"{loc_tag}{sub_cat}", "卫生挑不出毛病"),
            (f"{loc_tag}{sub_cat}", "洁癖星人完全治愈"),
            (f"{loc_tag}{sub_cat}", "连住3晚不想退房"),
            (f"{loc_tag}差旅优选", "出差反复来住这家"),
            (f"{loc_tag}{sub_cat}", "关上门整个世界静音"),
            (f"{loc_tag}{sub_cat}", "质感完全超出预期"),
        ]
    elif macro_type in ["tea", "custom", "beauty", "recreation"]:
        emojis = ("✨", "🌿", "💫")
        pool = [
            (f"{loc_tag}{sub_cat}", "周末放松好去处"),
            (f"{loc_tag}{sub_cat}", "被我挖到宝了"),
            (f"{loc_tag}{sub_cat}", "体验感真的能打"),
            (f"{loc_tag}{sub_cat}", "私藏宝藏好店"),
        ]
    else:
        # 地方菜/江浙菜/湘菜/潮汕菜/铁锅炖/新疆菜等
        emojis = ("🥘", "🍚", "✨")
        pool = [
            (f"{loc_tag}{sub_cat}", "巨下饭！炫两碗"),
            (f"{loc_tag}{sub_cat}", "被我挖到宝了"),
            (f"{loc_tag}{sub_cat}", "好吃到想N刷"),
            (f"{loc_tag}{sub_cat}", "锅气十足太香了"),
            (f"{loc_tag}{sub_cat}", "饭搭子直呼会选"),
            (f"{loc_tag}{sub_cat}", "盲点完全不踩雷"),
            (f"{loc_tag}{sub_cat}", "我愿意反复吃"),
            (f"{loc_tag}{sub_cat}", "周末聚餐好去处"),
        ]

    line1_raw, line2_raw = pool[pick_seed % len(pool)]

    # 年轻白领网感多巴胺/奶油系配色池 (6 套高颜值柔和吸睛配色)
    palettes = [
        {
            "name": "奶油亮黄配纯白",
            "colors_2": [(255, 253, 245, 255), (255, 226, 74, 255)],
            "colors_3": [(255, 248, 225, 255), (255, 255, 255, 255), (255, 226, 74, 255)]
        },
        {
            "name": "蜜桃甜橙配柔白",
            "colors_2": [(255, 255, 255, 255), (255, 154, 92, 255)],
            "colors_3": [(255, 236, 179, 255), (255, 255, 255, 255), (255, 154, 92, 255)]
        },
        {
            "name": "多巴胺暖金配奶白",
            "colors_2": [(255, 228, 88, 255), (255, 255, 255, 255)],
            "colors_3": [(255, 228, 88, 255), (255, 255, 255, 255), (255, 171, 115, 255)]
        },
        {
            "name": "薄荷森系配奶油白",
            "colors_2": [(255, 255, 255, 255), (138, 240, 185, 255)],
            "colors_3": [(232, 245, 233, 255), (255, 255, 255, 255), (138, 240, 185, 255)]
        },
        {
            "name": "落日珊瑚配浅杏",
            "colors_2": [(255, 249, 238, 255), (255, 126, 103, 255)],
            "colors_3": [(255, 224, 130, 255), (255, 255, 255, 255), (255, 126, 103, 255)]
        },
        {
            "name": "香槟浅金配珍珠白",
            "colors_2": [(255, 255, 255, 255), (255, 213, 107, 255)],
            "colors_3": [(255, 213, 107, 255), (255, 255, 255, 255), (255, 238, 173, 255)]
        },
    ]

    if macro_type in ["spa", "tea", "hotel"]:
        pal = palettes[3] if (pick_seed % 2 == 0) else palettes[5]
    else:
        pal = palettes[(store_hash + note_idx) % len(palettes)]

    # 智能分行与主次字号比例分配 (role: "tag" 轻标签较小, "sub" 品类中等, "hero" 核心情绪词最大)
    if len(line1_raw) >= 8:
        lines = [loc_tag, sub_cat, line2_raw]
        line_roles = ["tag", "sub", "hero"]
        line_colors = pal["colors_3"]
    else:
        lines = [line1_raw, line2_raw]
        line_roles = ["sub", "hero"]
        line_colors = pal["colors_2"]

    # 免费可商用字体轮换与混搭方案
    font_combos = [
        # 方案 0: 站酷庆科黄油体 (圆润Q弹) + 站酷快乐体 (俏皮灵动)
        ("ZCOOLQingKeHuangYou-Regular.ttf", "ZCOOLKuaiLe-Regular.ttf", "圆润黄油+俏皮快乐混搭"),
        # 方案 1: 全图站酷快乐体 (轻松网感涂鸦风)
        ("ZCOOLKuaiLe-Regular.ttf", "ZCOOLKuaiLe-Regular.ttf", "站酷快乐涂鸦风"),
        # 方案 2: 全图站酷庆科黄油体 (小红书圆角爆款风)
        ("ZCOOLQingKeHuangYou-Regular.ttf", "ZCOOLQingKeHuangYou-Regular.ttf", "庆科黄油圆体风"),
        # 方案 3: 站酷小薇体 (文艺精致) + 站酷庆科黄油体
        ("ZCOOLXiaoWei-Regular.ttf", "ZCOOLQingKeHuangYou-Regular.ttf", "小薇文艺+黄油圆体混搭"),
        # 方案 4: 站酷庆科黄油体 + 龙藏随性手写体 (烟火气手写混搭)
        ("ZCOOLQingKeHuangYou-Regular.ttf", "LongCang-Regular.ttf", "黄油圆体+龙藏手写混搭"),
    ]

    if macro_type in ["spa", "tea", "exotic", "hotel"]:
        combo_idx = [3, 0, 2][(store_hash + note_idx) % 3]
    elif macro_type in ["hotpot", "bbq", "noodle"]:
        combo_idx = [0, 1, 2, 4][(store_hash + note_idx) % 4]
    else:
        combo_idx = (store_hash + note_idx) % len(font_combos)

    tag_font_file, hero_font_file, font_style_name = font_combos[combo_idx]

    return {
        "lines": lines,
        "line_roles": line_roles,
        "line_colors": line_colors,
        "color_scheme": {"name": pal["name"]},
        "font_style_name": font_style_name,
        "tag_font_file": tag_font_file,
        "hero_font_file": hero_font_file,
        "emojis": emojis
    }


def resolve_font_path(font_filename: str) -> str:
    """从 V4 Skill 目录或公共资源自适应加载免费可商用字体，带多级稳健兜底"""
    candidate_dirs = [
        SKILL_V4_DIR,
        os.path.join(SKILL_V4_DIR, "ayi-store-note-cover-generator-v4"),
        os.path.join(SKILL_V4_DIR, "..", "ayi-store-note-cover-generator-v4"),
        os.path.join(SKILL_V4_DIR, "fonts"),
        os.path.join(SKILL_V4_DIR, "..", "assets", "fonts"),
        os.path.join(SKILL_V4_DIR, "assets", "fonts"),
    ]
    for d in candidate_dirs:
        cand = os.path.join(d, font_filename)
        if os.path.exists(cand):
            return cand
    for d in candidate_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.lower().endswith(".ttf"):
                    return os.path.join(d, f)
    return "C:/Windows/Fonts/msyhbd.ttc"


def draw_styled_cover(
    bg_image_path: str,
    title_data: Dict[str, Any],
    output_path: str,
    mask_opacity: float = 0.0
) -> str:
    """
    在九宫格高清原图上直接渲染封面（默认无遮罩，保留通透鲜艳质感与高光食欲），
    采用免费商用年轻网感字体 + 主次字号错落层次 + 柔和立体炭黑描边长投影渲染封面。
    """
    base_img = Image.open(bg_image_path).convert("RGBA")
    w, h = base_img.size

    # 去除黑色遮罩逻辑：默认 mask_opacity=0.0，直接使用原图呈现通透质感
    if mask_opacity > 0.0:
        alpha_val = int(255 * max(0.0, min(0.9, mask_opacity)))
        mask_layer = Image.new("RGBA", (w, h), (0, 0, 0, alpha_val))
        composed = Image.alpha_composite(base_img, mask_layer)
    else:
        composed = base_img

    lines = title_data.get("lines", [])
    line_roles = title_data.get("line_roles", ["sub", "hero"])
    line_colors = title_data.get("line_colors", [])
    emojis = title_data.get("emojis", ("✨", "🔥", "🥢"))
    tag_font_path = resolve_font_path(title_data.get("tag_font_file", "ZCOOLQingKeHuangYou-Regular.ttf"))
    hero_font_path = resolve_font_path(title_data.get("hero_font_file", "ZCOOLKuaiLe-Regular.ttf"))
    num_lines = len(lines)

    draw_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(draw_layer)

    max_allowed_w = int(w * 0.86)

    # 主次错落字号层次计算：tag(地标引子)较小秀气，sub(菜系)适中，hero(核心真香情绪词)最大醒目
    def get_role_font_size(text: str, role: str, is_three_lines: bool) -> int:
        n = len(text)
        if role == "tag":
            # 顶部地标轻标签：精致秀气
            base_ratio = 0.092 if n <= 5 else 0.084
        elif role == "sub":
            # 品类/副主标：适中偏醒目
            if is_three_lines:
                base_ratio = 0.110 if n <= 5 else 0.100
            else:
                base_ratio = 0.102 if n <= 6 else 0.092
        else:
            # hero 核心情绪大主标：视觉重心，放大抓眼球
            if n <= 5:
                base_ratio = 0.138
            elif n == 6:
                base_ratio = 0.128
            elif n == 7:
                base_ratio = 0.118
            else:
                base_ratio = 0.108
        return int(w * base_ratio)

    fonts = []
    line_widths = []
    line_heights = []
    line_y_offsets = []

    for idx, text in enumerate(lines):
        role = line_roles[idx] if idx < len(line_roles) else "hero"
        f_path = hero_font_path if role == "hero" else tag_font_path
        cur_size = get_role_font_size(text, role, num_lines == 3)
        font = ImageFont.truetype(f_path, cur_size)
        bbox = draw_ov.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        while text_w > max_allowed_w and cur_size > int(w * 0.04):
            cur_size -= 2
            font = ImageFont.truetype(f_path, cur_size)
            bbox = draw_ov.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]

        fonts.append(font)
        line_widths.append(text_w)
        line_heights.append(bbox[3] - bbox[1])
        line_y_offsets.append(bbox[1])

    emoji_font_size = int(w * 0.072)
    emoji_font_path = "C:/Windows/Fonts/seguiemj.ttf"
    emoji_font = None
    if os.path.exists(emoji_font_path):
        try:
            emoji_font = ImageFont.truetype(emoji_font_path, emoji_font_size)
        except Exception:
            emoji_font = None

    line_spacing = int(h * 0.022) if num_lines == 3 else int(h * 0.028)
    total_text_h = sum(line_heights) + (num_lines - 1) * line_spacing
    start_y = (h - total_text_h) // 2

    def draw_soft_pop_text(draw_target, x, y, text, font, fill_color, role: str):
        outline_w = 6 if role == "hero" else 4
        shadow_dist = 9 if role == "hero" else 6
        # 柔和立体深炭灰长投影 (避免死黑生硬感)
        for s in range(1, shadow_dist + 1):
            alpha_s = max(60, 200 - s * 14)
            draw_target.text((x + s, y + s), text, font=font, fill=(18, 16, 16, alpha_s))
        # 圆润抗锯齿深炭黑描边
        for ox in range(-outline_w, outline_w + 1):
            for oy in range(-outline_w, outline_w + 1):
                if ox * ox + oy * oy <= outline_w * outline_w + 1:
                    draw_target.text((x + ox, y + oy), text, font=font, fill=(22, 20, 20, 250))
        # 填充主色
        draw_target.text((x, y), text, font=font, fill=fill_color)

    cur_y = start_y
    for i in range(num_lines):
        text = lines[i]
        font = fonts[i]
        role = line_roles[i] if i < len(line_roles) else "hero"
        text_w = line_widths[i]
        text_h = line_heights[i]
        y_off = line_y_offsets[i]
        x = (w - text_w) // 2
        y = cur_y - y_off
        color = line_colors[i] if i < len(line_colors) else (255, 255, 255, 255)

        draw_soft_pop_text(draw_ov, x, y, text, font, fill_color=color, role=role)
        cur_y += text_h + line_spacing

    if emoji_font:
        em1 = emojis[0]
        em2 = emojis[1] if len(emojis) > 1 else emojis[0]
        em3 = emojis[2] if len(emojis) > 2 else "✨"

        top_y = start_y
        bottom_y = start_y + total_text_h

        pos_left = (int(w * 0.08), top_y - int(h * 0.032))
        pos_right = (int(w * 0.83), bottom_y + int(h * 0.012))
        pos_top = (int(w * 0.75), top_y - int(h * 0.075))

        try:
            draw_ov.text(pos_left, em1, font=emoji_font, embedded_color=True)
            draw_ov.text(pos_right, em2, font=emoji_font, embedded_color=True)
            draw_ov.text(pos_top, em3, font=emoji_font, embedded_color=True)
        except Exception:
            pass

    final_img = Image.alpha_composite(composed, draw_layer).convert("RGB")
    final_img.save(output_path, format="JPEG", quality=95)
    return output_path


def process_single_cover(target_dir: str, store_name: str, mask_opacity: float = 0.0) -> Optional[str]:
    """为指定目录（商铺根目录或'笔记 X'子目录）生成 V4 封面（默认无遮罩，通透鲜艳质感）"""
    bg_path = find_grid_cover_image(target_dir)
    if not bg_path:
        print(f"⚠️ 跳过 [{os.path.basename(target_dir)}]: 未找到九宫格底图 (需包含 mix9_*.jpg)")
        return None

    kw_path = os.path.join(target_dir, "店铺关键词.txt")
    data = parse_store_keywords(kw_path)
    if not data["store_name"]:
        data["store_name"] = store_name or os.path.basename(target_dir)

    note_idx = 1
    m_idx = re.search(r"笔记\s*(\d+)", os.path.basename(target_dir))
    if m_idx:
        try:
            note_idx = int(m_idx.group(1))
        except Exception:
            note_idx = 1

    title_data = build_cover_title_and_decorations(data, note_idx=note_idx)
    out_cover_path = os.path.join(target_dir, "商铺点评笔记_封面.jpg")
    try:
        draw_styled_cover(
            bg_image_path=bg_path,
            title_data=title_data,
            output_path=out_cover_path,
            mask_opacity=mask_opacity
        )
        print(f"==================================================")
        print(f"✅ [V4 年轻网感版] 成功生成封面(无遮罩通透版): {os.path.basename(target_dir)}")
        print(f"🖼️ 底图文件: {os.path.basename(bg_path)}")
        print(f"🔤 字体搭配: {title_data.get('font_style_name')} | 🎨 配色: {title_data['color_scheme']['name']}")
        for idx, l in enumerate(title_data.get("lines", []), 1):
            print(f"🏷️ 第{idx}行 ({title_data['line_roles'][idx-1]}): {l}")
        print(f"✨ 装饰表情: {' '.join(title_data['emojis'])}")
        print(f"📁 保存路径: {out_cover_path}")
        print(f"==================================================")
        return out_cover_path
    except Exception as e:
        print(f"❌ 生成封面图失败 [{os.path.basename(target_dir)}]: {e}")
        import traceback
        traceback.print_exc()
        return None


def process_store_cover(store_dir: str, mask_opacity: float = 0.0) -> List[str]:
    """处理单个商铺封面生成（自动穿透识别“笔记 1”、“笔记 2”等子目录）"""
    if not os.path.exists(store_dir):
        print(f"❌ 目录不存在: {store_dir}")
        return []

    store_name = os.path.basename(os.path.normpath(store_dir))

    sub_note_dirs = []
    for d in sorted(os.listdir(store_dir)):
        subp = os.path.join(store_dir, d)
        if os.path.isdir(subp) and re.match(r"^笔记\s*\d+$", d):
            sub_note_dirs.append(subp)

    generated_covers = []
    if sub_note_dirs:
        print(f"检测到商铺 [{store_name}] 下有 {len(sub_note_dirs)} 个笔记子文件夹，开始为各笔记生成 V4 独立封面...")
        for ndir in sub_note_dirs:
            c = process_single_cover(ndir, store_name=store_name, mask_opacity=mask_opacity)
            if c:
                generated_covers.append(c)
    else:
        c = process_single_cover(store_dir, store_name=store_name, mask_opacity=mask_opacity)
        if c:
            generated_covers.append(c)

    return generated_covers


def batch_process_covers(batch_dir: str, mask_opacity: float = 0.0):
    """批量处理目录下所有商铺子文件夹"""
    if not os.path.exists(batch_dir):
        print(f"❌ 批量父目录不存在: {batch_dir}")
        return

    subdirs = [os.path.join(batch_dir, d) for d in sorted(os.listdir(batch_dir)) if os.path.isdir(os.path.join(batch_dir, d))]
    print(f"🔍 检测到 {len(subdirs)} 个待处理店铺子文件夹，开始批量生成 V4 年轻网感封面图(无遮罩通透版)...")

    total_covers = 0
    skipped = 0
    for idx, sdir in enumerate(subdirs, 1):
        print(f"\n[{idx}/{len(subdirs)}] 处理商铺: {os.path.basename(sdir)}")
        res_list = process_store_cover(sdir, mask_opacity=mask_opacity)
        if res_list:
            total_covers += len(res_list)
        else:
            skipped += 1

    print(f"\n==========================================")
    print(f"🎉 [V4 年轻网感版] 批量封面生成完毕！共扫描 {len(subdirs)} 个店铺：")
    print(f"- 累计生成封面图: {total_covers} 张")
    print(f"- 跳过/失败: {skipped} 家")
    print(f"==========================================")


def main():
    parser = argparse.ArgumentParser(description="阿一商铺笔记封面生成器 V4 (免费商用网感字体+白领松弛感文案+主次字号错落层次+无遮罩通透原色)")
    parser.add_argument("--folder", type=str, default=None, help="单个商铺文件夹绝对路径")
    parser.add_argument("--batch_dir", type=str, default=None, help="包含多个商铺文件夹的父目录绝对路径")
    parser.add_argument("--mask_opacity", type=float, default=0.0, help="黑色涂层不透明度，默认 0.0 (无遮罩，保留原图通透鲜艳质感)")

    args = parser.parse_args()

    if args.folder:
        process_store_cover(args.folder, mask_opacity=args.mask_opacity)
    elif args.batch_dir:
        batch_process_covers(args.batch_dir, mask_opacity=args.mask_opacity)
    else:
        print("❌ 错误：请传入 --folder 或 --batch_dir 参数。")
        sys.exit(1)


if __name__ == "__main__":
    main()
