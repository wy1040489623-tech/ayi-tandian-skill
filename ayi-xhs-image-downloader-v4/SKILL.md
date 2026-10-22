---
name: ayi-xhs-image-downloader-v4
description: Use when downloading images, photos, or food materials from Xiaohongshu (小红书) based on search keywords or store names, with V4 Advanced Anti-Duplication Pipeline (geometric rotation, dynamic lines mask, stealth corner icon, color jitter, and unified camera EXIF injection) while extracting positive-only dish reviews and store info to 小红书商品信息.txt.
---

# 阿一小红书图片下载与高阶去重 Skill (V4 旗舰版)

## 概述
本 Skill 为小红书高清素材采集与去重流水线的 **V4 旗舰升级版本**。在全面继承 Chrome CDP 原生鉴权免封禁下载、纯正面口碑提取能力的基础上，**重构升级了全自动五重去重引擎**，并建立全新的**“8合1 高阶纯净实拍智能质检网关”**：
1. **源头 DOM 隔离 + 尺寸门禁**：仅从正文媒体轮播区提取图片，彻底排除博主与评论区头像；设置尺寸门禁（过滤宽或高 < 380px 的头像小图）；
2. **卡通/插画/二次元低纹理拦截**：基于色彩平坦度、边缘线稿与自然噪点特征识别手绘/卡通/动漫图片，坚决拦截非实拍素材；
3. **纯文字卡片/备忘录卡片拦截**：大面积纯色/白底背景占比 > 65% 且包含文字立即拦截；
4. **额外产生文字/花字贴纸拦截**：凡单行文字宽度占比 >= 30% 或高度占比 >= 4.5%（覆盖中下部菜品主体）均视为后期博主贴纸坚决拦截，仅放行顶部 <= 25% 区域的自然远景门头招牌；
5. **多行文字/菜单截图/手机截屏拦截**：整图文字 >= 15 字或行数 >= 4 坚决拦截；
6. **人脸/肖像出现拦截** (YOLOv8 深度目标检测)；
7. **超长长图/海报比例拦截** (ratio > 2.2)；
8. **平台账号水印拦截**。

---

## 🚀 V4 核心升级特性 (五重去重防御矩阵)

1. **第一重：几何微形变**
   - 随机向左或向右微倾斜 2.0° ~ 12.0°；
   - 自动执行最大内切矩形无黑边裁剪，原图画面保留率高达 85%~95% 以上。

2. **第二重：动态微缩放与微位移网格遮罩**
   - 加载 `ayi_img/lines.png` 网格底图；
   - 绝非死板 1:1 拉伸，而是随机进行 102%~106% 微缩放与随机偏移位移（Offset），避免多图产生相同网格特征；
   - 以 **2% 极低透明度（Alpha ≈ 5/255）** 进行全图 Alpha 复合，肉眼毫无网格痕迹，但彻底改变了整张图片每一个像素的高频 DCT 频域特征。

3. **第三重：角落隐形品类图元注入**
   - 读取 `ayi_img/ico/` 餐饮线条图标库；
   - 内置智能品类路由算法，根据商铺名称与业态（火锅、烧烤、中餐、日料、西餐、咖啡奶茶、甜品等）自动挑选匹配的 1~2 个专属 Icon；
   - 将 Icon 随机微缩至 **12 ~ 24 像素**，透明度设为 **1.5% ~ 3.0%** 之间的微弱随机值；
   - 随机放置在图片的 1~2 个角落（距边缘 5%~12% 安全边距，避开中心区域），注入不可察觉的局部特征指纹。

4. **第四重：微观色彩空间微抖动**
   - 对图片的亮度（±1.5%）、对比度（±2%）、饱和度（±2%）进行随机微抖动，重构色彩直方图，使菜品呈现更鲜亮自然的诱人质感。

5. **第五重：商铺级设备指纹锁定与连贯实拍 EXIF 注入**
   - **单店设备锁定机制**：整家商铺或同一批次的所有图片，**严格统一绑定同一款主流旗舰手机**（如 Apple iPhone 15 Pro 或 Xiaomi 14），杜绝“同一家店出现不同机型”的虚假破绽；
   - **时间流连续递增**：所有相片拍摄时间戳统一设定在真实就餐时段，每道菜按序号递增 25~60 秒，完美模拟食客现场一道道拍照的连贯行为。

---

## 触发场景 (When to Use)
当用户提出以下需求时激活此 Skill：
- “使用 V4 下载 [商户名] 的图片并执行高阶去重”
- “采集 [商户名] 的小红书素材，开启 V4 算法去重”
- “帮我下载并做带网格和隐形水印的 V4 深度去重图片”
- “调用 ayi-xhs-image-downloader-v4”

