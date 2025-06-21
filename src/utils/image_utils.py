# -*- coding: utf-8 -*-
"""
图像工具模块
提供图像处理相关的实用函数
"""

import io
from typing import Optional, Tuple, List
from PIL import Image, ImageOps, ImageFilter
from loguru import logger


def validate_image_data(image_data: bytes) -> bool:
    """验证图像数据是否有效"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            img.verify()
        return True
    except Exception:
        return False


def get_image_info(image_data: bytes) -> Optional[dict]:
    """获取图像信息"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            return {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
                "has_transparency": img.mode in ("RGBA", "LA")
                or "transparency" in img.info,
            }
    except Exception as e:
        logger.error(f"获取图像信息失败: {e}")
        return None


def resize_image(
    image_data: bytes,
    max_size: Tuple[int, int],
    keep_aspect_ratio: bool = True,
    quality: int = 85,
) -> Optional[bytes]:
    """调整图像大小"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为RGB模式（如果需要）
            if img.mode in ("RGBA", "LA"):
                # 创建白色背景
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 调整大小
            if keep_aspect_ratio:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            else:
                img = img.resize(max_size, Image.Resampling.LANCZOS)

            # 保存到字节流
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=quality, optimize=True)
            return output.getvalue()

    except Exception as e:
        logger.error(f"调整图像大小失败: {e}")
        return None


def create_thumbnail(image_data: bytes, size: Tuple[int, int]) -> Optional[bytes]:
    """创建缩略图"""
    return resize_image(image_data, size, keep_aspect_ratio=True, quality=75)


def normalize_image_for_hash(
    image_data: bytes, size: Tuple[int, int] = (32, 32)
) -> Optional[Image.Image]:
    """标准化图像用于哈希计算"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为灰度
            img = img.convert("L")

            # 调整大小
            img = img.resize(size, Image.Resampling.LANCZOS)

            # 应用高斯模糊减少噪声
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

            return img

    except Exception as e:
        logger.error(f"标准化图像失败: {e}")
        return None


def extract_dominant_colors(
    image_data: bytes, num_colors: int = 5
) -> List[Tuple[int, int, int]]:
    """提取图像主要颜色"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为RGB
            if img.mode != "RGB":
                img = img.convert("RGB")

            # 缩小图像以提高性能
            img.thumbnail((150, 150))

            # 量化颜色
            img = img.quantize(colors=num_colors)

            # 获取调色板
            palette = img.getpalette()
            if not palette:
                return []

            # 转换为RGB元组
            colors = []
            for i in range(0, len(palette), 3):
                if i + 2 < len(palette):
                    colors.append((palette[i], palette[i + 1], palette[i + 2]))

            return colors[:num_colors]

    except Exception as e:
        logger.error(f"提取主要颜色失败: {e}")
        return []


def calculate_image_brightness(image_data: bytes) -> Optional[float]:
    """计算图像亮度（0-1）"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为灰度
            grayscale = img.convert("L")

            # 计算平均亮度
            pixels = list(grayscale.getdata())
            brightness = sum(pixels) / len(pixels) / 255.0

            return brightness

    except Exception as e:
        logger.error(f"计算图像亮度失败: {e}")
        return None


