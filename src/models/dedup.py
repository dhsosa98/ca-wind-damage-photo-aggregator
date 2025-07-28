"""
Image deduplication using perceptual hashing
Identifies visually similar images and keeps the highest quality one
"""

import logging
from typing import List, Dict
from PIL import Image
import io
import numpy as np

from schemas import (
    DeduplicationResult, 
    ImageTuple
)

logger = logging.getLogger(__name__)

class Deduplicator:
    """
    Deduplicates images using perceptual hashing
    """
    
    def __init__(self):
        """Initialize deduplicator with similarity threshold"""
        self.similarity_threshold = 0.9  # Images with similarity > 0.9 are considered duplicates
        self.hash_size = 8  # Size of perceptual hash (8x8 = 64 bits)
    
    def deduplicate(self, images: List[ImageTuple]) -> List[ImageTuple]:
        """
        Remove duplicate images, keeping the highest quality one from each cluster
        
        Args:
            images: List of (image_path, image_bytes) tuples
            
        Returns:
            List of unique images (highest quality from each cluster)
        """
        if len(images) <= 1:
            return images
        
        # Calculate perceptual hashes for all images
        image_hashes = []
        for image_path, image_bytes in images:
            try:
                phash = self._calculate_perceptual_hash(image_bytes)
                quality_score = self._calculate_quality_score(image_bytes)
                image_hashes.append({
                    'path': image_path,
                    'bytes': image_bytes,
                    'hash': phash,
                    'quality_score': quality_score
                })
            except Exception as e:
                logger.warning(f"Error calculating hash for {image_path}: {str(e)}")
                continue
        
        # Group similar images
        clusters = self._cluster_similar_images(image_hashes)
        
        # Select best image from each cluster
        unique_images = []
        for cluster in clusters:
            if cluster:
                # Sort by quality score and take the best one
                best_image = max(cluster, key=lambda x: x['quality_score'])
                unique_images.append((best_image['path'], best_image['bytes']))
        
        logger.info(f"Deduplication: {len(images)} -> {len(unique_images)} images")
        return unique_images
    
    def _calculate_perceptual_hash(self, image_bytes: bytes) -> str:
        """
        Calculate perceptual hash of an image
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            Perceptual hash string
        """
        try:
            # Open image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to grayscale
            image = image.convert('L')
            
            # Resize to hash_size x hash_size
            image = image.resize((self.hash_size, self.hash_size))
            
            # Convert to numpy array
            pixels = np.array(image)
            
            # Calculate mean pixel value
            mean_pixel = np.mean(pixels)
            
            # Create hash: 1 if pixel > mean, 0 otherwise
            hash_bits = pixels > mean_pixel
            
            # Convert to string
            hash_string = ''.join(['1' if bit else '0' for bit in hash_bits.flatten()])
            
            return hash_string
            
        except Exception as e:
            logger.error(f"Error calculating perceptual hash: {str(e)}")
            # Return a default hash
            return '0' * (self.hash_size * self.hash_size)
    
    def _calculate_quality_score(self, image_bytes: bytes) -> float:
        """
        Calculate quality score for ranking images in clusters
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            Quality score between 0 and 1
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            
            # Simple quality metrics
            width, height = image.size
            
            # Resolution score
            resolution_score = min(1.0, (width * height) / (1920 * 1080))
            
            # Aspect ratio score
            aspect_ratio = width / height
            aspect_score = 1.0 if 0.5 <= aspect_ratio <= 2.0 else 0.5
            
            # Combine scores
            quality_score = (resolution_score + aspect_score) / 2
            
            return max(0.0, min(1.0, quality_score))
            
        except Exception as e:
            logger.warning(f"Error calculating quality score: {str(e)}")
            return 0.5
    
    def _cluster_similar_images(self, image_hashes: List[Dict]) -> List[List[Dict]]:
        """
        Group images into clusters based on similarity
        
        Args:
            image_hashes: List of image hash dictionaries
            
        Returns:
            List of clusters (each cluster is a list of similar images)
        """
        clusters = []
        processed = set()
        
        for i, img1 in enumerate(image_hashes):
            if i in processed:
                continue
            
            # Start new cluster
            cluster = [img1]
            processed.add(i)
            
            # Find similar images
            for j, img2 in enumerate(image_hashes[i+1:], i+1):
                if j in processed:
                    continue
                
                similarity = self._calculate_similarity(img1['hash'], img2['hash'])
                if similarity >= self.similarity_threshold:
                    cluster.append(img2)
                    processed.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def _calculate_similarity(self, hash1: str, hash2: str) -> float:
        """
        Calculate similarity between two perceptual hashes
        
        Args:
            hash1: First perceptual hash string
            hash2: Second perceptual hash string
            
        Returns:
            Similarity score between 0 and 1
        """
        if len(hash1) != len(hash2):
            return 0.0
        
        # Calculate Hamming distance
        hamming_distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        
        # Convert to similarity (0 = identical, 1 = completely different)
        max_distance = len(hash1)
        similarity = 1.0 - (hamming_distance / max_distance)
        
        return similarity
    
    def get_cluster_info(self, images: List[ImageTuple]) -> DeduplicationResult:
        """
        Get information about deduplication clusters
        
        Args:
            images: List of (image_path, image_bytes) tuples
            
        Returns:
            DeduplicationResult with cluster information
        """
        if len(images) <= 1:
            return DeduplicationResult(
                total_images=len(images),
                clusters=len(images),
                duplicates_removed=0,
                cluster_sizes=[1] * len(images)
            )
        
        # Calculate hashes
        image_hashes = []
        for image_path, image_bytes in images:
            try:
                phash = self._calculate_perceptual_hash(image_bytes)
                quality_score = self._calculate_quality_score(image_bytes)
                image_hashes.append({
                    'path': image_path,
                    'bytes': image_bytes,
                    'hash': phash,
                    'quality_score': quality_score
                })
            except Exception as e:
                logger.warning(f"Error in cluster info calculation: {str(e)}")
                continue
        
        # Cluster images
        clusters = self._cluster_similar_images(image_hashes)
        
        # Calculate statistics
        total_images = len(images)
        num_clusters = len(clusters)
        duplicates_removed = total_images - num_clusters
        
        return DeduplicationResult(
            total_images=total_images,
            clusters=num_clusters,
            duplicates_removed=duplicates_removed,
            cluster_sizes=[len(cluster) for cluster in clusters]
        ) 