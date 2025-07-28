"""
Main Lambda handler for Wind-Damage Photo Aggregator
Handles HTTP requests, validates input, orchestrates analysis pipeline
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
import asyncio
from src.models.damage_detector_gemini import DamageDetector
from src.models.quality import QualityAnalyzer
from src.models.dedup import Deduplicator
from src.utils.fetch import ImageFetcher
from src.utils.logging import setup_logging
from src.utils.aggregation import DamageAggregator, SeverityCalculator, DataGapAnalyzer, ConfidenceCalculator
from src.schemas import (
    AggregateRequest, AggregateResponse, ErrorResponse, SourceImages, LogContext,
    ProcessingResult, validate_image_url
)

# Setup logging
logger = setup_logging()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for processing wind damage photo aggregation requests
    
    Args:
        event: API Gateway event containing request body
        context: Lambda context
        
    Returns:
        Dict containing aggregated damage analysis results
    """
    loop = asyncio.get_event_loop()
    correlation_id = str(uuid.uuid4())
    log_context = LogContext(correlation_id=correlation_id)
    logger.info("Processing request", extra={"correlation_id": correlation_id})

    try:
        # Handle both direct Lambda invocation and API Gateway events
        if 'body' in event:
            # API Gateway event
            body = json.loads(event.get('body', '{}'))
        else:
            # Direct Lambda invocation
            body = event
        
        logger.info(f"Event: {body}", extra={"correlation_id": correlation_id})
        
        try:
            request = AggregateRequest.model_validate(body)
            log_context.claim_id = request.claim_id
        except Exception as e:
            return error_response(422, str(e), correlation_id)
        
        # Validate image URLs
        invalid_urls = [url for url in request.images if not validate_image_url(url)]
        if invalid_urls:
            return error_response(422, f"Invalid image URLs: {invalid_urls[:3]}", correlation_id)
            
        # Initialize components
        fetcher = ImageFetcher()
        quality_analyzer = QualityAnalyzer()
        deduplicator = Deduplicator()
        damage_detector = DamageDetector(debug=True)
        
        # Initialize aggregation components
        damage_aggregator = DamageAggregator()
        severity_calculator = SeverityCalculator()
        data_gap_analyzer = DataGapAnalyzer()
        confidence_calculator = ConfidenceCalculator()
        
        # Process images
        results = loop.run_until_complete(process_images(
            images=request.images,
            fetcher=fetcher,
            quality_analyzer=quality_analyzer,
            deduplicator=deduplicator,
            damage_detector=damage_detector,
            correlation_id=correlation_id
        ))
        
        # Generate typed response using aggregation components
        response = generate_response(
            claim_id=request.claim_id,
            results=results,
            damage_aggregator=damage_aggregator,
            severity_calculator=severity_calculator,
            data_gap_analyzer=data_gap_analyzer,
            confidence_calculator=confidence_calculator,
            correlation_id=correlation_id
        )

        logger.info("Request completed successfully",
                   extra={"correlation_id": correlation_id, "claim_id": request.claim_id})

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': response.model_dump()
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}",
                    extra={"correlation_id": correlation_id}, exc_info=True)
        return error_response(500, "Internal server error", correlation_id)

async def process_images(images: List[str], 
                   *,
                   fetcher: ImageFetcher, 
                   quality_analyzer: QualityAnalyzer, 
                   deduplicator: Deduplicator, 
                   damage_detector: DamageDetector, 
                   correlation_id: str) -> ProcessingResult:
    """
    Process the image analysis pipeline
    
    Args:
        images: List of image URLs
        fetcher: ImageFetcher instance
        quality_analyzer: QualityAnalyzer instance
        deduplicator: Deduplicator instance
        damage_detector: DamageDetector instance
        correlation_id: Request correlation ID
        
    Returns:
        ProcessingResult containing analysis results
    """
    # Download images
    downloaded_images = await fetcher.fetch_images(images, correlation_id)
    
    # Analyze quality and filter
    quality_results = await quality_analyzer.analyze_batch(downloaded_images)
    high_quality_images = [img for img, score in quality_results if score > 0.3]
    
    # Deduplicate
    unique_images = deduplicator.deduplicate(high_quality_images)
    
    # Detect damage
    damage_results = await damage_detector.analyze_batch(unique_images)

    error_results = []
    for result in damage_results:
        if result.error:
            error_results.append(result)

    if error_results:
        logger.error(f"Error results: {error_results}", extra={"correlation_id": correlation_id})

    damage_results = [result for result in damage_results if not result.error]

    
    return ProcessingResult(
        total_images=len(images),
        analyzed_images=len(high_quality_images),
        discarded_low_quality=len(images) - len(high_quality_images),
        clusters=len(unique_images),
        damage_results=damage_results
    )

def generate_response(claim_id: str, results: ProcessingResult, 
                    *,
                    damage_aggregator: DamageAggregator,
                    severity_calculator: SeverityCalculator,
                    data_gap_analyzer: DataGapAnalyzer,
                    confidence_calculator: ConfidenceCalculator,
                    correlation_id: str) -> AggregateResponse:
    """
    Generate the final typed response using aggregation components
    
    Args:
        claim_id: Claim identifier
        results: Analysis results
        correlation_id: Request correlation ID
        damage_aggregator: Damage aggregation component
        severity_calculator: Severity calculation component
        data_gap_analyzer: Data gap analysis component
        confidence_calculator: Confidence calculation component
        
    Returns:
        AggregateResponse containing formatted response
    """
    # Aggregate damage by area
    areas = damage_aggregator.aggregate_damage_by_area(results.damage_results)
    
    # Calculate overall severity
    overall_severity = severity_calculator.calculate_overall_severity(results.damage_results)
    
    # Create source images info
    source_images = SourceImages(
        total=results.total_images,
        analyzed=results.analyzed_images,
        discarded_low_quality=results.discarded_low_quality,
        clusters=results.clusters
    )
    
    return AggregateResponse(
        claim_id=claim_id,
        source_images=source_images,
        overall_damage_severity=overall_severity,
        areas=areas,
        data_gaps=data_gap_analyzer.identify_data_gaps(areas),
        confidence=confidence_calculator.calculate_confidence(results.damage_results),
        generated_at=datetime.now(timezone.utc).isoformat(),
        correlation_id=correlation_id
    )



def error_response(status_code: int, message: str, correlation_id: str) -> Dict[str, Any]:
    """Generate error response using Pydantic"""
    error_response = ErrorResponse(
        error=message,
        correlation_id=correlation_id
    )
    
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json'},
        'body': error_response.model_dump()
    } 