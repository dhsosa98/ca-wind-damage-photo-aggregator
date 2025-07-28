import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Literal, Tuple
from pydantic import BaseModel, Field, field_validator
from src.schemas import DamageAnalysis, DamageArea, DamageSeverity, DamageIndicator
import traceback
import asyncio


class DamageIndicatorOutput(BaseModel):
    type: Literal['damage', 'broken', 'cracked', 'torn', 'missing', 'debris', 'destruction', 'wreckage', 'ruins'] = Field(..., description="Damage type")
    confidence: float = Field(..., description="Confidence score")
    severity_weight: int = Field(..., description="Severity weight")

class DamageAnalysisGeminiOutput(BaseModel):
    has_damage: bool = Field(..., description="Whether damage was detected")
    location: Literal['roof', 'attic', 'siding', 'garage', 'windows', 'gutters', 'unknown'] = Field(..., description="Damage area")
    severity: int = Field(..., description="Damage severity")
    confidence: float = Field(..., description="Analysis confidence")
    damage_indicators: List[DamageIndicatorOutput] = Field(default_factory=list, description="List of damage indicators")
    notes: str = Field(..., description="Notes about the analysis. E.g: 'Shingle uplift along ridge'")

    @field_validator('severity')
    def validate_severity(cls, v):
        if v not in [0, 1, 2, 3, 4]:
            raise ValueError("Severity must be an integer between 0 and 4")
        return v

logger = logging.getLogger(__name__)

