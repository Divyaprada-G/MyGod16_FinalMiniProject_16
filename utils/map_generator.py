import folium
import json
import os
import numpy as np
import random

class MapGenerator:
    def __init__(self):
        self.mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN', '')
        
    def create_crop_map(self, center, crop_data, zoom=10):
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles='OpenStreetMap'
        )
        
        if crop_data:
            for item in crop_data:
                folium.CircleMarker(
                    location=center,
                    radius=10,
                    popup=f"{item['crop_name']}: {item['percentage']}%",
                    color=item['color'],
                    fill=True,
                    fillColor=item['color'],
                    fillOpacity=0.6
                ).add_to(m)
        
        return m._repr_html_()
    
    def generate_geojson_bounds(self, bounds):
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [bounds[1], bounds[0]],
                    [bounds[3], bounds[0]],
                    [bounds[3], bounds[2]],
                    [bounds[1], bounds[2]],
                    [bounds[1], bounds[0]]
                ]]
            },
            "properties": {}
        }
    
    def generate_crop_map_geojson(self, bounds, area_statistics, crop_predictor):
        min_lat, min_lon, max_lat, max_lon = bounds
        
        random.seed(hash(str(bounds)) % 2**32)
        np.random.seed(hash(str(bounds)) % 2**32)
        
        grid_size = 8
        lat_step = (max_lat - min_lat) / grid_size
        lon_step = (max_lon - min_lon) / grid_size
        
        crop_weights = []
        crop_ids = []
        for stat in area_statistics:
            crop_weights.append(stat['percentage'])
            crop_ids.append(stat['crop_id'])
        
        total_weight = sum(crop_weights)
        crop_weights = [w / total_weight for w in crop_weights]
        
        features = []
        
        for i in range(grid_size):
            for j in range(grid_size):
                lat1 = min_lat + i * lat_step
                lat2 = min_lat + (i + 1) * lat_step
                lon1 = min_lon + j * lon_step
                lon2 = min_lon + (j + 1) * lon_step
                
                crop_id = np.random.choice(crop_ids, p=crop_weights)
                crop_info = crop_predictor.get_crop_info(crop_id)
                
                lat_offset = (np.random.random() - 0.5) * lat_step * 0.3
                lon_offset = (np.random.random() - 0.5) * lon_step * 0.3
                
                polygon_coords = [
                    [lon1 + lon_offset, lat1 + lat_offset],
                    [lon2 + lon_offset, lat1 + lat_offset],
                    [lon2 + lon_offset, lat2 + lat_offset],
                    [lon1 + lon_offset, lat2 + lat_offset],
                    [lon1 + lon_offset, lat1 + lat_offset]
                ]
                
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon_coords]
                    },
                    "properties": {
                        "crop_id": int(crop_id),
                        "crop_name": crop_info['name'],
                        "color": crop_info['color']
                    }
                }
                features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features
        }
