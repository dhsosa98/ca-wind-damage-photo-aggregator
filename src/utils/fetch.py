"""
Image fetching utility for downloading images from URLs concurrently
Handles timeouts, retries, and error handling
"""

import asyncio
import aiohttp
import logging
from typing import List, Optional
from schemas import ImageTuple, BatchProcessingResult

logger = logging.getLogger(__name__)

class ImageFetcher:
    """
    Fetches images from URLs concurrently with error handling
    """
    
    def __init__(self):
        """Initialize fetcher with configuration"""
        self.timeout = 30  # seconds
        self.max_retries = 3
        self.max_concurrent = 10  # max concurrent downloads
        self.max_size = 10 * 1024 * 1024  # 10MB max file size
        
    async def fetch_images(self, urls: List[str], correlation_id: str) -> List[ImageTuple]:
        """
        Fetch images from URLs synchronously (wrapper for async)
        
        Args:
            urls: List of image URLs
            correlation_id: Request correlation ID for logging
            
        Returns:
            List of (url, image_bytes) tuples
        """
        return await self._fetch_images_async(urls, correlation_id)
    
    async def _fetch_images_async(self, urls: List[str], correlation_id: str) -> List[ImageTuple]:
        """
        Fetch images from URLs asynchronously
        
        Args:
            urls: List of image URLs
            correlation_id: Request correlation ID for logging
            
        Returns:
            List of (url, image_bytes) tuples
        """
        logger.info(f"Fetching {len(urls)} images", extra={"correlation_id": correlation_id})
        
        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Create tasks for all URLs
        tasks = [
            self._fetch_single_image(url, semaphore, correlation_id)
            for url in urls
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed downloads
        successful_downloads = []
        failed_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                logger.warning(f"Failed to download image: {str(result)}", 
                             extra={"correlation_id": correlation_id})
            elif result is not None:
                successful_downloads.append(result)
        
        logger.info(f"Downloaded {len(successful_downloads)}/{len(urls)} images successfully", 
                   extra={"correlation_id": correlation_id, "failed": failed_count})
        
        return successful_downloads
    
    async def _fetch_single_image(self, url: str, semaphore: asyncio.Semaphore, 
                                 correlation_id: str) -> Optional[ImageTuple]:
        """
        Fetch a single image with retry logic
        
        Args:
            url: Image URL
            semaphore: Semaphore for limiting concurrent downloads
            correlation_id: Request correlation ID for logging
            
        Returns:
            Tuple of (url, image_bytes) or None if failed
        """
        async with semaphore:
            for attempt in range(self.max_retries):
                try:
                    return await self._download_image(url, correlation_id)
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to download {url} after {self.max_retries} attempts: {str(e)}", 
                                   extra={"correlation_id": correlation_id})
                        return None
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}", 
                                     extra={"correlation_id": correlation_id})
                        await asyncio.sleep(1)  # Brief delay before retry
    
    async def _download_image(self, url: str, correlation_id: str) -> ImageTuple:
        """
        Download a single image
        
        Args:
            url: Image URL
            correlation_id: Request correlation ID for logging
            
        Returns:
            Tuple of (url, image_bytes)
        """
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if not content_type.startswith('image/'):
                    raise Exception(f"Invalid content type: {content_type}")
                
                # Read image data with size limit
                image_data = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    image_data.extend(chunk)
                    if len(image_data) > self.max_size:
                        raise Exception(f"Image too large: {len(image_data)} bytes")
                
                if not image_data:
                    raise Exception("Empty image data")
                
                logger.debug(f"Successfully downloaded {url} ({len(image_data)} bytes)", 
                           extra={"correlation_id": correlation_id})
                
                return (url, bytes(image_data))
    
    def validate_url(self, url: str) -> bool:
        """
        Validate if URL is likely to be an image
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears to be an image
        """
        if not url:
            return False
        
        # Check for common image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        url_lower = url.lower()
        
        return any(ext in url_lower for ext in image_extensions)
    
    def get_download_stats(self, urls: List[str], results: List[ImageTuple]) -> BatchProcessingResult:
        """
        Get statistics about download results
        
        Args:
            urls: Original list of URLs
            results: List of successful downloads
            
        Returns:
            BatchProcessingResult with download statistics
        """
        total_urls = len(urls)
        successful_downloads = len(results)
        failed_downloads = total_urls - successful_downloads
        
        total_size = sum(len(image_bytes) for _, image_bytes in results)
        avg_size = total_size / successful_downloads if successful_downloads > 0 else 0
        
        return BatchProcessingResult(
            total_items=total_urls,
            successful_items=successful_downloads,
            failed_items=failed_downloads,
            results=results,
            errors=[]  # Could be enhanced to track specific errors
        ) 