class DamageDetector:
    """
    Uses Google Gemini Vision API to detect and classify wind damage in images.
    Provides location classification and severity scoring.
    """
    
    def __init__(self, debug: bool = False):
        # Initialize Gemini API
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        model = ChatGoogleGenerativeAI(model='gemini-2.5-flash', temperature=0.0, api_key=api_key)
        self.chain = model.with_structured_output(DamageAnalysisGeminiOutput)
        self.debug = debug

    async def analyze_batch(self, images: List[Tuple[str, bytes]], batch_size: int = 2) -> List[DamageAnalysis]:
        """
        Analyze a batch of images for damage detection using asyncio and batching.

        Args:
            images: List of (image_path, image_bytes) tuples
            batch_size: Number of images to process concurrently in a batch

        Returns:
            List of damage analysis results
        """
        semaphore = asyncio.Semaphore(batch_size)

        async def analyze_one(image_path, image_bytes):
            try:
                # Run the sync analyze_single_image in a thread to avoid blocking
                async with semaphore:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, self.analyze_single_image, image_path, image_bytes
                    )
                    if self.debug:
                        logger.info(f"Damage analysis result: {result}")
                    return result
            except Exception as e:
                logger.error(f"Error analyzing image {image_path}: {str(e)}")
                return DamageAnalysis(
                    image_path=image_path,
                    has_damage=False,
                    area=DamageArea.UNKNOWN,
                    severity=DamageSeverity.NONE,
                    quality_score=0.0,
                    confidence=0.0,
                    damage_indicators=[],
                    error=str(e)
                )

        tasks = [analyze_one(image_path, image_bytes) for image_path, image_bytes in images]
        results = await asyncio.gather(*tasks)
        return results

    def analyze_single_image(self, image_path: str, image_bytes: bytes) -> DamageAnalysis:
        """
        Classify wind damage in an image using Gemini Vision API.
        
        Args:
            image_path: Path of the image
            image_bytes: Image bytes data
            
        Returns:
            Dict containing damage classification results
        """
        try:
            # Prepare prompt for Gemini
            prompt = self._create_analysis_prompt()
            
            # Analyze with Gemini
            response = self._analyze_with_gemini(image_url=image_path, prompt=prompt)

            damage_analysis = DamageAnalysis(
                image_path=image_path,
                has_damage=response.has_damage,
                area=DamageArea(response.location),
                severity=DamageSeverity(response.severity),
                quality_score=0.0,
                confidence=response.confidence,
                damage_indicators=[
                    DamageIndicator(
                        type=indicator.type,
                        confidence=indicator.confidence,
                        severity_weight=indicator.severity_weight
                    )
                    for indicator in response.damage_indicators
                ],
                error=None,
                notes=response.notes
            )
            return damage_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing image {image_path}: {str(e)}")
            return DamageAnalysis(
                image_path=image_path,
                has_damage=False,
                area=DamageArea.UNKNOWN,
                severity=DamageSeverity.NONE,
                quality_score=0.0,
                confidence=0.0,
                damage_indicators=[],
                error=str(e)
            )
    
    def _create_analysis_prompt(self) -> str:
        """Create a detailed prompt for wind damage analysis."""
        return """
        You are an expert building inspector specializing in wind damage assessment. Analyze this image for wind-related damage to buildings and property structures.

        CRITICAL INSTRUCTIONS:
        - Examine the image systematically from top to bottom, left to right
        - Look for wind-specific damage patterns that distinguish from other types of damage
        - Consider the context and scale of damage relative to the building size
        - Assess both visible damage and potential hidden structural issues
        - Be conservative in severity assessment - when in doubt, choose the lower severity level

        WIND DAMAGE INDICATORS TO LOOK FOR:
        - Uplifted or missing roof shingles (wind can lift shingles from edges)
        - Displaced or torn siding panels
        - Broken or missing gutters and downspouts
        - Cracked or shattered windows (especially on windward side)
        - Damaged garage doors or carports
        - Fallen tree branches or debris on structures
        - Structural displacement or leaning
        - Missing or damaged roof vents, chimneys, or antennas
        - Water intrusion signs (indicating roof damage)
        - Bent or twisted metal components

        SEVERITY ASSESSMENT GUIDELINES:
        - 0 (None): No visible damage, building appears intact
        - 1 (Minor): Cosmetic damage only - loose shingles, minor siding damage, small dents
        - 2 (Moderate): Multiple areas affected, some structural concerns, significant repair needed
        - 3 (Significant): Major structural issues, extensive damage, safety concerns
        - 4 (Severe): Critical structural damage, building may be unsafe, extensive reconstruction needed

        LOCATION CLASSIFICATION:
        - roof: Any damage to roof structure, shingles, flashing, chimneys, vents
        - attic: Any damage to attic structure, insulation, framing, roof sheathing
        - siding: Exterior wall coverings, trim, fascia boards
        - garage: Garage doors, carports, attached garage structures
        - windows: Window glass, frames, screens, window trim
        - gutters: Gutter systems, downspouts, drainage components
        - unknown: Other building components not fitting above categories

        CONFIDENCE SCORING:
        - 0.9-1.0: Clear, unambiguous damage with high certainty
        - 0.7-0.8: Clear damage but some uncertainty about extent
        - 0.5-0.6: Visible damage but unclear if wind-related
        - 0.3-0.4: Possible damage but image quality or angle limits assessment
        - 0.1-0.2: Very unclear, poor image quality or angle

        DAMAGE INDICATOR TYPES:
        - damage: General structural damage
        - broken: Fractured or shattered components
        - cracked: Visible cracks in materials
        - torn: Ripped or torn materials
        - missing: Completely absent components
        - debris: Loose materials or wreckage
        - destruction: Extensive structural failure
        - wreckage: Severe structural collapse
        - ruins: Complete structural failure

        SEVERITY WEIGHT (0-10):
        - 1-2: Minor cosmetic damage
        - 3-4: Moderate structural damage
        - 5-6: Significant structural concerns
        - 7-8: Major structural damage
        - 9-10: Critical structural failure

        NOTES:
        - Provide a note for the analysis, including any observations that are not covered by the other fields.

        RESPONSE FORMAT (JSON only):
        {
            "has_damage": true/false,
            "location": "roof|attic|siding|garage|windows|gutters|unknown",
            "severity": 0-4,
            "confidence": 0.0-1.0,
            "damage_indicators": [
                {
                    "type": "damage|broken|cracked|torn|missing|debris|destruction|wreckage|ruins",
                    "confidence": 0.0-1.0,
                    "severity_weight": 0-10
                }
            ],
            "notes": "Notes about the analysis"
        }

        IMPORTANT: Return ONLY valid JSON. No explanations, no additional text.
        """
    
    def _analyze_with_gemini(self, image_url: str, prompt: str) -> DamageAnalysisGeminiOutput:
        """Send image and prompt to Gemini Vision API."""
        try:
            system_message = {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
            user_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this image for wind damage to a building or property. Provide a detailed assessment in the following JSON format",
                    },
                    {
                        "type": "image_url",
                        "image_url": image_url,
                    },
                ],
            }
            response = self.chain.invoke([system_message, user_message])
            print(response)
            if response:
                return response
            else:
                logger.warning("Empty response from Gemini API")
                return DamageAnalysisGeminiOutput(
                    has_damage=False,
                    location=DamageArea.UNKNOWN,
                    severity=DamageSeverity.NONE,
                    confidence=0.0,
                    damage_indicators=[],
                    notes=""
                )
                
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Gemini API error: {str(e)}")
            return DamageAnalysisGeminiOutput(
                has_damage=False,
                location=DamageArea.UNKNOWN,
                severity=DamageSeverity.NONE,
                confidence=0.0,
                damage_indicators=[],
                notes=""
            )
    
    # def validate_damage_confidence(self, classification: Dict[str, Any]) -> bool:
    #     """
    #     Validate if the damage classification is confident enough to be reliable.
        
    #     Args:
    #         classification: Damage classification result
            
    #     Returns:
    #         True if classification is reliable, False otherwise
    #     """
    #     # Check confidence threshold
    #     if classification['confidence'] < 0.6:
    #         return False
        
    #     # Check if damage is detected but severity is 0 (inconsistent)
    #     if classification['damage_detected'] and classification['severity'] == 0:
    #         return False
        
    #     # Check if no damage but severity > 0 (inconsistent)
    #     if not classification['damage_detected'] and classification['severity'] > 0:
    #         return False
        
    #     return True

if __name__ == "__main__":
    detector = DamageDetectorGemini()
    result = detector.analyze_single_image("https://ca-wa-public-images.s3.us-east-1.amazonaws.com/83-lin-tong-5032-photos-04-02-2025-002418/item_3ac502f6-984f-4437-a9b8-400d10255f7a.jpg", "test_images/test_image.jpg")
    print(result)