"""
Image quality analysis for filtering blurry, dark, or unrelated images
Uses Laplacian variance for blur detection and luminance analysis
"""

import cv2
import numpy as np
import logging
from typing import List, Tuple
from src.schemas import ImageTuple
import asyncio

logger = logging.getLogger(__name__)

class QualityAnalyzer:
    """
    Analyzes image quality using various metrics
    """
    
    def __init__(self):
        """Initialize quality analyzer with thresholds"""
        # Quality thresholds
        self.blur_threshold = 100.0  # Laplacian variance threshold
        self.brightness_threshold = 30.0  # Minimum average brightness
        self.contrast_threshold = 20.0  # Minimum contrast
        
        # Size thresholds
        self.min_width = 200
        self.min_height = 200
        self.max_width = 8000
        self.max_height = 8000
    
    async def analyze_batch(self, images: List[ImageTuple], batch_size: int = 8) -> List[Tuple[ImageTuple, float]]:
        """
        Analyze quality for a batch of images asynchronously with batching.

        Args:
            images: List of (image_path, image_bytes) tuples
            batch_size: Number of images to process concurrently

        Returns:
            List of (image_tuple, quality_score) tuples
        """
        semaphore = asyncio.Semaphore(batch_size)

        async def analyze_one(image_tuple: ImageTuple) -> Tuple[ImageTuple, float]:
            try:
                async with semaphore:
                    loop = asyncio.get_running_loop()
                    # Run the sync analyze_single_image in a thread pool
                    quality_score = await loop.run_in_executor(
                        None, self.analyze_single_image, image_tuple[1]
                    )
                    return (image_tuple, quality_score)
            except Exception as e:
                logger.warning(f"Error analyzing quality for image: {str(e)}")
                # Assign low quality score for failed analysis
                return (image_tuple, 0.1)

        tasks = [analyze_one(image_tuple) for image_tuple in images]
        results = await asyncio.gather(*tasks)
        return results
    
    def analyze_single_image(self, image_bytes: bytes) -> float:
        """
        Analyze quality of a single image
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            Quality score between 0 and 1
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return 0.0
            
            # Calculate quality metrics
            blur_score = self._calculate_blur_score(image)
            brightness_score = self._calculate_brightness_score(image)
            contrast_score = self._calculate_contrast_score(image)
            size_score = self._calculate_size_score(image)
            
            # Combine scores with weights
            quality_score = (
                blur_score * 0.4 +
                brightness_score * 0.3 +
                contrast_score * 0.2 +
                size_score * 0.1
            )
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            logger.error(f"Error in quality analysis: {str(e)}")
            return 0.0
    
    def _calculate_blur_score(self, image: np.ndarray) -> float:
        """
        Calculate blur score using Laplacian variance
        
        Args:
            image: OpenCV image array
            
        Returns:
            Blur score between 0 and 1 (higher = less blurry)
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Normalize to 0-1 scale
            # Higher variance = less blurry
            blur_score = min(1.0, laplacian_var / self.blur_threshold)
            
            return blur_score
            
        except Exception as e:
            logger.warning(f"Error calculating blur score: {str(e)}")
            return 0.5
    
    def _calculate_brightness_score(self, image: np.ndarray) -> float:
        """
        Calculate brightness score
        
        Args:
            image: OpenCV image array
            
        Returns:
            Brightness score between 0 and 1
        """
        try:
            # Convert to HSV for better brightness analysis
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:, :, 2]
            
            # Calculate average brightness
            avg_brightness = np.mean(v_channel)
            
            # Normalize to 0-1 scale
            # Optimal brightness around 128 (middle of 0-255)
            brightness_score = 1.0 - abs(avg_brightness - 128) / 128
            
            return max(0.0, min(1.0, brightness_score))
            
        except Exception as e:
            logger.warning(f"Error calculating brightness score: {str(e)}")
            return 0.5
    
    def _calculate_contrast_score(self, image: np.ndarray) -> float:
        """
        Calculate contrast score
        
        Args:
            image: OpenCV image array
            
        Returns:
            Contrast score between 0 and 1
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Calculate standard deviation as contrast measure
            contrast = np.std(gray)
            
            # Normalize to 0-1 scale
            # Higher contrast is better, but not too high
            contrast_score = min(1.0, contrast / 50.0)
            
            return contrast_score
            
        except Exception as e:
            logger.warning(f"Error calculating contrast score: {str(e)}")
            return 0.5
    
    def _calculate_size_score(self, image: np.ndarray) -> float:
        """
        Calculate size score based on image dimensions
        
        Args:
            image: OpenCV image array
            
        Returns:
            Size score between 0 and 1
        """
        try:
            height, width = image.shape[:2]
            
            # Check minimum size
            if width < self.min_width or height < self.min_height:
                return 0.0
            
            # Check maximum size
            if width > self.max_width or height > self.max_height:
                return 0.5  # Penalize very large images
            
            # Calculate area
            area = width * height
            
            # Optimal area around 1MP (1024x1024)
            optimal_area = 1024 * 1024
            
            # Score based on how close to optimal area
            area_ratio = min(area / optimal_area, optimal_area / area)
            size_score = area_ratio
            
            return max(0.0, min(1.0, size_score))
            
        except Exception as e:
            logger.warning(f"Error calculating size score: {str(e)}")
            return 0.5
    
    def is_acceptable_quality(self, quality_score: float) -> bool:
        """
        Determine if quality score is acceptable
        
        Args:
            quality_score: Quality score between 0 and 1
            
        Returns:
            True if quality is acceptable
        """
        return quality_score >= 0.3
    
    def get_quality_description(self, quality_score: float) -> str:
        """
        Get human-readable quality description
        
        Args:
            quality_score: Quality score between 0 and 1
            
        Returns:
            Quality description string
        """
        if quality_score >= 0.8:
            return "excellent"
        elif quality_score >= 0.6:
            return "good"
        elif quality_score >= 0.4:
            return "fair"
        elif quality_score >= 0.2:
            return "poor"
        else:
            return "unacceptable" 