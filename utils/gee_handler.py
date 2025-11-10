import os
import json
import numpy as np
from datetime import datetime, timedelta

class GEEHandler:
    def __init__(self):
        self.gee_service_account = os.getenv('GEE_SERVICE_ACCOUNT', '')
        self.gee_private_key = os.getenv('GEE_PRIVATE_KEY', '')
        self.initialized = False
        
    def initialize(self):
        if not self.gee_service_account or not self.gee_private_key:
            print("Warning: GEE credentials not found. Using simulated data.")
            self.initialized = False
            return False
            
        try:
            import ee
            credentials = ee.ServiceAccountCredentials(
                self.gee_service_account,
                key_data=self.gee_private_key
            )
            ee.Initialize(credentials)
            self.initialized = True
            print("Google Earth Engine initialized successfully")
            return True
        except Exception as e:
            print(f"GEE initialization failed: {str(e)}. Using simulated data.")
            self.initialized = False
            return False
    
    def get_ndvi_data(self, bounds, start_date, end_date):
        if not self.initialized:
            return self._generate_simulated_ndvi_data(bounds)
        
        try:
            import ee
            geometry = ee.Geometry.Rectangle(bounds)
            
            collection = ee.ImageCollection('COPERNICUS/S2_SR') \
                .filterBounds(geometry) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            
            def calculate_ndvi(image):
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                return image.addBands(ndvi)
            
            ndvi_collection = collection.map(calculate_ndvi)
            
            ndvi_composite = ndvi_collection.select('NDVI').median()
            
            ndvi_stats = ndvi_composite.reduceRegion(
                reducer=ee.Reducer.percentile([25, 50, 75]),
                geometry=geometry,
                scale=10,
                maxPixels=1e9
            )
            
            stats = ndvi_stats.getInfo()
            
            return {
                'ndvi_p25': stats.get('NDVI_p25', 0.3),
                'ndvi_median': stats.get('NDVI_p50', 0.5),
                'ndvi_p75': stats.get('NDVI_p75', 0.7),
                'image_count': ndvi_collection.size().getInfo(),
                'bounds': bounds
            }
        except Exception as e:
            print(f"Error fetching GEE data: {str(e)}. Using simulated data.")
            return self._generate_simulated_ndvi_data(bounds)
    
    def _generate_simulated_ndvi_data(self, bounds):
        np.random.seed(hash(str(bounds)) % 2**32)
        
        base_ndvi = np.random.uniform(0.3, 0.7)
        variation = np.random.uniform(0.1, 0.2)
        
        return {
            'ndvi_p25': max(0, min(1, base_ndvi - variation)),
            'ndvi_median': max(0, min(1, base_ndvi)),
            'ndvi_p75': max(0, min(1, base_ndvi + variation)),
            'image_count': np.random.randint(5, 20),
            'bounds': bounds,
            'simulated': True
        }
    
    def extract_features(self, ndvi_data):
        features = []
        
        features.append(ndvi_data.get('ndvi_median', 0.5))
        features.append(ndvi_data.get('ndvi_p25', 0.3))
        features.append(ndvi_data.get('ndvi_p75', 0.7))
        features.append(ndvi_data.get('ndvi_p75', 0.7) - ndvi_data.get('ndvi_p25', 0.3))
        
        np.random.seed(hash(str(ndvi_data.get('bounds', []))) % 2**32)
        features.extend(np.random.rand(8).tolist())
        
        return np.array(features).reshape(1, -1)
