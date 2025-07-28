"""
Aggregation utilities for Wind-Damage Photo Aggregator
Handles damage aggregation, severity calculation, and data gap analysis
"""

from typing import List, Dict
from collections import defaultdict

from src.schemas import (
    DamageAnalysis, DamageAreaInfo, DamageArea, DamageSeverity,
    DamageResult
)

class DamageAggregator:
    """
    Aggregates damage analysis results by area with business rules
    """
    
    def __init__(self):
        """Initialize aggregator with configuration"""
        self.confirmation_threshold = 2  # Minimum photos for damage confirmation
        self.severity_threshold = DamageSeverity.MODERATE  # Minimum severity for confirmation
        self.critical_areas = {DamageArea.ROOF, DamageArea.SIDING}
        self.max_representative_images = 3
    
    def aggregate_damage_by_area(self, damage_results: DamageResult) -> List[DamageAreaInfo]:
        """
        Aggregate damage results by area with confirmation rules
        
        Rules:
        - Group by DamageArea
        - Confirm damage when >= 2 photos show severity >= 2
        - Calculate weighted average severity
        - Select representative images (highest quality)
        
        Args:
            damage_results: List of damage analysis results
            
        Returns:
            List of aggregated damage area information
        """
        if not damage_results:
            return []
        
        # Group results by area
        area_groups = self._group_by_area(damage_results)
        
        aggregated_areas = []
        
        for area, results in area_groups.items():
            if area == DamageArea.UNKNOWN:
                continue  # Skip unknown areas
            
            area_info = self._process_area(area, results)
            if area_info:
                aggregated_areas.append(area_info)
        
        return aggregated_areas
    
    def _group_by_area(self, damage_results: DamageResult) -> Dict[DamageArea, List[DamageAnalysis]]:
        """Group damage results by area"""
        area_groups: Dict[DamageArea, List[DamageAnalysis]] = defaultdict(list)
        
        for result in damage_results:
            area_groups[result.area].append(result)
        
        return dict(area_groups)
    
    def _process_area(self, area: DamageArea, results: List[DamageAnalysis]) -> DamageAreaInfo:
        """Process a single area's damage results"""
        # Filter results with damage
        damage_results = [r for r in results if r.has_damage]
        
        # Check confirmation rule
        damage_confirmed = self._check_damage_confirmation(damage_results)
        
        # Calculate average severity
        avg_severity = self._calculate_area_severity(damage_results)
        
        # Select representative images
        representative_images = self._select_representative_images(damage_results)
        
        # Generate notes
        notes = self._generate_area_notes(area, damage_results)
        
        return DamageAreaInfo(
            area=area,
            damage_confirmed=damage_confirmed,
            primary_peril="wind",
            count=len(damage_results),
            avg_severity=round(avg_severity, 1),
            representative_images=representative_images,
            notes=notes
        )
    
    def _check_damage_confirmation(self, damage_results: List[DamageAnalysis]) -> bool:
        """Check if damage is confirmed based on business rules"""
        if len(damage_results) < self.confirmation_threshold:
            return False
        
        # Count high severity results
        high_severity_count = sum(
            1 for r in damage_results 
            if r.severity >= self.severity_threshold
        )
        
        return high_severity_count >= self.confirmation_threshold
    
    def _calculate_area_severity(self, damage_results: List[DamageAnalysis]) -> float:
        """Calculate weighted average severity for an area"""
        if not damage_results:
            return 0.0
        
        # Calculate weighted average by quality score
        total_weight = sum(r.quality_score for r in damage_results)
        
        if total_weight > 0:
            avg_severity = sum(r.severity * r.quality_score for r in damage_results) / total_weight
        else:
            # Fallback to simple average
            avg_severity = sum(r.severity for r in damage_results) / len(damage_results)
        
        return avg_severity
    
    def _select_representative_images(self, damage_results: List[DamageAnalysis]) -> List[str]:
        """Select representative images (highest quality)"""
        if not damage_results:
            return []
        
        # Sort by quality score and take top images
        sorted_results = sorted(damage_results, key=lambda x: x.quality_score, reverse=True)
        return [r.image_path for r in sorted_results[:self.max_representative_images]]
    
    def _generate_area_notes(self, area: DamageArea, damage_results: List[DamageAnalysis]) -> str:
        """Generate descriptive notes for a damage area"""
        if not damage_results:
            return f"No damage detected in {area}"
        
        # Aggregate notes from all damage analyses for this area
        notes_list = []
        for r in damage_results:
            if hasattr(r, "notes") and r.notes:
                notes_list.append(r.notes)
        if notes_list:
            # Concatenate unique notes, separated by semicolons
            unique_notes = list(dict.fromkeys(notes_list))
            return "; ".join(unique_notes)
        else:
            return f"Damage detected in {area}"
    
    def _count_damage_types(self, damage_results: List[DamageAnalysis]) -> Dict[str, int]:
        """Count occurrences of different damage types"""
        damage_types = defaultdict(int)
        
        for result in damage_results:
            for indicator in result.damage_indicators:
                damage_types[indicator.type] += 1
        
        return dict(damage_types)

