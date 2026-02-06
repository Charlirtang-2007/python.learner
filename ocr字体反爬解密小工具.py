"""字体识别小工具 - 优化版"""
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from fontTools.ttLib import TTFont
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import ddddocr


def calculate_font_size(font_path: str, char: str, target_width: int, target_height: int) -> int:
    """
    计算合适的字体大小，使字符适应目标尺寸

    Args:
        font_path: 字体文件路径
        char: 字符
        target_width: 目标宽度
        target_height: 目标高度

    Returns:
        合适的字体大小
    """
    # 初始字体大小设为高度的80%
    font_size = int(target_height * 0.8)

    # 使用临时图像测试边界
    temp_img = Image.new('L', (target_width, target_height), 255)
    temp_draw = ImageDraw.Draw(temp_img)

    # 尝试调整字体大小直到字符适应
    for i in range(5):  # 最多尝试5次
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            # 如果无法加载字体，返回默认大小
            return int(target_height * 0.6)

        # 获取文本边界
        bbox = temp_draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        char_height = bbox[3] - bbox[1]

        # 如果字符太小，增大字体
        if char_width < target_width * 0.3 or char_height < target_height * 0.3:
            font_size += 5
        # 如果字符太大，减小字体
        elif char_width > target_width * 0.9 or char_height > target_height * 0.9:
            font_size -= 5
        else:
            break

    return max(20, min(font_size, target_height * 0.9))  # 确保在合理范围内


def convert_cmap_to_image(cmap_code: int, font_path: str,
                         img_size: Tuple[int, int] = (64, 64)) -> Image.Image:
    """
    将字符转换为OCR友好的图像

    Args:
        cmap_code: Unicode码点
        font_path: 字体文件路径
        img_size: 图像大小 (宽, 高)

    Returns:
        包含字符的图像对象
    """
    width, height = img_size
    character = chr(cmap_code)  # 将 cmap code 转换为字符

    # 使用灰度图像，白色背景，黑色文字 - OCR对此格式识别最好
    img = Image.new('L', (width, height), 255)  # 'L'模式是8位灰度，255是白色
    draw = ImageDraw.Draw(img)

    try:
        # 计算合适的字体大小
        font_size = calculate_font_size(font_path, character, width, height)
        font = ImageFont.truetype(font_path, font_size)
    except Exception as e:
        print(f"加载字体失败，使用默认字体: {e}")
        # 如果无法加载字体，使用默认字体
        font_size = int(height * 0.6)
        try:
            # 尝试加载系统默认字体
            font = ImageFont.truetype(font_path, font_size)
        except:
            # 最后使用PIL默认字体
            font = ImageFont.load_default()

    # 获取文本边界
    bbox = draw.textbbox((0, 0), character, font=font)
    char_width = bbox[2] - bbox[0]
    char_height = bbox[3] - bbox[1]

    # 计算居中位置
    x = (width - char_width) // 2 - bbox[0]
    y = (height - char_height) // 2 - bbox[1]

    # 绘制文本（黑色）
    draw.text((x, y), character, font=font, fill=0)  # 0是黑色

    # 对图像进行轻微锐化，提高OCR识别率
    img = img.filter(ImageFilter.SHARPEN)

    # 转换为二值图像（黑白），进一步提高对比度
    img = img.point(lambda x: 0 if x < 128 else 255, '1')

    # 转换回灰度图像（因为ddddocr可能对灰度图像识别更好）
    img = img.convert('L')

    return img


def save_character_image(image: Image.Image, save_dir: Path,
                        glyph_name: str, cmap_code: int) -> str:
    """
    保存字符图像到指定目录

    Args:
        image: 图像对象
        save_dir: 保存目录
        glyph_name: 字形名称
        cmap_code: Unicode码点

    Returns:
        保存的文件名
    """
    # 创建保存目录（如果不存在）
    save_dir.mkdir(parents=True, exist_ok=True)

    # 生成安全的文件名
    hex_code = f"{cmap_code:04x}"
    base_filename = f"{glyph_name}_U{hex_code}"

    # 清理文件名中的非法字符
    safe_filename = "".join(c for c in base_filename if c.isalnum() or c in ('-', '_', '.'))
    if not safe_filename:
        safe_filename = f"char_{hex_code}"

    # 确保文件名不重复
    counter = 1
    original_filename = safe_filename
    while (save_dir / f"{safe_filename}.png").exists():
        safe_filename = f"{original_filename}_{counter}"
        counter += 1

    # 保存图像为PNG格式
    filename = f"{safe_filename}.png"
    image.save(save_dir / filename, "PNG")

    return filename


