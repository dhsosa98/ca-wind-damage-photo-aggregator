"""
Type definitions for Wind-Damage Photo Aggregator
Using Pydantic for validation and JSON serialization
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Enums
class LossType(str, Enum):
    """Supported loss types"""
    WIND = "wind"

class DamageArea(str, Enum):
    """Supported damage areas"""
    ROOF = "roof"
    ATTIC = "attic"
    SIDING = "siding"
    GARAGE = "garage"
    WINDOWS = "windows"
    GUTTERS = "gutters"
    UNKNOWN = "unknown"

class DamageSeverity(int, Enum):
    """Damage severity levels"""
    NONE = 0
    MINOR = 1
    MODERATE = 2
    MAJOR = 3
    SEVERE = 4

# Request/Response Types
class AggregateRequest(BaseModel):
    """Request payload for image aggregation"""
    model_config = ConfigDict(use_enum_values=True)
    
    claim_id: str = Field(..., description="Claim identifier")
    loss_type: LossType = Field(..., description="Type of loss")
    images: List[str] = Field(..., description="List of image URLs")
    
    @field_validator('claim_id')
    @classmethod
    def validate_claim_id(cls, v):
        if not v:
            raise ValueError("claim_id is required")
        if len(v) > 50:
            raise ValueError("claim_id too long")
        return v
    
    @field_validator('images')
    @classmethod
    def validate_images(cls, v):
        if not v:
            raise ValueError("images array cannot be empty")
        if len(v) > 100:
            raise ValueError("Maximum 100 images allowed")
        return v
    
    @field_validator('loss_type')
    @classmethod
    def validate_loss_type(cls, v):
        if v != LossType.WIND:
            raise ValueError("Only wind loss type is supported")
        return v

class ErrorResponse(BaseModel):
    """Error response structure"""
    model_config = ConfigDict(use_enum_values=True)
    
    error: str = Field(..., description="Error message")
    correlation_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class SourceImages(BaseModel):
    """Source image statistics"""
    model_config = ConfigDict(use_enum_values=True)
    
    total: int = Field(..., description="Total images received")
    analyzed: int = Field(..., description="Images analyzed")
    discarded_low_quality: int = Field(..., description="Images discarded due to quality")
    clusters: int = Field(..., description="Number of image clusters")

class DamageAreaInfo(BaseModel):
    """Damage information for a specific area"""
    model_config = ConfigDict(use_enum_values=True)
    
    area: DamageArea = Field(..., description="Damage area")
    damage_confirmed: bool = Field(..., description="Whether damage is confirmed")
    primary_peril: str = Field(..., description="Primary peril type")
    count: int = Field(..., description="Number of images for this area")
    avg_severity: float = Field(..., description="Average severity score")
    representative_images: List[str] = Field(..., description="Representative image URLs")
    notes: str = Field(..., description="Additional notes")

class AggregateResponse(BaseModel):
    """Response payload for image aggregation"""
    model_config = ConfigDict(use_enum_values=True)
    
    claim_id: str = Field(..., description="Claim identifier")
    source_images: SourceImages = Field(..., description="Source image statistics")
    overall_damage_severity: float = Field(..., description="Overall damage severity")
    areas: List[DamageAreaInfo] = Field(..., description="Damage by area")
    data_gaps: List[str] = Field(..., description="Identified data gaps")
    confidence: float = Field(..., description="Overall confidence score")
    generated_at: str = Field(..., description="Generation timestamp")
    correlation_id: str = Field(..., description="Request correlation ID")

# Image Processing Types
class ImageData(BaseModel):
    """Image data with metadata"""
    model_config = ConfigDict(use_enum_values=True)
    
    url: str = Field(..., description="Image URL")
    image_bytes: bytes = Field(..., description="Image bytes")
    size_bytes: int = Field(..., description="Image size in bytes")
    content_type: str = Field(..., description="Content type")

class QualityScore(BaseModel):
    """Image quality analysis results"""
    model_config = ConfigDict(use_enum_values=True)
    
    blur_score: float = Field(..., description="Blur detection score")
    brightness_score: float = Field(..., description="Brightness score")
    contrast_score: float = Field(..., description="Contrast score")
    size_score: float = Field(..., description="Size score")
    overall_score: float = Field(..., description="Overall quality score")
    is_acceptable: bool = Field(..., description="Whether image is acceptable")

class DamageIndicatorType(str, Enum):
    """Damage indicator types"""
    DAMAGE = "damage"
    BROKEN = "broken"
    CRACKED = "cracked"
    TORN = "torn"
    MISSING = "missing"
    DEBRIS = "debris"
    DESTRUCTION = "destruction"
    WRECKAGE = "wreckage"
    RUINS = "ruins"

class DamageIndicator(BaseModel):
    """Individual damage indicator"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: DamageIndicatorType = Field(..., description="Damage type")
    confidence: float = Field(..., description="Confidence score")
    severity_weight: int = Field(..., description="Severity weight")

class DamageAnalysis(BaseModel):
    """Complete damage analysis for an image"""
    model_config = ConfigDict(use_enum_values=True)
    
    image_path: str = Field(..., description="Image path/URL")
    has_damage: bool = Field(..., description="Whether damage was detected")
    area: DamageArea = Field(..., description="Damage area")
    severity: DamageSeverity = Field(..., description="Damage severity")
    quality_score: float = Field(..., description="Image quality score")
    confidence: float = Field(..., description="Analysis confidence")
    damage_indicators: List[DamageIndicator] = Field(default_factory=list)
    error: Optional[str] = Field(None, description="Error message if any")
    notes: str = Field(..., description="Notes about the analysis. E.g: 'Shingle uplift along ridge'")

