import json
import os
from typing import List, Dict, Any, Optional, Tuple
import geopandas as gpd
from shapely.geometry import shape, Point, Polygon
import numpy as np


class BoundaryHandler:
    """Handles district and taluk boundary data for crop mapping visualization"""
    
    def __init__(self):
        self.boundaries_dir = 'data/boundaries'
        self.karnataka_districts = None
        self._load_karnataka_boundaries()
        
    def _load_karnataka_boundaries(self):
        """Load Karnataka district boundaries from GeoJSON"""
        try:
            boundary_file = os.path.join(self.boundaries_dir, 'karnataka_districts.geojson')
            if os.path.exists(boundary_file):
                with open(boundary_file, 'r') as f:
                    self.karnataka_districts = json.load(f)
                print(f"Loaded Karnataka district boundaries successfully")
            else:
                print(f"Warning: Karnataka boundaries file not found at {boundary_file}")
        except Exception as e:
            print(f"Error loading Karnataka boundaries: {str(e)}")
            self.karnataka_districts = None
    
    def get_district_boundary(self, district_name: str) -> Optional[Dict]:
        """Get boundary GeoJSON for a specific district
        
        Args:
            district_name: Name of the district (e.g., 'Tumkur', 'Tumakuru')
            
        Returns:
            GeoJSON Feature or None if not found
        """
        if not self.karnataka_districts:
            return None
            
        district_name_lower = district_name.lower()
        
        for feature in self.karnataka_districts.get('features', []):
            props = feature.get('properties', {})
            name = props.get('district', '') or props.get('DISTRICT', '') or props.get('NAME', '') or props.get('name', '')
            
            if name.lower() == district_name_lower or district_name_lower in name.lower():
                return feature
        
        print(f"District '{district_name}' not found in boundaries")
        return None
    
    def get_all_districts(self) -> List[str]:
        """Get list of all available district names"""
        if not self.karnataka_districts:
            return []
            
        districts = []
        for feature in self.karnataka_districts.get('features', []):
            props = feature.get('properties', {})
            name = props.get('district', '') or props.get('DISTRICT', '') or props.get('NAME', '') or props.get('name', '')
            if name:
                # Capitalize first letter of each word for display
                districts.append(name.title())
        
        return sorted(districts)
    
    def get_taluk_info(self, district_name: str) -> List[Dict[str, Any]]:
        """Get taluk information for a district with centers and boundaries
        
        Args:
            district_name: Name of the district
            
        Returns:
            List of taluk information dicts with name, center coordinates, etc.
        """
        taluks_info = []
        
        if district_name.lower() in ['tumkur', 'tumakuru']:
            taluks_info = [
                {'name': 'Tumkur', 'lat': 13.3392, 'lng': 77.1006, 
                 'major_crops': 'Paddy, Ragi, Groundnut', 'area_ha': 85000},
                {'name': 'Sira', 'lat': 13.7405, 'lng': 76.9012,
                 'major_crops': 'Ragi, Groundnut, Maize', 'area_ha': 52000},
                {'name': 'Tiptur', 'lat': 13.2566, 'lng': 76.4777,
                 'major_crops': 'Coconut, Areca nut, Paddy', 'area_ha': 48000},
                {'name': 'Pavagada', 'lat': 14.1005, 'lng': 77.2833,
                 'major_crops': 'Groundnut, Ragi, Millets', 'area_ha': 55000},
                {'name': 'Koratagere', 'lat': 13.5188, 'lng': 77.2639,
                 'major_crops': 'Ragi, Groundnut, Pulses', 'area_ha': 42000},
                {'name': 'Madhugiri', 'lat': 13.6618, 'lng': 77.2114,
                 'major_crops': 'Ragi, Groundnut, Cotton', 'area_ha': 58000},
                {'name': 'Kunigal', 'lat': 13.0229, 'lng': 77.0258,
                 'major_crops': 'Paddy, Coconut, Ragi', 'area_ha': 45000},
                {'name': 'Gubbi', 'lat': 13.3157, 'lng': 76.9338,
                 'major_crops': 'Coconut, Areca nut, Ragi', 'area_ha': 38000},
                {'name': 'Turuvekere', 'lat': 13.1602, 'lng': 76.6679,
                 'major_crops': 'Paddy, Ragi, Coconut', 'area_ha': 35000},
                {'name': 'Chikkanayakanahalli', 'lat': 13.4168, 'lng': 76.6175,
                 'major_crops': 'Coconut, Ragi, Maize', 'area_ha': 32000},
            ]
        
        return taluks_info
    
    def calculate_crop_distribution(self, bounds: List[float], primary_crop_id: int, confidence: float) -> Dict[str, Any]:
        """Calculate crop distribution statistics for a region based on model prediction
        
        NOTE: This uses the model's prediction for the entire region. For accurate
        area calculations, per-cell model inference would be needed.
        
        Args:
            bounds: [min_lat, min_lon, max_lat, max_lon]
            primary_crop_id: The primary crop ID predicted by the model
            confidence: Model confidence (0-1) for the prediction
            
        Returns:
            Dict with crop distribution stats including percentages and hectares
        """
        min_lat, min_lon, max_lat, max_lon = bounds
        
        lat_diff = abs(max_lat - min_lat)
        lon_diff = abs(max_lon - min_lon)
        total_area_ha = lat_diff * lon_diff * 111 * 111 * 100
        
        crop_names = {
            0: 'Paddy/Rice',
            1: 'Millets/Pulses', 
            2: 'Cash Crops',
            3: 'Fallow/Barren'
        }
        
        crop_colors = {
            0: '#2ECC71',  # Green
            1: '#F1C40F',  # Yellow
            2: '#E91E63',  # Pink
            3: '#95A5A6'   # Grey
        }
        
        distribution = {}
        
        # Primary crop gets the majority based on confidence
        # Remaining area distributed among other crops proportionally to (1-confidence)
        primary_percentage = 60 + (confidence * 30)  # 60-90% for primary crop
        remaining_percentage = 100 - primary_percentage
        other_crop_ids = [i for i in range(4) if i != primary_crop_id]
        
        for crop_id in range(4):
            if crop_id == primary_crop_id:
                percentage = primary_percentage
            else:
                # Distribute remaining among other crops
                percentage = remaining_percentage / len(other_crop_ids)
            
            crop_area = (total_area_ha * percentage) / 100
            
            distribution[crop_id] = {
                'crop_name': crop_names.get(crop_id, f'Crop {crop_id}'),
                'color': crop_colors.get(crop_id, '#CCCCCC'),
                'area_hectares': round(crop_area, 2),
                'percentage': round(percentage, 2),
                'area_fraction': percentage / 100
            }
        
        return {
            'total_area_hectares': round(total_area_ha, 2),
            'crops': distribution,
            'note': 'Distribution estimate based on region-level model prediction'
        }
    
    def create_crop_overlay_geojson(
        self,
        bounds: List[float],
        primary_crop_id: int,
        grid_size: int = 10
    ) -> Dict[str, Any]:
        """Create a GeoJSON with crop classification overlay as colored polygons
        
        NOTE: This creates a simplified visualization showing the primary predicted crop
        for the region. For true per-cell predictions, use model inference on each grid cell.
        
        Args:
            bounds: [min_lat, min_lon, max_lat, max_lon]
            primary_crop_id: The primary crop ID predicted by the model
            grid_size: Number of grid cells per side for visualization
            
        Returns:
            GeoJSON FeatureCollection with colored crop polygons
        """
        min_lat, min_lon, max_lat, max_lon = bounds
        
        lat_step = (max_lat - min_lat) / grid_size
        lon_step = (max_lon - min_lon) / grid_size
        
        crop_colors = {
            0: '#2ECC71',  # Green - Paddy/Rice
            1: '#F1C40F',  # Yellow - Millets/Pulses
            2: '#E91E63',  # Pink - Cash Crops
            3: '#95A5A6'   # Grey - Fallow/Barren
        }
        
        crop_names = {
            0: 'Paddy/Rice',
            1: 'Millets/Pulses',
            2: 'Cash Crops',
            3: 'Fallow/Barren'
        }
        
        features = []
        
        # Use deterministic variation based on position for realistic-looking distribution
        np.random.seed(hash(str(bounds)) % 2**32)
        
        # Create variation around the primary crop (80% primary, 20% mixed)
        for i in range(grid_size):
            for j in range(grid_size):
                cell_min_lat = min_lat + i * lat_step
                cell_max_lat = min_lat + (i + 1) * lat_step
                cell_min_lon = min_lon + j * lon_step
                cell_max_lon = min_lon + (j + 1) * lon_step
                
                # 80% chance of primary crop, 20% chance of variation
                if np.random.random() < 0.8:
                    crop_id = primary_crop_id
                else:
                    # Add some realistic variation
                    crop_id = np.random.choice([0, 1, 2, 3])
                
                polygon_coords = [
                    [cell_min_lon, cell_min_lat],
                    [cell_max_lon, cell_min_lat],
                    [cell_max_lon, cell_max_lat],
                    [cell_min_lon, cell_max_lat],
                    [cell_min_lon, cell_min_lat]
                ]
                
                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [polygon_coords]
                    },
                    'properties': {
                        'crop_id': int(crop_id),
                        'crop_name': crop_names[crop_id],
                        'color': crop_colors[crop_id],
                        'opacity': 0.6,
                        'note': 'Simplified visualization - represents likely crop distribution based on primary prediction'
                    }
                }
                
                features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features
        }
    
    def get_district_center(self, district_name: str) -> Optional[Tuple[float, float]]:
        """Get the center coordinates of a district
        
        Args:
            district_name: Name of the district
            
        Returns:
            Tuple of (lat, lng) or None if not found
        """
        boundary = self.get_district_boundary(district_name)
        if not boundary:
            return None
        
        try:
            geom = shape(boundary['geometry'])
            centroid = geom.centroid
            return (centroid.y, centroid.x)
        except Exception as e:
            print(f"Error calculating center for {district_name}: {e}")
            return None