---

## 核心输入参数规范

| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| **`keyword`** | string | (必填) | 搜索关键词（商户名、菜品名，如 `东盛炭烤自助料理`） |
| **`count`** | int | **20** | 目标下载图片数量。若未指定，默认 20 张 |
| **`device`** | string | **None** (自动哈希)| **[新增]** 指定拍摄手机型号（支持模糊匹配，如 `iPhone 15 Pro`、`小米14`、`Mate 60 Pro` 等；详见同目录 [`支持手机列表.txt`](file:///E:/%E6%88%91%E7%9A%84%E9%A1%B9%E7%9B%AE/%E5%A4%A7%E4%BC%97%E7%82%B9%E8%AF%84%E9%A1%B9%E7%9B%AE/.gemini/skills/ayi_tandian_skill_v4/ayi-xhs-image-downloader-v4/%E6%94%AF%E6%8C%81%E6%89%8B%E6%9C%BA%E5%88%97%E8%A1%A8.txt)；若不指定则按商铺名称自动哈希锁定） |
| **`no_filter`** | bool | **False** (默认开启)| 4合1 图像智能质检网关（过滤人像/纯字截屏/海报/大字贴纸） |
| **`no_rotate`** | bool | **False** (默认开启)| 是否关闭 V4 去重流水线。默认开启，生成 `P_` 前缀高阶去重图 |

---

## 执行流程与调用指南

Agent 在执行此 Skill 时，运行配套的 V4 专用驱动脚本（无论是项目根目录下运行还是独立环境均可自适应执行）：

### 1. 标准调用命令 (默认 20 张，商铺自动哈希绑定同款手机)
```bash
python xhs_downloader_v4.py --keyword "<关键词/商户名>"
```
*注：若作为独立包运行，亦可直接执行当前目录脚本：*
```bash
python .gemini/skills/ayi_tandian_skill_v4/ayi-xhs-image-downloader-v4/xhs_downloader_v4.py --keyword "<关键词/商户名>"
```

### 2. 指定拍摄手机型号 (例如指定小米14或iPhone 15 Pro)
```bash
# 指定小米 14
python xhs_downloader_v4.py --keyword "聚宝源火锅" --count 20 --device "小米14"

# 指定 iPhone 15 Pro
python xhs_downloader_v4.py --keyword "东盛炭烤自助料理" --count 20 --device "iPhone 15 Pro"
```
> [!TIP]
> 支持模糊输入与中英文别名，如 `苹果15`、`15promax`、`小米14ultra`、`华为mate60pro`、`vivo x100` 等。完整机型请随时查看 [`支持手机列表.txt`](file:///E:/%E6%88%91%E7%9A%84%E9%A1%B9%E7%9B%AE/%E5%A4%A7%E4%BC%97%E7%82%B9%E8%AF%84%E9%A1%B9%E7%9B%AE/.gemini/skills/ayi_tandian_skill_v4/ayi-xhs-image-downloader-v4/%E6%94%AF%E6%8C%81%E6%89%8B%E6%9C%BA%E5%88%97%E8%A1%A8.txt)。

### 3. 指定下载数量与自定义商铺文件夹
```bash
python xhs_downloader_v4.py --keyword "<关键词>" --count 15 --folder "<自定义商户文件夹名>" --device "华为mate60pro"
```

### 4. 单独对已有文件夹执行 V4 批量去重 (无需重复下载，支持指定机型)
```bash
python image_dedup_processor_v4.py --folder "<目标图片文件夹绝对路径>" --store "<商铺名称>" --device "<手机机型>"
```

---

## 文件存储与产物归档规范

1. **存储路径**：
   `[项目根目录]/[YYYY-MM-DD]/[商铺名称]/`
   例如：`2026-10-15/东盛炭烤自助料理(长泰广场店)/`

2. **产物清单与文件命名规则**：
   - **原图素材**：`[商户名]_[序号].jpg`（从小红书采集的原始实拍图）
   - **V4 深度去重图**：**`P_[商户名]_[序号].jpg`**（向下完美兼容所有后续拼接与封面 Skill）
   - **真实食客正面口碑档案**：**`小红书商品信息.txt`**（提炼纯正面好评与招牌菜推荐）

3. **向下游协同无缝兼容**：
   - 输出的 `P_` 命名与原版完全保持一致，后续调用 `ayi-image-collage`（多图拼接）或 `ayi-store-note-cover-generator` 时无需做任何路径改动，直接无缝读取最新 V4 去重成果！
