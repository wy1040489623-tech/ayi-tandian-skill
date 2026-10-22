"""
探店笔记 V4 级多图智能无缝拼接与九宫格封面生成器 (food_collage_generator_v4.py)

核心特性升级：
1. 多样化拼图版式矩阵：
   - 2 拼图：严格采用【上下两拼】(split_tb，上方占 50% 高度，下方占 50% 高度)
   - 3 拼图：重点强化【上一下二】(top1_bottom2，上方 100% 宽幅，下方左右各 50%) 与【上二下一】(top2_bottom1)
   - 4 拼图：经典 2x2 田字四格无缝满铺 (grid_4，各占 25%)
   - 均衡多元配比：2 拼、3 拼、4 拼图全面混搭，消除呆板单一感。
2. 拼图数量在原基础上翻倍 (2x)：
   - 采用智能多轮组合机制 (默认 rounds=2)，使有限素材通过错位重排生成更多高质量、无重复画面的拼图海报。
3. 封面规范：
   - 精确生成 1 张 3x3 九宫格无缝满铺图作为专属封面 (mix9_[商铺名].jpg)。
"""

import os
import sys
import re
import random
from typing import List, Tuple
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')


def crop_to_fill(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """保持比例居中裁剪填充指定宽高"""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        offset = (src_w - new_w) // 2
        img = img.crop((offset, 0, offset + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        offset = (src_h - new_h) // 2
        img = img.crop((0, offset, src_w, offset + new_h))
    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


def split_images_into_balanced_groups(images: List[str]) -> List[Tuple[str, List[str]]]:
    """
    V4 均衡分组算法：
    均衡生成 2 拼（上下）、3 拼（上一下二为主）、4 拼（田字），
    权重分布：2 拼图约 35%、3 拼图约 35%、4 拼图约 30%，杜绝清一色 4 拼。
    """
    n = len(images)
    if n == 0:
        return []

    group_sizes = []
    rem = n

    while rem > 0:
        if rem >= 7:
            # 随机权重选择 2, 3 或 4 拼
            r = random.random()
            if r < 0.35:
                choice = 2
            elif r < 0.70:
                choice = 3
            else:
                choice = 4

            # 防呆：如果剩余减去 choice 为 1，则微调以防落单
            if rem - choice == 1:
                choice = 3 if choice == 2 else 2

            group_sizes.append(choice)
            rem -= choice
        elif rem == 6:
            # 可选 3+3, 4+2, 2+2+2
            r = random.random()
            if r < 0.4:
                group_sizes.extend([3, 3])
            elif r < 0.7:
                group_sizes.extend([4, 2])
            else:
                group_sizes.extend([2, 2, 2])
            rem = 0
        elif rem == 5:
            # 3+2
            group_sizes.extend([3, 2] if random.random() < 0.5 else [2, 3])
            rem = 0
        elif rem == 4:
            # 4 拼 或 2+2
            if random.random() < 0.6:
                group_sizes.append(4)
            else:
                group_sizes.extend([2, 2])
            rem = 0
        elif rem in [3, 2]:
            group_sizes.append(rem)
            rem = 0
        elif rem == 1:
            # 消除单张：从前面的组借 1 张凑成 2 拼
            if 4 in group_sizes:
                idx = group_sizes.index(4)
                group_sizes[idx] = 3
                group_sizes.append(2)
            elif 3 in group_sizes:
                idx = group_sizes.index(3)
                group_sizes[idx] = 2
                group_sizes.append(2)
            else:
                group_sizes.append(1)
            rem = 0

    groups = []
    cursor = 0
    three_toggle = 0

    for sz in group_sizes:
        sub_imgs = images[cursor:cursor + sz]
        cursor += sz

        if sz == 4:
            layout = 'grid_4'
        elif sz == 3:
            # 70% 概率采用用户特别强调的【上一下二】，30% 采用【上二下一】
            if random.random() < 0.7:
                layout = 'top1_bottom2'
            else:
                layout = 'top2_bottom1'
        elif sz == 2:
            # 严格采用用户指定的【上下两拼】
            layout = 'split_tb'
        else:
            layout = 'single'

        groups.append((layout, sub_imgs))

    return groups


def render_seamless_collage(layout: str, img_paths: List[str], canvas_w=1080, canvas_h=1440) -> Image.Image:
    """
    渲染完全无缝、零白边、零空隙的拼图海报 (1080x1440)
    支持：
    1. grid_4: 4 格田字无缝满铺
    2. top1_bottom2: 3 格上一下二（上面 1 张全宽占 50% 高，下面左右各占 50% 宽 50% 高）
    3. top2_bottom1: 3 格上二下一（上面左右各占 50% 宽 50% 高，下面 1 张全宽占 50% 高）
    4. split_tb: 2 格上下拼（上宽幅 50% 高，下宽幅 50% 高）
    """
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    loaded_imgs = []
    for p in img_paths:
        try:
            im = Image.open(p)
            if im.mode != "RGB":
                im = im.convert("RGB")
            loaded_imgs.append(im)
        except Exception as e:
            print(f"  [跳过损坏图片] {p}: {e}")

    if not loaded_imgs:
        return canvas

    if layout == 'grid_4' and len(loaded_imgs) >= 4:
        w1 = canvas_w // 2
        w2 = canvas_w - w1
        h1 = canvas_h // 2
        h2 = canvas_h - h1

        # 左上
        c0 = crop_to_fill(loaded_imgs[0], w1, h1)
        canvas.paste(c0, (0, 0))
        # 右上
        c1 = crop_to_fill(loaded_imgs[1], w2, h1)
        canvas.paste(c1, (w1, 0))
        # 左下
        c2 = crop_to_fill(loaded_imgs[2], w1, h2)
        canvas.paste(c2, (0, h1))
        # 右下
        c3 = crop_to_fill(loaded_imgs[3], w2, h2)
        canvas.paste(c3, (w1, h1))

    elif layout == 'top1_bottom2' and len(loaded_imgs) >= 3:
        # 上一下二：上面一个、下面左右各一个
        top_h = canvas_h // 2
        bot_h = canvas_h - top_h
        bot_w1 = canvas_w // 2
        bot_w2 = canvas_w - bot_w1

        # 上方单张全宽
        c0 = crop_to_fill(loaded_imgs[0], canvas_w, top_h)
        canvas.paste(c0, (0, 0))
        # 下方左侧
        c1 = crop_to_fill(loaded_imgs[1], bot_w1, bot_h)
        canvas.paste(c1, (0, top_h))
        # 下方右侧
        c2 = crop_to_fill(loaded_imgs[2], bot_w2, bot_h)
        canvas.paste(c2, (bot_w1, top_h))

    elif layout == 'top2_bottom1' and len(loaded_imgs) >= 3:
        # 上二下一：上面左右各一个、下面一个全宽
        top_h = canvas_h // 2
        bot_h = canvas_h - top_h
        top_w1 = canvas_w // 2
        top_w2 = canvas_w - top_w1

        # 上方左侧
        c0 = crop_to_fill(loaded_imgs[0], top_w1, top_h)
        canvas.paste(c0, (0, 0))
        # 上方右侧
        c1 = crop_to_fill(loaded_imgs[1], top_w2, top_h)
        canvas.paste(c1, (top_w1, 0))
        # 下方单张全宽
        c2 = crop_to_fill(loaded_imgs[2], canvas_w, bot_h)
        canvas.paste(c2, (0, top_h))

    elif layout == 'split_tb' and len(loaded_imgs) >= 2:
        # 2 格严格上下拼图
        h1 = canvas_h // 2
        h2 = canvas_h - h1

        # 上半张
        c0 = crop_to_fill(loaded_imgs[0], canvas_w, h1)
        canvas.paste(c0, (0, 0))
        # 下半张
        c1 = crop_to_fill(loaded_imgs[1], canvas_w, h2)
        canvas.paste(c1, (0, h1))

    elif len(loaded_imgs) == 1:
        c0 = crop_to_fill(loaded_imgs[0], canvas_w, canvas_h)
        canvas.paste(c0, (0, 0))

    for im in loaded_imgs:
        try:
            im.close()
        except Exception:
            pass

    return canvas


def create_nine_grid_cover(images: List[str], output_path: str, canvas_w=1080, canvas_h=1440) -> str:
    """
    用 9 张精选菜品图片生成 1 张 3x3 九宫格满铺封面 (作为正式封面)：
    - 绝无缝隙、绝无白边、四周完全满铺
    - 九宫格素材允许在其他拼图中复用
    """
    if len(images) < 9:
        print(f"  [提示] 图片不足 9 张 (仅有 {len(images)} 张)，自动循环补齐以生成 9 宫格封面。")
        extended = []
        while len(extended) < 9:
            extended.extend(images)
        selected_imgs = extended[:9]
    else:
        selected_imgs = images[:9]

    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))

    col_widths = [canvas_w // 3, canvas_w // 3, canvas_w - (canvas_w // 3) * 2]
    row_heights = [canvas_h // 3, canvas_h // 3, canvas_h - (canvas_h // 3) * 2]

    col_x = [0, col_widths[0], col_widths[0] + col_widths[1]]
    row_y = [0, row_heights[0], row_heights[0] + row_heights[1]]

    idx = 0
    for r in range(3):
        for c in range(3):
            img_path = selected_imgs[idx]
            idx += 1
            w = col_widths[c]
            h = row_heights[r]
            x = col_x[c]
            y = row_y[r]

            with Image.open(img_path) as im:
                if im.mode != "RGB":
                    im = im.convert("RGB")
                cropped = crop_to_fill(im, w, h)
                canvas.paste(cropped, (x, y))

    canvas.save(output_path, format="JPEG", quality=95)
    print(f"[成功输出] 9宫格专属封面: {os.path.basename(output_path)}")
    return output_path


def is_valid_material_image(filename: str) -> bool:
    """筛选实拍素材图片，排除已生成的各类拼图与封面"""
    f_lower = filename.lower()
    if not f_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return False
    if filename.startswith("mix_") or filename.startswith("mix9_") or "封面" in filename or "cover" in f_lower:
        return False
    return True


def get_image_sort_key(filename: str) -> Tuple[int, str]:
    """自然数字排序键"""
    name_without_ext, _ = os.path.splitext(filename)
    match = re.search(r'_(\d+)$', name_without_ext)
    if match:
        return (int(match.group(1)), filename)
    return (999999, filename)


def generate_collages_v4(
    target_dir: str,
    candidate_files: List[str],
    dir_name: str,
    note_idx: int = 1,
    rounds: int = 2
) -> Tuple[str, List[str]]:
    """
    V4 核心拼图生成函数：
    1. 生成 1 张精美九宫格封面 (mix9_[商铺名].jpg)
    2. 执行多轮错位组合 (默认 rounds=2，拼图总数量翻倍)
    3. 全面覆盖 2 拼（上下）、3 拼（上一下二为主）、4 拼（田字）
    """
    n = len(candidate_files)
    if n == 0:
        return "", []

    # 1. 生成 1 张专属 9 宫格封面
    nine_imgs = []
    if n >= 9:
        shift = (note_idx - 1) * 3
        for i in range(9):
            nine_imgs.append(candidate_files[(i + shift) % n])
    else:
        nine_imgs = candidate_files

    nine_grid_cover_name = f"mix9_{dir_name}.jpg"
    nine_grid_cover_path = os.path.join(target_dir, nine_grid_cover_name)
    cover_res = create_nine_grid_cover(nine_imgs, nine_grid_cover_path)

    # 2. 多轮拼图生成（拼图数量翻倍机制）
    layout_name_map = {
        'grid_4': '4格田字无缝拼',
        'top1_bottom2': '3格上一下二无缝拼',
        'top2_bottom1': '3格上二下一无缝拼',
        'split_tb': '2格上下无缝拼',
        'single': '单张满铺'
    }

    mix_output_files = []
    total_task_idx = 0

    print(f"\n[V4 拼图规划 - 笔记 {note_idx}] 启动 {rounds} 轮错位重组（目标产出数量翻倍）：")

    for round_num in range(1, rounds + 1):
        # 错位洗牌排列，确保每轮拼图由不同图片组合搭配
        if round_num == 1:
            # 基础排列
            perm = list(range(n))
        else:
            # 奇偶交错或步长洗牌
            evens = [i for i in range(0, n, 2)]
            odds = [i for i in range(1, n, 2)]
            perm = (odds + evens) if round_num % 2 == 0 else list(reversed(range(n)))

        ordered_files = [candidate_files[i] for i in perm]
        groups = split_images_into_balanced_groups(ordered_files)

        print(f"  --- 第 {round_num}/{rounds} 轮组合 (共 {len(groups)} 组多样化拼图) ---")
        for g_idx, (layout, img_list) in enumerate(groups, 1):
            total_task_idx += 1
            collage_img = render_seamless_collage(layout, img_list, canvas_w=1080, canvas_h=1440)
            out_filename = f"mix_{dir_name}_{total_task_idx}.jpg"
            out_path = os.path.join(target_dir, out_filename)
            collage_img.save(out_path, format="JPEG", quality=95)
            mix_output_files.append(out_path)

            desc = layout_name_map.get(layout, layout)
            print(f"    [{total_task_idx}] ✅ {out_filename} -> {desc} ({len(img_list)}图)")

    return cover_res, mix_output_files


def process_folder_collages(
    store_dir: str,
    note_count: int = 1,
    rounds: int = 2
) -> Tuple[List[str], List[str]]:
    """
    对指定商户目录执行 V4 无缝拼图流水线：
    - 优先选用 P_ 开头的高阶去重实拍素材
    - 支持 rounds=2 拼图总数翻倍
    - 支持 2 拼（上下）、3 拼（上一下二/上二下一）、4 拼多元混搭
    - 精准生成 1 张九宫格封面
    """
    if not os.path.exists(store_dir):
        print(f"[错误] 目录不存在: {store_dir}")
        return [], []

    dir_name = os.path.basename(os.path.normpath(store_dir))
    all_files = os.listdir(store_dir)

    # 1. 优先筛选 P_ 开头的 V4 去重实拍素材
    p_files = [f for f in all_files if f.startswith("P_") and is_valid_material_image(f)]
    p_numbered = [f for f in p_files if re.search(r'_\d+$', os.path.splitext(f)[0])]
    selected_p = p_numbered if p_numbered else p_files

    if selected_p:
        selected_p.sort(key=get_image_sort_key)
        candidate_files = [os.path.join(store_dir, f) for f in selected_p]
        src_desc = f"P_ 高阶去重图 ({len(candidate_files)} 张)"
    else:
        # 2. 若没有 P_ 图片，从原图实拍中筛选
        raw_files = [f for f in all_files if is_valid_material_image(f)]
        raw_numbered = [f for f in raw_files if re.search(r'_\d+$', os.path.splitext(f)[0])]
        selected_raw = raw_numbered if raw_numbered else raw_files
        selected_raw.sort(key=get_image_sort_key)
        candidate_files = [os.path.join(store_dir, f) for f in selected_raw]
        src_desc = f"原始实拍素材 ({len(candidate_files)} 张)"

    print(f"\n==================================================")
    print(f"🚀 启动 V4 级多图智能无缝拼图流水线")
    print(f"目标商铺: {dir_name}")
    print(f"素材来源: {src_desc}")
    print(f"拼图类型: 2拼(上下) + 3拼(上一下二为主) + 4拼(田字) 多元均衡混搭")
    print(f"拼图数量: 启动 {rounds} 轮错位重组（数量翻倍）")
    print(f"封面配置: 1 张 3x3 九宫格满铺封面")
    print(f"==================================================")

    if not candidate_files:
        print("[提示] 目录下无可用的美食实拍素材。")
        return [], []

    all_covers = []
    all_mixes = []

    if note_count <= 1:
        cover_res, mix_files = generate_collages_v4(
            target_dir=store_dir,
            candidate_files=candidate_files,
            dir_name=dir_name,
            note_idx=1,
            rounds=rounds
        )
        if cover_res:
            all_covers.append(cover_res)
        all_mixes.extend(mix_files)
    else:
        for k in range(1, note_count + 1):
            sub_note_dir = os.path.join(store_dir, f"笔记 {k}")
            os.makedirs(sub_note_dir, exist_ok=True)
            print(f"\n>>> 正在生成 [笔记 {k}] 专属拼图与九宫格封面...")
            cover_res, mix_files = generate_collages_v4(
                target_dir=sub_note_dir,
                candidate_files=candidate_files,
                dir_name=dir_name,
                note_idx=k,
                rounds=rounds
            )
            if cover_res:
                all_covers.append(cover_res)
            all_mixes.extend(mix_files)

    return all_covers, all_mixes


def main():
    import argparse
    parser = argparse.ArgumentParser(description="阿一美食图片智能无缝拼接处理器 V4 (2拼/3拼/4拼均衡混搭/数量翻倍/九宫格封面)")
    parser.add_argument("--folder", "-f", type=str, default="", help="目标商铺图片文件夹绝对路径")
    parser.add_argument("--batch_dir", "-b", type=str, default="", help="包含多个商铺文件夹的父目录绝对路径")
    parser.add_argument("--note_count", "-n", type=int, default=1, help="生成笔记套数 (默认1份)")
    parser.add_argument("--rounds", "-r", type=int, default=2, help="拼图重组轮数，默认2轮（在原有数量基础上翻倍）")

    args = parser.parse_args()

    if args.batch_dir:
        parent = args.batch_dir
        if not os.path.exists(parent):
            print(f"[错误] 目录不存在: {parent}")
            return
        subdirs = [os.path.join(parent, d) for d in sorted(os.listdir(parent)) if os.path.isdir(os.path.join(parent, d))]
        print(f"检测到 {len(subdirs)} 个待处理商铺子文件夹...")
        total_covers = 0
        total_mixes = 0
        for idx, sdir in enumerate(subdirs, 1):
            print(f"\n>>> 正在批量处理 [{idx}/{len(subdirs)}]: {os.path.basename(sdir)}")
            c, m = process_folder_collages(sdir, note_count=args.note_count, rounds=args.rounds)
            total_covers += len(c)
            total_mixes += len(m)
        print(f"\n==========================================")
        print(f"V4 批量拼图生成完毕！共处理 {len(subdirs)} 个商铺：")
        print(f"- 九宫格专属封面: {total_covers} 张")
        print(f"- 多元无缝拼图海报: {total_mixes} 张")
        print(f"==========================================")
    elif args.folder:
        covers, mix_list = process_folder_collages(args.folder, note_count=args.note_count, rounds=args.rounds)
        print(f"\n==========================================")
        print(f"V4 拼图生成圆满完成！")
        print(f"九宫格封面: {len(covers)} 张 (mix9_ 开头)")
        print(f"多元无缝拼图: {len(mix_list)} 张 (mix_ 开头，数量已翻倍)")
        print(f"==========================================")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
