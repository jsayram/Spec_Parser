"""
Image preprocessing for OCR optimization.

Provides contrast enhancement, binarization, and denoising
to improve OCR accuracy on extracted PDF regions.
"""

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
from typing import Tuple
from loguru import logger


class ImagePreprocessor:
    """
    Image preprocessing pipeline for OCR optimization.
    
    Applies contrast enhancement, sharpening, adaptive binarization,
    and denoising to improve text recognition accuracy.
    """

    def __init__(
        self,
        contrast_factor: float = 1.5,
        sharpness_factor: float = 2.0,
    ):
        """
        Initialize image preprocessor.

        Args:
            contrast_factor: Contrast enhancement multiplier (1.0 = no change)
            sharpness_factor: Sharpness enhancement multiplier (1.0 = no change)
        """
        self.contrast_factor = contrast_factor
        self.sharpness_factor = sharpness_factor

    def preprocess(self, image: Image.Image) -> Image.Image:
        """
        Apply full preprocessing pipeline to improve OCR accuracy.

        Pipeline steps:
        1. Convert to grayscale
        2. Enhance contrast
        3. Enhance sharpness
        4. Apply adaptive binarization (Otsu thresholding)
        5. Denoise with median filter
        6. Auto-invert if background is dark

        Args:
            image: Original PIL Image (RGB or grayscale)

        Returns:
            Preprocessed PIL Image optimized for OCR
        """
        try:
            # Step 1: Convert to grayscale
            gray = image.convert("L")

            # Step 2: Enhance contrast
            contrasted = self._enhance_contrast(gray)

            # Step 3: Enhance sharpness
            sharpened = self._enhance_sharpness(contrasted)

            # Step 4: Adaptive binarization
            binarized = self._binarize(sharpened)

            # Step 5: Denoise
            denoised = self._denoise(binarized)

            # Step 6: Auto-invert if needed
            result = self._auto_invert(denoised)

            logger.debug(
                f"Preprocessed image: {image.size} -> grayscale, "
                f"contrast={self.contrast_factor}"
            )

            return result

        except Exception as e:
            logger.warning(f"Preprocessing failed, using original image: {e}")
            return image

    def _enhance_contrast(self, image: Image.Image) -> Image.Image:
        """
        Enhance image contrast.

        Args:
            image: Grayscale PIL Image

        Returns:
            Contrast-enhanced image
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(self.contrast_factor)

    def _enhance_sharpness(self, image: Image.Image) -> Image.Image:
        """
        Enhance image sharpness for crisper edges.

        Args:
            image: PIL Image

        Returns:
            Sharpness-enhanced image
        """
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(self.sharpness_factor)

    def _binarize(self, image: Image.Image) -> Image.Image:
        """
        Apply adaptive binarization using Otsu's method.

        Converts grayscale image to pure black and white
        using optimal threshold calculation.

        Args:
            image: Grayscale PIL Image

        Returns:
            Binarized (black/white only) image
        """
        img_array = np.array(image)
        threshold = self._otsu_threshold(img_array)
        binary_array = ((img_array > threshold) * 255).astype(np.uint8)
        return Image.fromarray(binary_array, mode="L")

    def _denoise(self, image: Image.Image) -> Image.Image:
        """
        Remove salt-and-pepper noise with median filter.

        Args:
            image: PIL Image

        Returns:
            Denoised image
        """
        return image.filter(ImageFilter.MedianFilter(size=3))

    def _auto_invert(self, image: Image.Image) -> Image.Image:
        """
        Invert image if background is dark.

        OCR works best with black text on white background.
        This detects and corrects inverted text (white on black).

        Args:
            image: Grayscale PIL Image

        Returns:
            Image with white background guaranteed
        """
        mean_value = np.mean(np.array(image))
        if mean_value < 127:
            return ImageOps.invert(image)
        return image

    def _otsu_threshold(self, img_array: np.ndarray) -> int:
        """
        Calculate Otsu's optimal threshold for binarization.

        Finds the threshold that minimizes intra-class variance
        between foreground and background pixels.

        Args:
            img_array: Grayscale image as numpy array

        Returns:
            Optimal threshold value (0-255)
        """
        # Calculate histogram
        pixel_counts = np.bincount(img_array.flatten(), minlength=256)
        total_pixels = img_array.size

        # Initialize for iterative optimization
        sum_total = np.sum(np.arange(256) * pixel_counts)
        sum_bg = 0
        weight_bg = 0
        max_variance = 0
        threshold = 0

        for t in range(256):
            weight_bg += pixel_counts[t]
            if weight_bg == 0:
                continue

            weight_fg = total_pixels - weight_bg
            if weight_fg == 0:
                break

            sum_bg += t * pixel_counts[t]

            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg

            # Between-class variance
            variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2

            if variance > max_variance:
                max_variance = variance
                threshold = t

        return threshold


def preprocess_for_ocr(
    image: Image.Image,
    contrast_factor: float = 1.5,
    sharpness_factor: float = 2.0,
) -> Image.Image:
    """
    Convenience function for one-off preprocessing.

    Args:
        image: Original PIL Image
        contrast_factor: Contrast enhancement multiplier
        sharpness_factor: Sharpness enhancement multiplier

    Returns:
        Preprocessed image optimized for OCR
    """
    preprocessor = ImagePreprocessor(
        contrast_factor=contrast_factor,
        sharpness_factor=sharpness_factor,
    )
    return preprocessor.preprocess(image)
