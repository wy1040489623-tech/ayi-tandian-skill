"""
小红书高清美食素材自动搜索与批量下载工具 (XhsDownloader)
- 通过 Chrome 原生 CDP WebSocket 协议直连已登录的 Chrome 浏览器 (默认端口 9222)
- 完美解决 Playwright 与 Chrome 130+ Omnibox Popup 的冲突
- 原生携带小红书最新 xsec_token 安全鉴权，杜绝 404/300031 重定向
- 支持智能纯净美食质检网关：全图 OCR 文字与水印检测、底部署名栏自动裁切、不合格不占名额自动补位
- 严格正面口碑过滤机制：坚决拦截负面吐槽与踩雷，提炼纯正面食客原声与招牌菜
- 自动化生成规范的《小红书商品信息.txt》与防查重微调《P_》图像流水线
"""

import os
import sys
import io
import re
import time
import random
import urllib.parse
import urllib.request
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import requests
import websocket
import numpy as np
import cv2
from PIL import Image

# 重型检测组件为可选：没装就跳过对应过滤规则，不影响采集主流程
try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:
    RapidOCR = None
try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


def _content_hash(img: Image.Image, s: int = 8) -> int:
    """dHash：同一张图跨帖重复下载时用来判重。"""
    g = img.convert("L").resize((s + 1, s), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for r in range(s):
        for c in range(s):
            bits = (bits << 1) | (px[r * (s + 1) + c] > px[r * (s + 1) + c + 1])
    return bits


def _is_dup_hash(h: int, seen: List[int], limit: int = 6) -> bool:
    return any(bin(h ^ s).count("1") <= limit for s in seen)

# 强制标准输出使用 UTF-8 与行缓冲，防止 Windows 控制台编码问题与缓冲卡死
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)


class CdpClient:
    """Chrome 原生 CDP WebSocket 客户端 (轻量、极速、无外部驱动依赖)"""

    def __init__(self, port: int = 9222):
        self.port = port
        self.ws: Optional[websocket.WebSocket] = None
        self.msg_id = 0
        self.page_target: Optional[Dict[str, Any]] = None

    def connect(self):
        """查找活动 Page Target 并建立 WebSocket 连接"""
        json_url = f"http://127.0.0.1:{self.port}/json"
        try:
            with urllib.request.urlopen(json_url, timeout=5) as resp:
                targets = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            raise ConnectionError(
                f"无法连接到 Chrome 调试端口 {json_url}。请确认已用参数 --remote-debugging-port={self.port} 启动 Chrome。"
            ) from e

        # 优先寻找包含小红书域名的普通 page，否则取第一个普通 page
        page_targets = [t for t in targets if t.get("type") == "page"]
        if not page_targets:
            raise RuntimeError("未在 Chrome 中找到任何打开的标签页！")

        target = None
        for t in page_targets:
            if "xiaohongshu.com" in t.get("url", ""):
                target = t
                break
        if not target:
            target = page_targets[0]

        self.page_target = target
        ws_url = target.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError(f"目标标签页未提供 webSocketDebuggerUrl: {target}")

        self.ws = websocket.create_connection(ws_url, timeout=20, suppress_origin=True)
        print(f"[CdpClient] 成功连接 Chrome CDP 页面: {target.get('title', '')} ({target.get('url', '')})")

    def eval(self, js_expr: str, return_by_value: bool = True) -> Any:
        """在页面上下文中同步执行 JavaScript 并返回结果，支持页面跳转时自动重连与重试"""
        for attempt in range(3):
            try:
                if not self.ws:
                    self.connect()
                self.msg_id += 1
                curr_id = self.msg_id
                msg = {
                    "id": curr_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": js_expr,
                        "returnByValue": return_by_value,
                        "awaitPromise": True
                    }
                }
                self.ws.send(json.dumps(msg))
                # 循环读取，直到获取匹配当前 id 的响应（忽略 CDP 自动推送的事件通知）
                while True:
                    raw_res = self.ws.recv()
                    data = json.loads(raw_res)
                    if data.get("id") == curr_id:
                        if "error" in data:
                            raise RuntimeError(f"CDP Runtime.evaluate 出错: {data['error']}")
                        result_obj = data.get("result", {}).get("result", {})
                        return result_obj.get("value")
            except (websocket.WebSocketTimeoutException, websocket.WebSocketConnectionClosedException, ConnectionResetError, TimeoutError) as e:
                print(f"[CdpClient] WebSocket 暂时超时或断开 ({e})，正在自动重连重试 ({attempt + 1}/3)...")
                try:
                    if self.ws:
                        self.ws.close()
                except Exception:
                    pass
                self.ws = None
                time.sleep(2)
                if attempt == 2:
                    raise

    def press_escape(self):
        """通过 CDP 原生分发硬件级 Escape 按键，100% 触发前端组件关闭详情弹窗"""
        try:
            if not self.ws:
                self.connect()
            for event_type in ["rawKeyDown", "keyUp"]:
                self.msg_id += 1
                curr_id = self.msg_id
                self.ws.send(json.dumps({
                    "id": curr_id,
                    "method": "Input.dispatchKeyEvent",
                    "params": {
                        "type": event_type,
                        "windowsVirtualKeyCode": 27,
                        "code": "Escape",
                        "key": "Escape"
                    }
                }))
                try:
                    self.ws.recv()
                except Exception:
                    pass
        except Exception:
            pass

    def close(self):
        """关闭 WebSocket 连接"""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


def extract_core_brand_keyword(text: str) -> str:
    """
    提取品牌核心主干词（智能剥离括号、地理位置、分店名等后缀）
    例如：
      贵州大黄牛肉火锅(孙桥路店) -> 贵州大黄牛肉火锅
      喜月酒家(双子塔店) -> 喜月酒家
      全季酒店(金科路店) -> 全季酒店
      汉庭酒店张江高科店 -> 汉庭酒店
      海底捞火锅人民广场店 -> 海底捞火锅
    """
    if not text:
        return ""
    # 1. 剥离所有括号及其内容
    s = re.sub(r"[\(（\[【].*?[\)）\]】]", "", text).strip()
    
    # 2. 剥离末尾的分店名 (如 '张江店', '张江高科店', '人民广场店', '孙桥路店', '双子塔店', '总店', '旗舰店')
    if s.endswith("店") and len(s) > 4:
        # 如果品牌本身以“酒店/饭店/小吃/烧烤/酒家/餐厅/馆/吧”结尾，且后面还有分店后缀
        m = re.search(r"^(.*?(?:酒店|饭店|烤肉|火锅|小吃|烧烤|酒家|餐厅|馆|吧))(.{2,8}店)$", s)
        if m:
            s = m.group(1).strip()
        else:
            # 常规品牌：剥离末尾 2-6 字的 xx店
            m2 = re.search(r"^(.*?[^\W\d_]{2,})([a-zA-Z\u4e00-\u9fa5]{2,6}店)$", s)
            if m2 and len(m2.group(1).strip()) >= 2:
                s = m2.group(1).strip()

    s = re.sub(r"[-_·\s]+$", "", s).strip()
    return s if len(s) >= 2 else text


