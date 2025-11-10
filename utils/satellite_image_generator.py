import math
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import os
from typing import List, Tuple, Dict, Any
import mercantile
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import threading

class SatelliteImageGenerator:
    def __init__(self):
        self.tile_size = 256
        self.satellite_tile_url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        self._thread_local = threading.local()
        
    def _get_session(self):
        """Get thread-local session with connection pooling and retry logic
        
        Thread-local approach ensures each ThreadPoolExecutor worker has its own
        requests.Session (avoiding concurrent session access issues) while still
        benefiting from connection pooling and retry logic. The global @lru_cache
        on _fetch_tile_cached() continues to serve cached tiles across all threads,
        bypassing session access on cache hits for maximum performance.
        """
        if not hasattr(self._thread_local, 'session'):
            session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=retry_strategy,
                pool_block=False
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            self._thread_local.session = session
        return self._thread_local.session
        
    def generate_annotated_satellite_image(
        self,
        bounds: List[float],
        crop_map_data: Dict[str, Any],
        area_statistics: List[Dict],
        location_labels: List[Dict] = None,
        width: int = 2048,
        height: int = 1536
    ) -> Image.Image:
        min_lat, min_lon, max_lat, max_lon = bounds
        
        zoom = self._calculate_zoom_level(min_lat, min_lon, max_lat, max_lon, width, height)
        zoom = min(zoom, 15)
        
        satellite_base = self._fetch_satellite_tiles(min_lat, min_lon, max_lat, max_lon, zoom, width, height)
        
        overlay = Image.new('RGBA', satellite_base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        self._draw_crop_areas(overlay, draw, crop_map_data, bounds, satellite_base.size)
        
        self._draw_boundary(draw, bounds, bounds, satellite_base.size)
        
        if location_labels:
            self._draw_location_labels(draw, location_labels, bounds, satellite_base.size)
        
        result = Image.alpha_composite(satellite_base.convert('RGBA'), overlay)
        
        legend_height = 200
        final_image = Image.new('RGBA', (result.width, result.height + legend_height), (255, 255, 255, 255))
        final_image.paste(result, (0, 0))
        
        self._draw_legend(final_image, area_statistics, result.height)
        
        return final_image
    
    def _calculate_zoom_level(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float, width: int, height: int) -> int:
        lat_diff = abs(max_lat - min_lat)
        lon_diff = abs(max_lon - min_lon)
        
        for zoom in range(18, 0, -1):
            lat_span = 180 / (2 ** zoom)
            lon_span = 360 / (2 ** zoom)
            
            tiles_x = lon_diff / lon_span
            tiles_y = lat_diff / lat_span
            
            if tiles_x * self.tile_size <= width and tiles_y * self.tile_size <= height:
                return zoom
        
        return 10
    
    @lru_cache(maxsize=500)
    def _fetch_tile_cached(self, z, y, x):
        """Fetch and cache individual tile"""
        try:
            tile_url = self.satellite_tile_url.format(z=z, y=y, x=x)
            session = self._get_session()
            response = session.get(tile_url, timeout=3)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            print(f"Error fetching tile z={z}, y={y}, x={x}: {e}")
        return None
    
    def _fetch_single_tile(self, tile, min_x, min_y):
        try:
            tile_content = self._fetch_tile_cached(tile.z, tile.y, tile.x)
            if tile_content:
                tile_image = Image.open(io.BytesIO(tile_content))
                x_offset = (tile.x - min_x) * self.tile_size
                y_offset = (tile.y - min_y) * self.tile_size
                return (tile_image, x_offset, y_offset)
        except Exception as e:
            print(f"Error processing tile {tile}: {e}")
        return None
    
    def _fetch_satellite_tiles(self, min_lat: float, min_lon: float, max_lat: float, max_lon: float, zoom: int, target_width: int, target_height: int) -> Image.Image:
        tiles = list(mercantile.tiles(min_lon, min_lat, max_lon, max_lat, zooms=zoom))
        
        if not tiles:
            return Image.new('RGB', (target_width, target_height), (200, 200, 200))
        
        if len(tiles) > 50:
            print(f"Warning: Limiting tiles from {len(tiles)} to 50 for faster generation")
            tiles = tiles[:50]
        
        min_x = min(t.x for t in tiles)
        max_x = max(t.x for t in tiles)
        min_y = min(t.y for t in tiles)
        max_y = max(t.y for t in tiles)
        
        grid_width = (max_x - min_x + 1) * self.tile_size
        grid_height = (max_y - min_y + 1) * self.tile_size
        composite = Image.new('RGB', (grid_width, grid_height), (200, 200, 200))
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self._fetch_single_tile, tile, min_x, min_y): tile for tile in tiles}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    tile_image, x_offset, y_offset = result
                    composite.paste(tile_image, (x_offset, y_offset))
        
        bounds_nw = mercantile.ul(min_x, min_y, zoom)
        bounds_se = mercantile.ul(max_x + 1, max_y + 1, zoom)
        
        lon_range = bounds_se.lng - bounds_nw.lng
        lat_range = bounds_nw.lat - bounds_se.lat
        
        crop_x1 = int(((min_lon - bounds_nw.lng) / lon_range) * grid_width)
        crop_y1 = int(((bounds_nw.lat - max_lat) / lat_range) * grid_height)
        crop_x2 = int(((max_lon - bounds_nw.lng) / lon_range) * grid_width)
        crop_y2 = int(((bounds_nw.lat - min_lat) / lat_range) * grid_height)
        
        crop_x1 = max(0, min(crop_x1, grid_width))
        crop_y1 = max(0, min(crop_y1, grid_height))
        crop_x2 = max(0, min(crop_x2, grid_width))
        crop_y2 = max(0, min(crop_y2, grid_height))
        
        if crop_x2 > crop_x1 and crop_y2 > crop_y1:
            cropped = composite.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        else:
            cropped = composite
        
        if cropped.size != (target_width, target_height):
            cropped = cropped.resize((target_width, target_height), Image.Resampling.BILINEAR)
        
        return cropped
    
    def _latlon_to_pixel(self, lat: float, lon: float, bounds: List[float], image_size: Tuple[int, int]) -> Tuple[int, int]:
        min_lat, min_lon, max_lat, max_lon = bounds
        width, height = image_size
        
        x = int(((lon - min_lon) / (max_lon - min_lon)) * width)
        y = int(((max_lat - lat) / (max_lat - min_lat)) * height)
        
        return (x, y)
    
    def _draw_crop_areas(self, overlay: Image.Image, draw: ImageDraw.Draw, crop_map_data: Dict, bounds: List[float], image_size: Tuple[int, int]):
        if not crop_map_data or 'features' not in crop_map_data:
            return
        
        for feature in crop_map_data['features']:
            if feature['geometry']['type'] != 'Polygon':
                continue
            
            coords = feature['geometry']['coordinates'][0]
            color = feature['properties'].get('color', '#00FF00')
            
            polygon_points = []
            for lon, lat in coords:
                x, y = self._latlon_to_pixel(lat, lon, bounds, image_size)
                polygon_points.append((x, y))
            
            if len(polygon_points) >= 3:
                rgb_color = self._hex_to_rgb(color)
                fill_color = rgb_color + (100,)
                outline_color = rgb_color + (180,)
                
                draw.polygon(polygon_points, fill=fill_color, outline=outline_color, width=2)
    
    def _draw_boundary(self, draw: ImageDraw.Draw, region_bounds: List[float], image_bounds: List[float], image_size: Tuple[int, int]):
        min_lat, min_lon, max_lat, max_lon = region_bounds
        
        corners = [
            (min_lon, max_lat),
            (max_lon, max_lat),
            (max_lon, min_lat),
            (min_lon, min_lat),
            (min_lon, max_lat)
        ]
        
        boundary_points = []
        for lon, lat in corners:
            x, y = self._latlon_to_pixel(lat, lon, image_bounds, image_size)
            boundary_points.append((x, y))
        
        draw.line(boundary_points, fill=(255, 0, 0, 255), width=4)
    
    def _draw_location_labels(self, draw: ImageDraw.Draw, locations: List[Dict], bounds: List[float], image_size: Tuple[int, int]):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        for location in locations:
            lat = location.get('lat')
            lon = location.get('lng')
            name = location.get('name', '')
            
            if lat is None or lon is None:
                continue
            
            x, y = self._latlon_to_pixel(lat, lon, bounds, image_size)
            
            draw.ellipse([x-8, y-8, x+8, y+8], fill=(255, 0, 0, 255), outline=(255, 255, 255, 255), width=2)
            
            bbox = draw.textbbox((0, 0), name, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            label_x = x + 12
            label_y = y - text_height // 2
            
            padding = 4
            draw.rectangle(
                [label_x - padding, label_y - padding, 
                 label_x + text_width + padding, label_y + text_height + padding],
                fill=(255, 255, 255, 220),
                outline=(0, 0, 0, 255),
                width=1
            )
            
            draw.text((label_x, label_y), name, fill=(0, 0, 0, 255), font=font)
    
    def _draw_legend(self, image: Image.Image, area_statistics: List[Dict], y_offset: int):
        draw = ImageDraw.Draw(image)
        
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            title_font = ImageFont.load_default()
            font = ImageFont.load_default()
        
        legend_x = 20
        legend_y = y_offset + 20
        
        draw.text((legend_x, legend_y), "Crop Distribution Legend", fill=(0, 0, 0, 255), font=title_font)
        legend_y += 35
        
        items_per_row = 3
        item_width = (image.width - 40) // items_per_row
        
        for idx, stat in enumerate(area_statistics):
            row = idx // items_per_row
            col = idx % items_per_row
            
            x = legend_x + (col * item_width)
            y = legend_y + (row * 40)
            
            color = self._hex_to_rgb(stat['color'])
            draw.rectangle([x, y, x + 30, y + 20], fill=color, outline=(0, 0, 0, 255), width=1)
            
            text = f"{stat['crop_name']}: {stat['percentage']}% ({stat['area_hectares']} ha)"
            draw.text((x + 40, y + 2), text, fill=(0, 0, 0, 255), font=font)
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
