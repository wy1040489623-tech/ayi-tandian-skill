---
name: ayi-image-dedup-v4
description: 阿一图像智能高阶去重 Skill V4。用于对单张图片或指定图片文件夹执行全套工业级图像去重与真实旗舰手机硬件级 EXIF 注入，阻断机器视觉查重检测，保护探店笔记原创度。
---

# 阿一图像智能高阶去重 Skill (V4 独立版)

本 Skill 是从探店笔记流水线中独立出的专用图像去重引擎，专门用于对**单张图片**或**指定文件夹内的全部图片**进行高强度去重处理。在不破坏人类视觉观感的前提下，全面瓦解平台机器视觉（感知哈希、特征指纹、直方图对比）查重算法，并注入 23 款主流旗舰手机的真实硬件拍摄元数据。

---

## 核心去重五层防御矩阵

1. **几何形态无损微扰动**：
   - 随机 0.3° ~ 1.2° 微旋转微倾斜，自适应裁剪黑色外边缘，彻底改变图片像素矩阵坐标系。
2. **全局动态网格遮罩 (2% 极低透明度)**：
   - 采用 `lines.png` 网格纹理 100% 贴合全图覆盖，透明度精确控制在 2%，打乱深度卷积神经网络特征图抽取。
3. **商铺主题角落隐形矢量 Icon 扰动 (1%~3% 随机透明度)**：
   - 自动识别或根据商铺名称匹配餐饮分类，从 20+ 款线条 Icon 中随机抽取 1~2 个，缩放至 8~16 像素，随机注入图片四个角落之一。
4. **底层色彩通道微量抖动**：
   - 对 RGB 像素通道进行 ±1~2% 微弱随机微调，破坏感知哈希（pHash / dHash）比对。
5. **真实旗舰手机 EXIF 硬件级参数伪装**：
   - 支持指定拍摄手机型号（支持 23 款主流旗舰中英文模糊匹配），若未指定则以商铺名称 Hash 锁定单一机型，杜绝同商铺内机型混杂的异常情况。
   - 自动生成机型专属镜头参数、光圈、ISO、快门速度、生成时间戳与软件构建版本号。

---

## 命令行调用说明

脚本路径：
`image_dedup_processor_v4.py`

### 1. 单张图片去重

```bash
# 语法
python image_dedup_processor_v4.py --image "<源图片路径>" --output "<目标图片路径>" [--device "<手机型号>"] [--store "<商铺名称>"]

# 示例：指定使用 iPhone 15 Pro Max 拍摄去重
python image_dedup_processor_v4.py --image "D:/photos/food.jpg" --output "D:/photos/food_clean.jpg" --device "iPhone 15 Pro Max"
```

### 2. 文件夹批量去重

```bash
# 语法：处理文件夹下所有 .jpg, .jpeg, .png, .webp 图片
python image_dedup_processor_v4.py --folder "<目标图片文件夹>" [--store "<商铺名称>"] [--device "<手机型号>"] [--output "<输出目录>"]

# 示例 1：指定商铺名称（自动锁定机型与匹配美食 Icon），输出到指定文件夹
python image_dedup_processor_v4.py --folder "D:/photos/shop1" --store "喜茶(万象城店)" --output "D:/photos/shop1_dedup"

# 示例 2：指定使用 小米14 Ultra 进行批量去重
python image_dedup_processor_v4.py --folder "D:/photos/shop1" --device "小米14 Ultra" --output "D:/photos/shop1_dedup"

# 示例 3：原地覆盖（不传 --output 则默认在原目录生成带有 _dedup 后缀的文件，若传入 --in-place 则直接覆盖原图）
python image_dedup_processor_v4.py --folder "D:/photos/shop1" --in-place
```

---

## 参数字典

| 参数名 | 简写 | 说明 |
| :--- | :--- | :--- |
| `--image` | `-i` | 单张源图片完整路径 |
| `--output` | `-o` | 输出图片文件路径（单图模式）或输出目录（批量模式） |
| `--folder` | `-f` | 待批量去重的图片文件夹路径 |
| `--device` | `-dev` | **【核心新特性】** 指定拍摄手机型号（模糊匹配，详见 `支持手机列表.txt`） |
| `--store` | `-s` | 商铺名称，用于主题 Icon 智能匹配及未指定手机时的机型哈希锁定 |
| `--in-place` | - | 文件夹批量模式下直接覆盖原图（慎用） |

---

## 支持拍摄手机型号速查 (23款主流旗舰)

用户可通过参数 `--device` 或 `-dev` 传入任意机型别名，系统支持中文、英文、大小写、简写模糊匹配：

- **苹果 Apple 系列**：
  - `iPhone 15 Pro Max` (别名: 15promax, 苹果15promax)
  - `iPhone 15 Pro` (别名: 15pro, 苹果15pro)
  - `iPhone 15` (别名: 15, 苹果15)
  - `iPhone 14 Pro Max` (别名: 14promax)
  - `iPhone 13 Pro` (别名: 13pro)
- **小米 Xiaomi 系列**：
  - `Xiaomi 14 Ultra` (别名: 小米14ultra, 14ultra)
  - `Xiaomi 14 Pro` (别名: 小米14pro, 14pro)
  - `Xiaomi 14` (别名: 小米14)
  - `Xiaomi 13 Ultra` (别名: 小米13ultra)
- **华为 HUAWEI 系列**：
  - `HUAWEI Mate 60 Pro+` (别名: mate60pro+, 华为mate60pro+)
  - `HUAWEI Mate 60 Pro` (别名: mate60pro, 华为mate60pro)
  - `HUAWEI Pura 70 Ultra` (别名: pura70ultra)
  - `HUAWEI Pura 70 Pro` (别名: pura70pro)
- **vivo 系列**：
  - `vivo X100 Ultra` (别名: x100ultra)
  - `vivo X100 Pro` (别名: x100pro)
  - `vivo X90 Pro+` (别名: x90pro+)
- **OPPO 系列**：
  - `OPPO Find X7 Ultra` (别名: findx7ultra)
  - `OPPO Find X6 Pro` (别名: findx6pro)
- **荣耀 HONOR 系列**：
  - `HONOR Magic6 Pro` (别名: magic6pro, 荣耀magic6pro)
  - `HONOR Magic5 Pro` (别名: magic5pro)

完整参数清单请参阅同目录下的 [`支持手机列表.txt`](支持手机列表.txt)。