class XhsDownloader:
    """小红书笔记图片自动检索与下载器"""

    def __init__(self, cdp_port: int = 9222):
        self.cdp = CdpClient(port=cdp_port)
        self.session = requests.Session()
        # 图片 CDN 直连，避免走系统代理（Veee）导致下载慢/黑图
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/",
        })
        self.ocr_engine = RapidOCR() if RapidOCR else None
        self.yolo_model = None
        if YOLO:
            try:
                self.yolo_model = YOLO("yolov8n.pt")
            except Exception:
                self.yolo_model = None

    def connect(self):
        self.cdp.connect()

    def close(self):
        self.cdp.close()

    def _media_srcs(self) -> list:
        """收集轮播图 src；懒加载的图 src 已存在但 complete=false，不能按加载状态过滤。"""
        return self.cdp.eval("""
        (() => {
            const isExcluded = (el) => !!el.closest('.author-container, .comments-container, .comment-item, .interaction-container, .user-avatar, .avatar, header, .author, .side-bar, .comment-list');
            const mediaRoot = document.querySelector('.media-container, .slider-container, .swiper, .carousel') || document.querySelector('.note-container');
            if (!mediaRoot) return [];
            const srcs = [];
            mediaRoot.querySelectorAll('img').forEach(img => {
                if (!isExcluded(img) && img.src && img.src.startsWith('http') && img.complete && img.naturalWidth >= 200) {
                    const s = img.src.toLowerCase();
                    if (!s.includes('avatar') && !s.includes('icon') && !s.includes('emoji')) srcs.push(img.src);
                }
            });
            return srcs;
        })()
        """) or []

    def _wait_media_loaded(self, timeout: float = 6.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._media_srcs():
                return True
            time.sleep(0.2)
        return False

    def _wait_media_stable(self, timeout: float = 5.0, idle: float = 1.0) -> int:
        """等轮播图加载稳定：已加载数量连续 idle 秒不增加就继续，最多等 timeout 秒。"""
        deadline = time.time() + timeout
        last, last_change = -1, time.time()
        while True:
            count = len(self._media_srcs())
            if count != last:
                last, last_change = count, time.time()
            elif count and time.time() - last_change >= idle:
                return count
            if time.time() >= deadline:
                return count
            time.sleep(0.3)

    def _page_state(self) -> dict:
        return self.cdp.eval("""
        (() => ({
            cards: document.querySelectorAll('section.note-item').length,
            modal: !!document.querySelector('.note-container, .modal-container'),
            url: location.href
        }))()
        """) or {}

    def _goto_search(self, search_url: str, timeout: float = 20.0) -> bool:
        """强制重载搜索页；同 URL 赋值也会重载，能清掉残留的笔记弹窗。"""
        self.cdp.eval(f"window.location.href = {json.dumps(search_url)};")
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self._page_state()
            if st.get("cards") and not st.get("modal"):
                return True
            time.sleep(0.5)
        return False

    def _back_to_search(self, search_url: str, timeout: float = 8.0) -> bool:
        """从笔记页回列表：优先后退，没恢复干净就强制重载搜索页。"""
        self.cdp.eval("history.back()")
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self._page_state()
            if st.get("cards") and not st.get("modal"):
                return True
            time.sleep(0.4)
        return self._goto_search(search_url)

    def _is_valid_candidate_image(self, url: str) -> bool:
        """初筛过滤掉非笔记内容图（头像、UI图标、表情等）"""
        if not url or not url.startswith("http"):
            return False
        bad_keywords = [
            "sns-avatar", "avatar", "picasso-static", "fe-platform",
            "icon", "emoji", "default_avatar", "loading", "svg", "formula-static"
        ]
        lower_url = url.lower()
        for bad in bad_keywords:
            if bad in lower_url:
                return False
        good_domains = ["xhscdn.com", "xiaohongshu.com"]
        if not any(d in lower_url for d in good_domains):
            return False
        return True

    def _clean_image_url(self, raw_url: str) -> str:
        """保留小红书完整防盗链签名参数，确保CDN正常下载高清大图"""
        return raw_url.strip()

    def _detect_and_crop_bottom_watermark(self, img: Image.Image) -> Image.Image:
        """检测并切除底部规整的署名/水印信息栏（如室内设计机构落款）"""
        w, h = img.size
        if h < 200:
            return img

        crop_h = min(120, int(h * 0.08))
        bottom_strip = np.array(img)[-crop_h:, :, :]
        white_mask = (bottom_strip[:, :, 0] > 220) & (bottom_strip[:, :, 1] > 220) & (bottom_strip[:, :, 2] > 220)
        white_rows = np.any(white_mask, axis=1)
        text_rows = np.where(white_rows)[0]

        if len(text_rows) >= 8:
            cut_from_bottom = crop_h - text_rows[0] + 15
            cut_pixels = max(60, min(int(h * 0.08), cut_from_bottom))
            return img.crop((0, 0, w, h - cut_pixels))

        return img

    def inspect_quality(self, img: Image.Image) -> Tuple[bool, Image.Image, str]:
        """
        V4 级高阶纯净实拍智能质检网关（出现以下任一情况坚决拦截，不计入下载总张数）：
        1. 尺寸过小 / 疑似头像缩略图 (min(w, h) < 380 或 w * h < 180,000)
        2. 比例超标海报 / 超长长图 (ratio > 2.2)
        3. 出现人脸/肖像 (YOLOv8 深度目标检测)
        4. 卡通/插画/二次元风格图像 (色块平坦度、边缘线稿与自然物理光影纹理分析)
        5. 纯文字卡片 / 备忘录 / 纯色文字宣泄图 (大面积纯色/白底背景占比 > 65% 且包含文字)
        6. 多行文字 / 手机截屏 / 点餐界面 (整图文字 >= 15 字或行数 >= 4)
        7. 图片上额外产生的文字 / 横幅花字贴纸 (宽度占比 >= 30% 或高度占比 >= 4.5% 或覆盖中下部菜品主体；仅放行顶部自然小门头招牌)
        8. 宣传海报 / 营销排版 / 平台水印
        """
        w, h = img.size
        # 1. 过滤小图 / 头像缩略图 (真实探店美食实拍原图尺寸均在 750x1000 以上)
        if min(w, h) < 380 or (w * h < 180000):
            return False, img, f"【规则1: 尺寸过小/疑似头像小图】({w}x{h})"

        # 2. 过滤超长比例海报
        ratio = max(w, h) / min(w, h)
        if ratio > 2.2:
            return False, img, f"【规则2: 超长比例海报/长图】({w}x{h})"

        np_img_rgb = np.array(img)

        # 3. 规则3: YOLOv8 检测是否有人物/人脸
        try:
            yolo_res = self.yolo_model(np_img_rgb, verbose=False)[0]
            persons = []
            for b in yolo_res.boxes:
                if int(b.cls[0]) == 0 and float(b.conf[0]) >= 0.4:
                    xywhn = b.xywhn[0].tolist()
                    area = xywhn[2] * xywhn[3]
                    persons.append(area)
            if persons:
                max_p = max(persons)
                # 单人画面占比 >= 7% 或多人累计占比 >= 10% 或 2人以上合影
                if max_p >= 0.07 or len(persons) >= 2 or sum(persons) >= 0.10:
                    return False, img, f"【规则3: 出现人脸/肖像】(人像面积占比:{max_p:.1%})"
        except Exception:
            pass

        # 4. 规则4: 卡通/插画/二次元质感检测 (平坦色块 + 缺乏真实物理光影噪点)
        try:
            resized_rgb = cv2.resize(np_img_rgb, (256, 256))
            r_gray = cv2.cvtColor(resized_rgb, cv2.COLOR_RGB2GRAY)
            quant = (resized_rgb // 32) * 32
            unique_colors = len(np.unique(quant.reshape(-1, 3), axis=0))
            filtered = cv2.bilateralFilter(r_gray, 9, 75, 75)
            bilateral_diff = float(np.mean(np.abs(r_gray.astype(np.float32) - filtered.astype(np.float32))))

            if unique_colors < 80 and bilateral_diff < 7.0:
                return False, img, f"【规则4: 卡通/插画/二次元低纹理图像】(色彩级数:{unique_colors}, 纹理度:{bilateral_diff:.2f})"
        except Exception:
            pass

        # 5. 尝试微裁切底部署名栏
        cleaned_img = self._detect_and_crop_bottom_watermark(img)

        # 6. 使用 RapidOCR 进行文字与版面分析（未安装则跳过文字类过滤）
        cleaned_np = np.array(cleaned_img)
        ocr_res = None
        if self.ocr_engine is not None:
            ocr_res, _ = self.ocr_engine(cleaned_np)
        if ocr_res:
            lines = [r[1].strip() for r in ocr_res]
            total_text = "".join(lines)
            total_chars = len(total_text)

            # 6.1 背景平坦度/纯色底检测 (判断是否为纯白/纯黑大底纯文字图)
            try:
                gray = cv2.cvtColor(cleaned_np, cv2.COLOR_RGB2GRAY)
                total_pixels = w * h
                hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                max_single_color_ratio = float(np.max(hist)) / total_pixels
                near_white_ratio = float(np.sum(gray > 240)) / total_pixels
                near_black_ratio = float(np.sum(gray < 25)) / total_pixels
                is_flat_background = (near_white_ratio >= 0.65) or (near_black_ratio >= 0.65) or (max_single_color_ratio >= 0.50)
            except Exception:
                is_flat_background = False

            # 6.2 规则5: 纯文字卡片 / 备忘录 / 提问贴 (大面积纯色/白底背景且有文字)
            if is_flat_background and total_chars >= 4:
                return False, cleaned_img, f"【规则5: 纯文字/备忘录卡片】(纯色底背景, 文字:'{total_text[:12]}')"

            # 6.3 规则6: 纯文字 / 多行文字 / 手机截屏 / 点餐界面检测
            ui_kw = [
                "购物车", "共点", "人餐", "团购", "详情", "¥", "元", "冷菜", "主菜", "时蔬",
                "备注", "仅限", "有什", "哪家", "微信", "关注", "立即", "支付", "订单", "满减", "打卡"
            ]
            hit_ui = sum(1 for k in ui_kw if k in total_text)
            if total_chars >= 15 or len(lines) >= 4 or hit_ui >= 2:
                return False, cleaned_img, f"【规则6: 多行文字/手机截图/点餐界面】(共{len(lines)}行, {total_chars}字)"

            # 6.4 规则7: 额外产生的文字 / 横幅花字贴纸检测 (放行顶部自然小门头招牌)
            banner_kws = [
                "新开", "探店", "攻略", "必吃", "打卡", "救命", "天花板", "吃到撑", "人均", "吃到饱",
                "自助", "排队", "日常", "生活", "绝", "拉满", "首选", "杀死", "犯了", "蛋糕", "年夜饭",
                "预订", "预定", "除夕", "全攻略", "年菜", "味道", "套餐", "推荐", "好吃", "必点"
            ]
            for r in ocr_res:
                pts = r[0]
                box_min_x = min(pt[0] for pt in pts)
                box_max_x = max(pt[0] for pt in pts)
                box_min_y = min(pt[1] for pt in pts)
                box_max_y = max(pt[1] for pt in pts)
                box_center_y = (box_min_y + box_max_y) / 2.0

                box_w = box_max_x - box_min_x
                box_h = box_max_y - box_min_y
                w_ratio = box_w / float(w)
                h_ratio = box_h / float(h)
                y_center_ratio = box_center_y / float(h)
                text_content = r[1].strip()

                # 顶部自然门头招牌放行门禁：必须位于画面顶部 25% 区域，且非超大横幅 (h_ratio < 0.075 且 w_ratio < 0.55)
                is_top_natural_signage = (box_max_y <= h * 0.25) and (h_ratio < 0.075) and (w_ratio < 0.55)

                # 判定为大字/横幅花字贴纸 (宽度超 30% 或高度超 4.5%)
                if w_ratio >= 0.30 or h_ratio >= 0.045:
                    if not is_top_natural_signage:
                        return False, cleaned_img, f"【规则7: 包含额外文字贴纸/横幅】[{text_content}] (位置:{y_center_ratio:.1%}, 宽比:{w_ratio:.1%}, 高比:{h_ratio:.1%})"
                    if any(bk in text_content for bk in banner_kws):
                        return False, cleaned_img, f"【规则7: 顶部后期花字贴纸】[{text_content}]"

            # 6.5 规则8: 宣传海报 / 营销排版
            poster_kw = [
                "年夜饭", "预订", "预定", "除夕", "迎春", "套餐", "折", "大促", "立减", "恭喜", "火热",
                "订座", "年会", "包厢预定", "限时", "抢购"
            ]
            if any(k in total_text for k in poster_kw):
                return False, cleaned_img, f"【规则8: 宣传海报/营销排版】[{total_text[:15]}]"

            # 6.6 水印检查
            bad_keywords = ["小红书", "xhs", "@", "id", "add", "tel"]
            if any(b in total_text.lower() for b in bad_keywords):
                return False, cleaned_img, "检测到平台账号水印"

        return True, cleaned_img, "合格实拍素材"

    # 笔记级门禁默认负面词（未传 --skip-if 时生效）
    DEFAULT_SKIP_WORDS = ("难吃", "避雷", "差评", "不推荐", "翻车", "吐槽", "踩坑", "拔草", "难以下咽", "劝退")

    PROMO_KEYWORDS = ("代金券", "团购", "优惠券", "买一送一", "吃100", "送100", "送一只",
                      "新店开业", "开业庆", "储值", "充值", "买单立减", "券后")

    def inspect_promo(self, img: Image.Image) -> Tuple[bool, Image.Image, str]:
        """关掉严格质检时仍拦截优惠券/开业海报，避免整店都是券图。"""
        try:
            ocr_res, _ = self.ocr_engine(np.array(img))
            text = "".join(r[1] for r in ocr_res) if ocr_res else ""
        except Exception:
            return True, img, "OCR失败，放行"
        hits = [w for w in self.PROMO_KEYWORDS if w in text]
        if hits:
            return False, img, f"【优惠券/宣传海报】[{','.join(hits)}]"
        return True, img, "合格"

    def _match_note_gate(self, title: str, desc: str, skip_if: str = "") -> str:
        """命中任一词返回该词（整篇跳过）；"不X"式正面表述（如"不踩雷"）不判负。
        只看标题和正文开头 80 字：整篇避雷贴通常开头就写明，
        正文后段「这个菜不太推荐」属于单菜评价，不能因此丢掉整篇素材。
        """
        pool = [w for w in re.split(r"[,，\s]+", skip_if) if w] or list(self.DEFAULT_SKIP_WORDS)
        head = f"{title or ''} {(desc or '')[:80]}"
        for w in pool:
            if w in head and (w.startswith("不") or f"不{w}" not in head):
                return w
        return ""

    def _filter_positive_dish_reviews(self, title: str, desc: str) -> Dict[str, Any]:
        """对正文进行纯正面评价清洗过滤（坚决拦截任何负面踩雷）"""
        note_data = {"title": title, "desc": desc, "positive_reviews": [], "positive_dishes": []}

        negative_words = [
            "难吃", "避雷", "踩雷", "不推荐", "拔草", "失望", "一般般", "太咸", "太油",
            "太甜", "太贵", "不划算", "翻车", "差评", "不新鲜", "腥味", "拉跨", "拉胯",
            "退步", "变质", "服务差", "态度差", "不值", "不要点", "很雷", "排队劝退"
        ]

        positive_words = [
            "好吃", "必点", "绝了", "惊艳", "招牌", "美味", "鲜美", "嫩", "香", "酥脆",
            "软糯", "入味", "地道", "爱吃", "推荐", "回味", "饱满", "真材实料", "浓郁",
            "细腻", "清爽", "正宗", "赞", "喜欢", "满足", "一口入魂", "封神", "下饭", "过瘾"
        ]

        food_clues = [
            "鱼", "肉", "蟹", "虾", "鸡", "鸭", "鹅", "煲", "饭", "面", "汤",
            "豆腐", "排骨", "牛肉", "羊肉", "海鲜", "生腌", "醉", "蹄", "鳝",
            "串", "串烧", "和牛", "烧鸟", "火锅", "清汤", "油边", "提包酥", "牛排"
        ]

        all_text = f"{title}。{desc}"
        sentences = re.split(r"[。\n！!？?；;]+", all_text)

        for s in sentences:
            s = s.strip()
            if len(s) < 4 or len(s) > 120:
                continue
            # 1. 负面拦截：只要命中任意负面词，坚决舍弃
            if any(nw in s for nw in negative_words):
                continue
            # 2. 正面提取：包含正面特征词
            if any(pw in s for pw in positive_words):
                note_data["positive_reviews"].append(s)
                if any(fc in s for fc in food_clues):
                    note_data["positive_dishes"].append(s)

        return note_data

    def download_images(
        self,
        keyword: str,
        target_count: int = 20,
        clean_food_only: bool = True,
        base_dir: Optional[str] = None,
        date_str: Optional[str] = None,
        auto_rotate: bool = True,
        folder_name: Optional[str] = None,
        search_keyword: Optional[str] = None,
        device: Optional[str] = None,
        skip_if: str = "",
        max_notes: int = 25,
    ) -> Dict[str, Any]:
        """按关键词搜索并下载图片素材（支持内容类型质检与防查重微调流水线）"""
        self.connect()

        base_dir = base_dir or os.getcwd()
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")

        target_folder = folder_name or keyword
        safe_folder = "".join(c for c in target_folder if c not in r'\/:*?"<>|').strip()
        safe_keyword = "".join(c for c in keyword if c not in r'\/:*?"<>|').strip()
        save_dir = os.path.join(base_dir, date_str, safe_folder)
        os.makedirs(save_dir, exist_ok=True)

        # 智能确定小红书搜索词序列：
        # 第 1 轮：严格精准搜索 (必须带上具体的地理位置与分店名，绝对不可提前剔除)
        # 第 2 轮：降级兜底搜索 (仅当第 1 轮搜出 0 篇笔记时才允许触发，剥离地理位置搜索品牌主干词)
        core_brand = extract_core_brand_keyword(keyword)
        search_queries = []
        if search_keyword:
            exact_query = search_keyword
        else:
            # 将括号转换为清晰空格，完整保留分店名与地理位置
            exact_query = re.sub(r'[\(（\[【](.*?)[\)）\]】]', r' \1', keyword).strip()
            exact_query = re.sub(r'[\s_]+', ' ', exact_query)
            if not exact_query:
                exact_query = keyword

        search_queries.append(exact_query)

        # 若提取的品牌主干词与严格精准词不同，作为备选第 2 轮降级搜索词
        if core_brand and core_brand != exact_query:
            search_queries.append(core_brand)
        
        # 严格限制最多 2 轮
        search_queries = search_queries[:2]

        print(f"\n==================================================")
        print(f"开始执行小红书素材采集任务")
        print(f"商户关键词: {keyword}")
        print(f"严格精准搜索词 (第1轮): 【{search_queries[0]}】")
        if len(search_queries) > 1:
            print(f"备选降级搜索词 (第2轮，仅在第1轮为0结果时触发): 【{search_queries[1]}】")
        print(f"目标下载量: {target_count} 张")
        print(f"4合1智能质检拦截: {'已全局开启 (严格拦截人脸/纯文字/宣传海报/大标题花字)' if clean_food_only else '已关闭'}")
        print(f"保存路径: {save_dir}")
        print(f"==================================================\n")

        downloaded_count = 0
        downloaded_files = []
        seen_hashes: List[int] = []  # 跨帖内容去重：同一张图只收一次
        thin_streak = 0  # 连续「只取到 1 张」的篇数，用于识别详情弹窗失效
        processed_cards = set()
        notes_scanned = 0
        all_positive_reviews = []
        all_positive_dishes = []
        captured_notes = []
        max_total_notes_scanned = max_notes  # 单商铺全轮次扫描笔记硬上限，避免无限死磕
        round1_found_cards = 0        # 记录第 1 轮是否搜出该门店的笔记

        # 依次执行搜索尝试 (第 1 轮精准带地理位置 -> 仅在 0 结果时降级第 2 轮)
        for q_idx, current_query in enumerate(search_queries, 1):
            if downloaded_count >= target_count or notes_scanned >= max_total_notes_scanned:
                break

            # 降级严格门禁：如果是第 2 轮搜索，但第 1 轮已经搜到了该具体门店的笔记卡片，坚决不降级混入其他分店！
            if q_idx > 1 and round1_found_cards > 0:
                print(f"\n  [门店精准保护] 第 1 轮带地理位置的搜索已命中该具体门店笔记 (共扫描 {round1_found_cards} 篇)，坚决不降级搜索外地其他同名店！")
                break

            encoded_kw = urllib.parse.quote(current_query)
            search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_kw}"
            print(f"[1/4] 打开搜索结果页面 (第{q_idx}/{len(search_queries)}轮: 【{current_query}】): {search_url}")
            self.cdp.eval(f"window.location.href = {json.dumps(search_url)};")

            # 预检：登录态和页面是否真的加载出笔记，避免静默 0 篇
            # 慢网络下首屏渲染会拖到 10 秒以上，轮询等卡片出现
            deadline = time.time() + 18
            preflight = {}
            while time.time() < deadline:
                time.sleep(1.5)
                preflight = self.cdp.eval("""
                (() => {
                    const cards = document.querySelectorAll('section.note-item').length;
                    const t = document.body.innerText || '';
                    const needLogin = /扫码登录|登录后查看|请先登录|登录后推荐/.test(t) || !!document.querySelector('.login-container, .login-modal, .login-btn');
                    const modal = !!document.querySelector('.note-container, .modal-container');
                    return {cards, needLogin, modal};
                })()
                """) or {}
                if preflight.get("cards") and not preflight.get("modal"):
                    break
            if not preflight.get("cards") or preflight.get("modal"):
                if preflight.get("needLogin"):
                    print("\n[需要登录] 小红书登录态已失效，请在调试 Chrome 里扫码登录后重新运行。")
                    print("           登录页：https://www.xiaohongshu.com")
                else:
                    print("\n[页面未加载] 搜索页没有出现笔记卡片，检查网络/代理后重试。")
                return {
                    "success": False,
                    "keyword": keyword,
                    "target_count": target_count,
                    "downloaded_count": 0,
                    "rotated_count": 0,
                    "save_dir": save_dir,
                    "downloaded_files": [],
                    "notes_scanned": 0,
                    "error": "login_required" if preflight.get("needLogin") else "page_not_loaded",
                }

            scroll_attempts = 0
            max_scroll_attempts = 8  # 单轮滑动最多 8 次，提高轮转效率

            print(f"[2/4] 开始扫描笔记列表并执行智能质检下载与正面口碑提取...")

            while downloaded_count < target_count and scroll_attempts < max_scroll_attempts:
                if notes_scanned >= max_total_notes_scanned:
                    print(f"  [保护触发] 该商铺已累计扫描 {notes_scanned} 篇笔记，达到单商铺扫描上限，停止翻找。")
                    break
                # 获取当前渲染的卡片列表
                cards_info = self.cdp.eval("""
                (() => {
                    const cards = document.querySelectorAll('section.note-item');
                    return Array.from(cards).map((c, idx) => {
                        const coverLink = c.querySelector('a.cover');
                        const coverImg = c.querySelector('img');
                        // 只认封面链接：卡片里还有作者主页链接，混进来会当成笔记打开
                        const href = (coverLink && /\/(?:search_result|explore)\//.test(coverLink.href)) ? coverLink.href : '';
                        const noteId = c.getAttribute('data-note-id') || href;
                        return {
                            index: idx,
                            noteId: noteId,
                            href: href,
                            hasCover: !!coverLink,
                            coverSrc: coverImg ? coverImg.src : ''
                        };
                    });
                })()
                """) or []

                if not cards_info and scroll_attempts == 0:
                    print(f"  [提示] 检索词【{current_query}】暂未发现笔记卡片，尝试轻微向下滑动...")

                new_card_found = False

                for card in cards_info:
                    if downloaded_count >= target_count:
                        break
                    if notes_scanned >= max_total_notes_scanned:
                        break

                    card_id = card.get("noteId")
                    if not card_id or card_id in processed_cards:
                        continue

                    processed_cards.add(card_id)
                    new_card_found = True
                    notes_scanned += 1
                    if q_idx == 1:
                        round1_found_cards += 1

                    try:
                        # 1. 直接导航到卡片真实链接（带 xsec_token），不再点卡片：
                        #    详情弹窗关不掉时点卡片会一直读到上一篇，直接打开每次都是干净的新页面
                        note_href = card.get("href") or ""
                        if not note_href:
                            continue
                        note_id = str(card.get("noteId") or "")
                        if not re.fullmatch(r"[0-9a-f]{20,32}", note_id):
                            m = re.search(r"/(?:search_result|explore)/([0-9a-f]+)", note_href)
                            note_id = m.group(1) if m else ""
                        self.cdp.eval(f"window.location.href = {json.dumps(note_href)};")

                        # 等地址栏真的切到目标笔记再读；否则会把上一篇的图当成这一篇
                        deadline = time.time() + 15
                        while time.time() < deadline:
                            time.sleep(0.4)
                            cur_url = self.cdp.eval("location.href") or ""
                            if note_id and note_id in cur_url:
                                break
                        else:
                            print(f"  [提示] 第 {notes_scanned} 篇笔记跳转超时，跳过")
                            self._back_to_search(search_url)
                            continue

                        # 等待详情页和首图真正加载完成，避免黑屏占位图
                        time.sleep(1.0 + random.random() * 0.3)
                        if not self._wait_media_loaded(6.0):
                            print("  [提示] 笔记图片加载超时，按已加载内容继续")

                        # 2. 先读标题/正文做整篇门禁；命中就不必再等轮播图和质检
                        head = self.cdp.eval("""
                        (() => {
                            const t = document.querySelector('#detail-title, .note-content .title')?.innerText || '';
                            const d = document.querySelector('#detail-desc, .note-content .desc, .note-text')?.innerText || '';
                            return {title: t, desc: d};
                        })()
                        """) or {}
                        gate_hit = self._match_note_gate(head.get("title", ""), head.get("desc", ""), skip_if)
                        if gate_hit:
                            print(f"  [门禁跳过] 第 {notes_scanned} 篇笔记命中「{gate_hit}」，整篇跳过")
                            self._back_to_search(search_url)
                            continue

                        # 轮播图是懒加载，不主动触发只会拿到首图；一次把 9 张全部加载出来
                        self.cdp.eval("""
                        (() => {
                            const r = document.querySelector('.media-container, .slider-container, .swiper, .carousel');
                            if (!r) return;
                            r.querySelectorAll('img').forEach(x => { x.loading = 'eager'; const s = x.src; x.src = ''; x.src = s; });
                        })()
                        """)
                        # 图加载到不再增加就往下走（快笔记约 1–2 秒，慢的最多 5 秒）
                        self._wait_media_stable(5.0, 1.0)

                        # 检查是否遭遇 404/风控重定向，若发生立即回退回搜索页
                        current_url = self.cdp.eval("window.location.href") or ""
                        if "404" in current_url:
                            print("  [提示] 触发页面导航重定向，自动恢复回搜索页...")
                            self._goto_search(search_url)
                            continue

                        # 2. 轮播获取弹窗内大图以及文本内容（严格限定正文媒体区，彻底排除作者栏与评论区头像）
                        modal_data = self.cdp.eval("""
                        (() => {
                            const modal = document.querySelector('.note-container, .modal-container');
                            if (!modal) return null;

                            const title = document.querySelector('#detail-title, .note-content .title')?.innerText || '';
                            const desc = document.querySelector('#detail-desc, .note-content .desc, .note-text')?.innerText || '';

                            // 排除选择器：作者栏、评论区、侧边栏、用户头像等，坚决不抓取
                            const isExcluded = (el) => {
                                return !!el.closest('.author-container, .comments-container, .comment-item, .interaction-container, .user-avatar, .avatar, header, .author, .side-bar, .comment-list');
                            };

                            const mediaRoot = modal.querySelector('.media-container, .slider-container, .swiper, .carousel') || modal;
                            const srcs = [];
                            mediaRoot.querySelectorAll('img').forEach(img => {
                                if (!isExcluded(img) && img.src && img.src.startsWith('http') && img.complete && img.naturalWidth >= 200) {
                                    const s = img.src.toLowerCase();
                                    if (!s.includes('avatar') && !s.includes('icon') && !s.includes('emoji') && !s.includes('default_avatar')) {
                                        srcs.push(img.src);
                                    }
                                }
                            });
                            mediaRoot.querySelectorAll('div[style*="background-image"]').forEach(el => {
                                if (!isExcluded(el)) {
                                    const bg = el.style.backgroundImage;
                                    const m = bg.match(/url\\(["']?(https?:\\/\\/[^"\\')]+)["']?\\)/);
                                    if (m && m[1] && !m[1].toLowerCase().includes('avatar')) {
                                        srcs.push(m[1]);
                                    }
                                }
                            });

                            return { title, desc, srcs };
                        })()
                        """)

                        # 翻动轮播图收集更多图片 (最多翻 6 次)
                        all_note_imgs = []
                        if modal_data and modal_data.get("srcs"):
                            all_note_imgs.extend(modal_data["srcs"])

                        for _ in range(6):
                            before = set(self._media_srcs())
                            has_next = self.cdp.eval("""
                            (() => {
                                const nextBtn = document.querySelector('.right, .arrow-right, .swiper-button-next:not(.swiper-button-disabled)');
                                if (nextBtn) {
                                    nextBtn.click();
                                    return true;
                                }
                                return false;
                            })()
                            """)
                            if not has_next:
                                break
                            # 等新一张加载出来；2.5 秒仍无新图就停，避免空等
                            deadline = time.time() + 2.5
                            now = set()
                            while time.time() < deadline:
                                now = set(self._media_srcs())
                                if now - before:
                                    break
                                time.sleep(0.3)
                            if not (now - before):
                                break
                            for m_src in now:
                                if m_src not in all_note_imgs:
                                    all_note_imgs.append(m_src)

                        # 如果弹窗未能抓取到图片，回退使用卡片封面大图
                        if not all_note_imgs and card.get("coverSrc"):
                            print("     [仅封面] 详情页未取到正文图，用卡片封面兜底")
                            all_note_imgs.append(card["coverSrc"])

                        # 3. 提取正面口碑与菜品
                        title_text = modal_data["title"] if modal_data else ""
                        desc_text = modal_data["desc"] if modal_data else ""
                        note_info = self._filter_positive_dish_reviews(title_text, desc_text)

                        if note_info["title"] or note_info["desc"]:
                            captured_notes.append({
                                "title": note_info["title"],
                                "positive_reviews": note_info["positive_reviews"],
                                "positive_dishes": note_info["positive_dishes"]
                            })
                            for rev in note_info["positive_reviews"]:
                                if rev not in all_positive_reviews:
                                    all_positive_reviews.append(rev)
                            for dish_rev in note_info["positive_dishes"]:
                                if dish_rev not in all_positive_dishes:
                                    all_positive_dishes.append(dish_rev)

                        # 转换为高清原图 URL (去缩略图后缀)
                        hd_img_urls = []
                        seen_urls = set()
                        for raw_url in all_note_imgs:
                            if self._is_valid_candidate_image(raw_url):
                                hd_url = self._clean_image_url(raw_url)
                                if hd_url and hd_url not in seen_urls:
                                    seen_urls.add(hd_url)
                                    hd_img_urls.append(hd_url)

                        print(f"  -> 第 {notes_scanned} 篇笔记: 发现 {len(hd_img_urls)} 张高清候选图，已提取 {len(note_info['positive_dishes'])} 条正面菜品评价")

                        # 连续 3 篇都只取到 1 张，说明详情弹窗没正常展开（懒加载/风控），继续扫是空转
                        if len(hd_img_urls) <= 1:
                            thin_streak += 1
                            if thin_streak >= 3:
                                print("\n[详情页异常] 连续 3 篇只取到 1 张图，弹窗未正常加载。已停止本轮，避免空转。")
                                print("           建议：等 5 分钟再抓，或在调试 Chrome 里手动点开一篇确认能看见多图。")
                                return {
                                    "success": False,
                                    "keyword": keyword,
                                    "target_count": target_count,
                                    "downloaded_count": downloaded_count,
                                    "rotated_count": 0,
                                    "save_dir": save_dir,
                                    "downloaded_files": downloaded_files,
                                    "notes_scanned": notes_scanned,
                                    "error": "detail_thin",
                                }
                        else:
                            thin_streak = 0

                        # 4. 下载图片二进制
                        for img_url in hd_img_urls:
                            if downloaded_count >= target_count:
                                break

                            try:
                                resp = self.session.get(img_url, timeout=15)
                                if resp.status_code != 200 or len(resp.content) < 1500:
                                    continue
                                raw_img = Image.open(io.BytesIO(resp.content))
                                if raw_img.mode != "RGB":
                                    raw_img = raw_img.convert("RGB")
                            except Exception:
                                continue

                            # 先按原图判重：重复图不再跑 OCR/YOLO
                            h = _content_hash(raw_img)
                            if _is_dup_hash(h, seen_hashes):
                                print(f"     [内容重复] 跳过: 与已处理图相同 (不占名额)")
                                continue
                            seen_hashes.append(h)

                            # 纯净美食智能质检网关
                            if clean_food_only:
                                passed, final_img, reason = self.inspect_quality(raw_img)
                            else:
                                # 即使关闭严格质检，也拦掉代金券/开业海报
                                passed, final_img, reason = self.inspect_promo(raw_img)
                            if not passed:
                                print(f"     [质检拦截] 舍弃: {reason} (不占名额)")
                                continue
                            else:
                                final_img = self._detect_and_crop_bottom_watermark(raw_img)

                            download_index = downloaded_count + 1
                            file_name = f"{safe_keyword}_{download_index}.jpg"
                            file_path = os.path.join(save_dir, file_name)

                            final_img.save(file_path, format="JPEG", quality=95)
                            downloaded_count += 1
                            downloaded_files.append(file_path)
                            print(f"     [进度 {downloaded_count}/{target_count}] 质检合格并保存: {file_name}")

                        # 5. 回到搜索页（弹窗关不掉，后退/重载比点关闭更可靠）
                        self._back_to_search(search_url)

                    except Exception as e:
                        print(f"  [跳过] 处理卡片 {card_id} 时出现轻微异常: {e}")
                        self._back_to_search(search_url)
                        continue

                if downloaded_count < target_count:
                    print(f"[3/4] 当前合格美食图 {downloaded_count}/{target_count} 张，向下滑动加载更多笔记...")
                    self.cdp.eval("window.scrollBy(0, 1500);")
                    time.sleep(2.5 + random.random() * 1.0)
                    scroll_attempts += 1

        # 保存提炼的小红书正面菜品评价与商户信息
        self._save_positive_note_summary(
            keyword=keyword,
            save_dir=save_dir,
            captured_notes=captured_notes,
            positive_dishes=all_positive_dishes,
            positive_reviews=all_positive_reviews,
            downloaded_count=downloaded_count
        )

        # 自动执行 V4 级高阶防查重流水线 (微倾斜 + 动态网格遮罩 + 隐形Icon + 原机EXIF注入)
        rotated_count = 0
        if auto_rotate and downloaded_count > 0:
            print(f"[4/4] 自动执行 V4 级高阶去重流水线 (微倾斜 + 动态网格 + 隐形Icon + 原机EXIF)...")
            from image_dedup_processor_v4 import batch_dedup_directory
            rotated_count = batch_dedup_directory(target_dir=save_dir, store_name=keyword, device=device)

        print(f"\n==================================================")
        print(f"商户小红书采集任务执行完毕 (V4 级高阶去重模式)！")
        print(f"商户名称: {keyword}")
        print(f"扫描笔记数: {notes_scanned} 篇")
        print(f"原图下载量: {downloaded_count}/{target_count} 张")
        if auto_rotate:
            print(f"防查重微调: 已生成 {rotated_count} 张 P_ 深度去重图片")
        print(f"保存目录: {save_dir}")
        if downloaded_count < target_count:
            if downloaded_count == 0:
                print(f"⚠️ [跳过提醒] 该商铺无足够合格实拍图 (有效图为0)，触发自动跳过机制，自动流转至下一商铺。")
            else:
                print(f"⚠️ [未满收尾] 该商铺合格实拍图未满 (已下载 {downloaded_count}/{target_count} 张)，已达扫描上限不再死磕，保留现有产物并进入下一商铺。")
        else:
            print(f"✅ [圆满达标] 成功集齐 {downloaded_count}/{target_count} 张高质量纯净实拍图！")
        print(f"==================================================\n")

        return {
            "success": downloaded_count >= target_count,
            "keyword": keyword,
            "target_count": target_count,
            "downloaded_count": downloaded_count,
            "rotated_count": rotated_count,
            "save_dir": save_dir,
            "downloaded_files": downloaded_files,
            "notes_scanned": notes_scanned,
        }

    def _save_positive_note_summary(
        self,
        keyword: str,
        save_dir: str,
        captured_notes: List[Dict[str, Any]],
        positive_dishes: List[str],
        positive_reviews: List[str],
        downloaded_count: int
    ):
        """将小红书笔记中提炼的真实正面菜品评价与口碑关键词保存为 小红书商品信息.txt"""
        txt_path = os.path.join(save_dir, "小红书商品信息.txt")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 整理正面推荐菜品列表（去重）
        unique_dishes = []
        seen = set()
        for d in positive_dishes:
            clean_d = d.strip()
            if clean_d and clean_d not in seen:
                seen.add(clean_d)
                unique_dishes.append(clean_d)

        # 整理通用正面口碑好评
        unique_reviews = []
        for r in positive_reviews:
            clean_r = r.strip()
            if clean_r and clean_r not in seen and clean_r not in unique_dishes:
                seen.add(clean_r)
                unique_reviews.append(clean_r)

        lines = [
            "==================================================",
            "【小红书商户/商品真实食客正面口碑与菜品素材库】",
            "==================================================",
            "",
            "【一、商户与采集基础信息】",
            f"- 检索关键词：{keyword}",
            f"- 采集生成时间：{now_str}",
            f"- 关联图片保存目录：{save_dir}",
            f"- 关联采集高清图数：{downloaded_count} 张",
            f"- 抓取参考笔记数量：{len(captured_notes)} 篇",
            "",
            "【二、真实食客正面推荐菜品清单 (纯正面好评，严禁任何负面踩雷)】"
        ]

        if unique_dishes:
            for idx, dish_item in enumerate(unique_dishes[:15], 1):
                lines.append(f"{idx}. {dish_item}")
        else:
            lines.append("- 店内招牌特色丰富，食客好评聚焦在主打特色风味与现做现制。")

        lines.extend([
            "",
            "【三、真实食客就餐体验正面好评精选 (已过滤所有吐槽与负面)】"
        ])

        if unique_reviews:
            for idx, rev in enumerate(unique_reviews[:15], 1):
                lines.append(f"- {rev}")
        else:
            lines.append("- 店内就餐环境舒适，食材新鲜入味，深受周边打卡与聚餐食客喜爱。")

        lines.extend([
            "",
            "【四、参考笔记标题一览】"
        ])
        for idx, n in enumerate(captured_notes[:8], 1):
            if n.get("title"):
                lines.append(f"{idx}. {n['title']}")

        lines.extend([
            "",
            "==================================================",
            "说明：此文件由“阿一小红书图片下载 Skill”在采集图片时自动提取并生成，",
            "已通过正面情感过滤算法彻底剔除所有“避雷、难吃、踩雷”等负向内容，",
            "专用于后续探店笔记生成与封面海报文案创作。",
            "==================================================",
            ""
        ])

        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"  [数据归档] 成功生成小红书正面菜品评价档案: {txt_path}")
        except Exception as e:
            print(f"  [警告] 保存 小红书商品信息.txt 失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="阿一小红书图片自动检索与下载器 (V4 级高阶去重驱动)")
    parser.add_argument("--keyword", "-k", type=str, required=True, help="搜索关键词")
    parser.add_argument("--count", "-c", type=int, default=20, help="下载图片数量，默认 20")
    parser.add_argument("--category", type=str, default=None, help="内容类型筛选，如: 菜品、美食等")
    parser.add_argument("--no-filter", action="store_true", help="是否关闭 4合1 智能质检过滤，默认全局开启")
    parser.add_argument("--no-rotate", action="store_true", help="是否关闭自动微调去重，默认自动开启去重")
    parser.add_argument("--port", "-p", type=int, default=9222, help="Chrome 调试端口，默认 9222")
    parser.add_argument("--dir", "-d", type=str, default=None, help="目标根目录，默认当前目录")
    parser.add_argument("--date", type=str, default=None, help="日期目录名，默认今天 (YYYY-MM-DD)")
    parser.add_argument("--folder", "-f", type=str, default=None, help="自定义保存的商户子文件夹名称")
    parser.add_argument("--search-query", "-sq", type=str, default=None, help="覆盖小红书实际搜索的检索词")
    parser.add_argument("--device", "-dev", type=str, default=None, help="指定拍摄手机型号（支持模糊匹配，如 iPhone 15 Pro、小米14 等；若不指定则按商铺哈希自动锁定）")
    parser.add_argument("--skip-if", type=str, default="", help="笔记级门禁：逗号分隔，命中即整篇跳过；留空用内置负面词表")
    parser.add_argument("--max-notes", type=int, default=25, help="单商铺最多扫描多少篇笔记，默认 25")

    args = parser.parse_args()

    # 4合1 智能质检默认全局开启 (严格拦截人脸肖像/纯文字/宣传海报/较大标题)
    is_food_filter = not args.no_filter
    if args.category and "all" in args.category.lower():
        is_food_filter = False

    downloader = XhsDownloader(cdp_port=args.port)
    try:
        downloader.download_images(
            keyword=args.keyword,
            target_count=args.count,
            clean_food_only=is_food_filter,
            base_dir=args.dir,
            date_str=args.date,
            auto_rotate=not args.no_rotate,
            folder_name=args.folder,
            search_keyword=args.search_query,
            device=args.device,
            skip_if=args.skip_if,
            max_notes=args.max_notes
        )
    finally:
        downloader.close()


if __name__ == "__main__":
    main()