class SeverityCalculator:
    """Calculates overall damage severity across all areas"""
    
    def calculate_overall_severity(self, damage_results: DamageResult) -> float:
        """
        Calculate weighted average severity across all areas
        
        Args:
            damage_results: List of damage analysis results
            
        Returns:
            Overall damage severity (0-4 scale)
        """
        if not damage_results:
            return 0.0
        
        # Filter results with damage
        damage_results_filtered = [r for r in damage_results if r.has_damage]
        
        if not damage_results_filtered:
            return 0.0
        
        # Calculate weighted average by quality score
        total_weight = sum(r.quality_score for r in damage_results_filtered)
        
        if total_weight == 0:
            # Fallback to simple average
            avg_severity = sum(r.severity for r in damage_results_filtered) / len(damage_results_filtered)
        else:
            # Weighted average
            avg_severity = sum(r.severity * r.quality_score for r in damage_results_filtered) / total_weight
        
        return round(avg_severity, 1)

class DataGapAnalyzer:
    """Analyzes data gaps and coverage issues"""
    
    def __init__(self):
        """Initialize analyzer with configuration"""
        self.critical_areas = {DamageArea.ROOF, DamageArea.ATTIC, DamageArea.SIDING, DamageArea.GARAGE, DamageArea.WINDOWS, DamageArea.GUTTERS}
        self.min_photos_per_area = 2
        self.min_total_areas = 2
    
    def identify_data_gaps(self, areas: List[DamageAreaInfo]) -> List[str]:
        """
        Identify missing data areas and coverage gaps
        
        Args:
            areas: List of analyzed damage areas
            
        Returns:
            List of data gap descriptions
        """
        gaps = []
        
        # Check for missing critical areas
        analyzed_areas = {area.area for area in areas}
        missing_critical = self.critical_areas - analyzed_areas
        
        for area in missing_critical:
            gaps.append(f"No {area.value} photos")
        
        # Check for areas with insufficient photos
        low_confidence_areas = [
            area for area in areas 
            if area.count < self.min_photos_per_area
        ]
        
        for area in low_confidence_areas:
            gaps.append(f"Insufficient {area.area} photos ({area.count} images)")
        
        # Check for areas with no damage confirmation
        unconfirmed_areas = [
            area for area in areas 
            if not area.damage_confirmed and area.count > 0
        ]
        
        for area in unconfirmed_areas:
            gaps.append(f"Unconfirmed {area.area} damage (severity too low)")
        
        # Check for overall coverage
        total_areas = len(areas)
        if total_areas < self.min_total_areas:
            gaps.append("Limited area coverage - need more photos")
        
        return gaps

class ConfidenceCalculator:
    """Calculates overall confidence score"""
    
    def calculate_confidence(self, damage_results: DamageResult) -> float:
        """
        Calculate overall confidence score based on multiple factors
        
        Args:
            damage_results: List of damage analysis results
            
        Returns:
            Confidence score between 0 and 1
        """
        if not damage_results:
            return 0.0
        
        # Calculate confidence factors
        total_images = len(damage_results)
        damage_images = len([r for r in damage_results if r.has_damage])
        
        # Quality factor (average quality score)
        avg_quality = sum(r.quality_score for r in damage_results) / total_images
        
        # Coverage factor (how many areas are covered)
        unique_areas = len(set(r.area for r in damage_results if r.area != DamageArea.UNKNOWN))
        coverage_factor = min(1.0, unique_areas / 3.0)  # Normalize to 3 areas max
        
        # Consistency factor (how consistent are the results)
        if damage_images > 0:
            consistency_factor = damage_images / total_images
        else:
            consistency_factor = 0.5  # Neutral if no damage detected
        
        # Average confidence from individual analyses
        avg_confidence = sum(r.confidence for r in damage_results) / total_images
        
        # Weighted combination
        final_confidence = (
            avg_quality * 0.3 +
            coverage_factor * 0.2 +
            consistency_factor * 0.2 +
            avg_confidence * 0.3
        )
        
        return round(final_confidence, 2) 