class DeduplicationCluster(BaseModel):
    """Image cluster for deduplication"""
    images: List[ImageData] = Field(..., description="List of images in the cluster")
    best_image: ImageData = Field(..., description="The best image in the cluster")
    similarity_score: float = Field(..., description="Similarity score between the best image and others")

class DeduplicationResult(BaseModel):
    """Deduplication analysis results"""
    total_images: int = Field(..., description="Total images processed")
    clusters: int = Field(..., description="Number of image clusters")
    duplicates_removed: int = Field(..., description="Number of images removed as duplicates")
    cluster_sizes: List[int] = Field(..., description="Size of each cluster")

# Processing Pipeline Types
class ProcessingStep(BaseModel):
    """Individual processing step result"""
    step_name: str = Field(..., description="Name of the processing step")
    duration_ms: float = Field(..., description="Duration in milliseconds")
    input_count: int = Field(..., description="Number of items input to the step")
    output_count: int = Field(..., description="Number of items output from the step")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during the step")

class ProcessingPipeline(BaseModel):
    """Complete processing pipeline results"""
    steps: List[ProcessingStep] = Field(..., description="List of processing steps")
    total_duration_ms: float = Field(..., description="Total duration of the pipeline in milliseconds")
    success: bool = Field(..., description="Whether the pipeline execution was successful")
    correlation_id: str = Field(..., description="Request correlation ID")

# API Gateway Types
class APIGatewayEvent(BaseModel):
    """API Gateway event structure"""
    body: str = Field(..., description="Request body")
    headers: Dict[str, str] = Field(..., description="Request headers")
    http_method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Request path")
    query_string_parameters: Optional[Dict[str, str]] = Field(None, description="Query string parameters")
    path_parameters: Optional[Dict[str, str]] = Field(None, description="Path parameters")

class APIGatewayResponse(BaseModel):
    """API Gateway response structure"""
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(..., description="Response headers")
    body: str = Field(..., description="Response body")
    is_base64_encoded: bool = Field(default=False, description="Whether the body is base64 encoded")

# Logging Types
class LogContext(BaseModel):
    """Structured logging context"""
    model_config = ConfigDict(use_enum_values=True)
    
    correlation_id: str = Field(..., description="Request correlation ID")
    claim_id: Optional[str] = Field(None, description="Claim identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    request_id: Optional[str] = Field(None, description="Request identifier")

class PerformanceMetric(BaseModel):
    """Performance metric for monitoring"""
    operation: str = Field(..., description="Operation name")
    duration_ms: float = Field(..., description="Duration in milliseconds")
    success: bool = Field(..., description="Whether the operation was successful")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

# AWS Service Types
class RekognitionLabel(BaseModel):
    """Amazon Rekognition label"""
    name: str = Field(..., description="Label name")
    confidence: float = Field(..., description="Confidence score")
    instances: List[Dict[str, Any]] = Field(default_factory=list, description="Instances of the label")
    parents: List[Dict[str, Any]] = Field(default_factory=list, description="Parent labels")

class RekognitionResponse(BaseModel):
    """Amazon Rekognition API response"""
    labels: List[RekognitionLabel] = Field(..., description="List of detected labels")
    label_model_version: str = Field(..., description="Version of the label detection model")
    image_properties: Optional[Dict[str, Any]] = Field(None, description="Image properties")

# Utility Types
class ImageDownloadResult(BaseModel):
    """Result of image download attempt"""
    url: str = Field(..., description="Image URL")
    success: bool = Field(..., description="Whether the download was successful")
    image_data: Optional[ImageData] = Field(None, description="Downloaded image data")
    error: Optional[str] = Field(None, description="Error message if download failed")
    duration_ms: float = Field(default=0.0, description="Duration of the download in milliseconds")

class BatchProcessingResult(BaseModel):
    """Result of batch processing operation"""
    total_items: int = Field(..., description="Total items processed")
    successful_items: int = Field(..., description="Number of successful items")
    failed_items: int = Field(..., description="Number of failed items")
    results: List[Any] = Field(..., description="List of results for each item")
    errors: List[str] = Field(default_factory=list, description="List of errors for failed items")

# Type Aliases for convenience
ImageTuple = Tuple[str, bytes]
QualityResult = Tuple[ImageTuple, float]
DamageResult = List[DamageAnalysis]

# Processing Result Type
class ProcessingResult(BaseModel):
    """Result of image processing pipeline"""
    model_config = ConfigDict(use_enum_values=True)
    
    total_images: int = Field(..., description="Total images processed")
    analyzed_images: int = Field(..., description="Images successfully analyzed")
    discarded_low_quality: int = Field(..., description="Images discarded")
    clusters: int = Field(..., description="Number of image clusters")
    damage_results: List[DamageAnalysis] = Field(..., description="Damage analysis results")

# Validation Functions
def validate_claim_id(claim_id: str) -> bool:
    """Validate claim ID format"""
    return bool(claim_id and len(claim_id) <= 50)

def validate_image_url(url: str) -> bool:
    """Validate image URL"""
    if not url:
        return False
    return url.startswith(('http://', 'https://'))

def validate_severity(severity: int) -> bool:
    """Validate damage severity"""
    return 0 <= severity <= 4

def validate_confidence(confidence: float) -> bool:
    """Validate confidence score"""
    return 0.0 <= confidence <= 1.0 