def extract_text_from_font(font_path: str, save_images: bool = False,
                          image_dir: Optional[str] = None) -> Dict[str, dict]:
    """
    从字体文件中提取字符映射关系

    Args:
        font_path: 字体文件路径
        save_images: 是否保存字符图像
        image_dir: 图像保存目录（如果为None则使用默认目录）

    Returns:
        字体映射字典
    """
    print(f"开始处理字体文件: {font_path}")

    # 检查字体文件是否存在
    if not os.path.exists(font_path):
        print(f"错误: 字体文件 '{font_path}' 不存在")
        return {}

    try:
        font = TTFont(font_path)  # 加载字体文件
    except Exception as e:
        print(f"加载字体文件失败: {e}")
        return {}

    # 初始化OCR
    print("初始化OCR引擎...")
    try:
        # 使用默认配置，确保兼容性
        ocr = ddddocr.DdddOcr(beta=True, show_ad=False)
    except Exception as e:
        print(f"初始化OCR失败: {e}")
        return {}

    font_map = {}
    cmap = font.getBestCmap()

    if not cmap:
        print("字体文件中未找到字符映射")
        return font_map

    print(f"发现 {len(cmap)} 个字符")

    # 设置图像保存目录
    if save_images:
        if image_dir is None:
            # 默认保存到字体文件同目录下的images文件夹
            font_file = Path(font_path)
            image_dir = font_file.parent / f"{font_file.stem}_images"
        else:
            image_dir = Path(image_dir)

        print(f"字符图像将保存到: {image_dir.absolute()}")

    processed = 0
    successful = 0

    for cmap_code, glyph_name in cmap.items():
        try:
            # 转换字符为图像（使用64x64大小，适合OCR识别）
            image = convert_cmap_to_image(cmap_code, font_path, img_size=(64, 64))

            # 保存图像（如果需要）
            image_filename = None
            if save_images and image_dir:
                image_filename = save_character_image(image, image_dir, glyph_name, cmap_code)

            # 使用OCR识别图像
            bytes_io = BytesIO()
            image.save(bytes_io, "PNG")
            bytes_io.seek(0)  # 重置指针到开始位置

            # OCR识别
            text = ocr.classification(bytes_io.getvalue())

            # 保存映射关系
            font_map[glyph_name] = {
                "text": text,
                "unicode": f"U+{cmap_code:04X}",
                "code_point": cmap_code,
                "hex": f"{cmap_code:04x}",
                "image_file": image_filename
            }

            successful += 1

        except Exception as e:
            print(f"处理字符 {glyph_name} (U+{cmap_code:04X}) 时出错: {e}")

        processed += 1

        # 显示进度
        if processed % 100 == 0 or processed == len(cmap):
            print(f"进度: {processed}/{len(cmap)} 字符，成功识别: {successful}")

    print(f"处理完成！成功处理 {successful}/{len(cmap)} 个字符")

    return font_map


def save_font_map(font_map: Dict, output_path: str, indent: int = 2):
    """
    保存字体映射到JSON文件

    Args:
        font_map: 字体映射字典
        output_path: 输出文件路径
        indent: JSON缩进
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(font_map, f, ensure_ascii=False, indent=indent)
        print(f"字体映射已保存到: {output_path}")
    except Exception as e:
        print(f"保存字体映射失败: {e}")


def main():
    # 配置参数
    font_file_path = 'font.woff2'  # 字体文件路径
    save_images = True  # 是否保存字符图像
    output_json = 'font_map.json'  # 输出JSON文件

    print("=" * 50)
    print("字体识别工具 - 优化版")
    print("=" * 50)

    # 检查字体文件是否存在
    if not os.path.exists(font_file_path):
        print(f"错误: 字体文件 '{font_file_path}' 不存在")
        print("请将字体文件命名为 'font.woff2' 或修改代码中的路径")
        return

    # 提取字体映射
    print("\n开始提取字体映射...")
    font_map = extract_text_from_font(
        font_file_path,
        save_images=save_images
    )

    if not font_map:
        print("未能提取任何字体映射")
        return

    # 保存映射到JSON文件
    print("\n保存结果...")
    save_font_map(font_map, output_json)

    # 输出统计信息
    print("\n" + "=" * 50)
    print("统计信息:")
    print(f"总字符数: {len(font_map)}")

    # 按字符类型统计
    text_chars = [item["text"] for item in font_map.values() if item["text"].strip()]
    unique_texts = set(text_chars)
    print(f"识别出的不同字符: {len(unique_texts)}")

    # 显示部分识别结果
    print("\n前20个字符识别结果:")
    for i, (glyph_name, info) in enumerate(list(font_map.items())[:20]):
        char = chr(info['code_point']) if info['code_point'] < 0x10000 else '?'
        print(f"  {i+1:2d}. {glyph_name:15} {info['unicode']} ({char}) -> '{info['text']}'")

    print("\n处理完成！")

#测试
if __name__ == "__main__":
    main()