def detect_image_edges(image_data: bytes) -> Optional[float]:
    """检测图像边缘密度"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为灰度
            grayscale = img.convert("L")

            # 应用边缘检测滤镜
            edges = grayscale.filter(ImageFilter.FIND_EDGES)

            # 计算边缘密度
            pixels = list(edges.getdata())
            edge_density = sum(1 for p in pixels if p > 50) / len(pixels)

            return edge_density

    except Exception as e:
        logger.error(f"检测图像边缘失败: {e}")
        return None


def is_image_mostly_blank(image_data: bytes, threshold: float = 0.95) -> bool:
    """检测图像是否主要为空白"""
    try:
        brightness = calculate_image_brightness(image_data)
        if brightness is None:
            return False

        return brightness > threshold

    except Exception as e:
        logger.error(f"检测空白图像失败: {e}")
        return False


def is_image_too_dark(image_data: bytes, threshold: float = 0.05) -> bool:
    """检测图像是否过暗"""
    try:
        brightness = calculate_image_brightness(image_data)
        if brightness is None:
            return False

        return brightness < threshold

    except Exception as e:
        logger.error(f"检测暗图像失败: {e}")
        return False


def enhance_image_contrast(image_data: bytes, factor: float = 1.5) -> Optional[bytes]:
    """增强图像对比度"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 增强对比度
            enhanced = ImageOps.autocontrast(img, cutoff=1)

            # 保存到字节流
            output = io.BytesIO()
            enhanced.save(output, format=img.format or "JPEG")
            return output.getvalue()

    except Exception as e:
        logger.error(f"增强图像对比度失败: {e}")
        return None


def rotate_image(image_data: bytes, angle: float) -> Optional[bytes]:
    """旋转图像"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 旋转图像
            rotated = img.rotate(angle, expand=True, fillcolor="white")

            # 保存到字节流
            output = io.BytesIO()
            rotated.save(output, format=img.format or "JPEG")
            return output.getvalue()

    except Exception as e:
        logger.error(f"旋转图像失败: {e}")
        return None


def flip_image(image_data: bytes, horizontal: bool = True) -> Optional[bytes]:
    """翻转图像"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 翻转图像
            if horizontal:
                flipped = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            else:
                flipped = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

            # 保存到字节流
            output = io.BytesIO()
            flipped.save(output, format=img.format or "JPEG")
            return output.getvalue()

    except Exception as e:
        logger.error(f"翻转图像失败: {e}")
        return None


def crop_image(image_data: bytes, box: Tuple[int, int, int, int]) -> Optional[bytes]:
    """裁剪图像"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 裁剪图像
            cropped = img.crop(box)

            # 保存到字节流
            output = io.BytesIO()
            cropped.save(output, format=img.format or "JPEG")
            return output.getvalue()

    except Exception as e:
        logger.error(f"裁剪图像失败: {e}")
        return None


def convert_image_format(
    image_data: bytes, target_format: str, quality: int = 85
) -> Optional[bytes]:
    """转换图像格式"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 如果目标格式不支持透明度，转换为RGB
            if target_format.upper() in ("JPEG", "JPG") and img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img, mask=img.split()[-1])
                img = background

            # 保存到字节流
            output = io.BytesIO()
            save_kwargs = {"format": target_format.upper()}

            if target_format.upper() in ("JPEG", "JPG"):
                save_kwargs["quality"] = quality
                save_kwargs["optimize"] = True

            img.save(output, **save_kwargs)
            return output.getvalue()

    except Exception as e:
        logger.error(f"转换图像格式失败: {e}")
        return None


def get_image_histogram(image_data: bytes) -> Optional[List[int]]:
    """获取图像直方图"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换为灰度
            grayscale = img.convert("L")

            # 计算直方图
            histogram = grayscale.histogram()

            return histogram

    except Exception as e:
        logger.error(f"获取图像直方图失败: {e}")
        return None


def compare_histograms(hist1: List[int], hist2: List[int]) -> float:
    """比较两个直方图的相似度（0-1）"""
    try:
        if len(hist1) != len(hist2):
            return 0.0

        # 计算相关系数
        sum1 = sum(hist1)
        sum2 = sum(hist2)

        if sum1 == 0 or sum2 == 0:
            return 0.0

        # 标准化
        norm_hist1 = [x / sum1 for x in hist1]
        norm_hist2 = [x / sum2 for x in hist2]

        # 计算相似度
        similarity = sum(min(a, b) for a, b in zip(norm_hist1, norm_hist2))

        return similarity

    except Exception as e:
        logger.error(f"比较直方图失败: {e}")
        return 0.0
