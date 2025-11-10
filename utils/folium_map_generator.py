"""
Enhanced Folium Map Generator for Interactive Crop Classification Visualization
Provides district/taluk boundaries, crop overlays, interactive markers, and legends

Uses dependency injection to integrate with BoundaryHandler for data sourcing.
"""

import folium
from folium import plugins
import branca.element as branca
import json
import os
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from utils.boundary_handler import BoundaryHandler


class FoliumMapGenerator:
    """Generates interactive Folium maps with enhanced crop classification visualization"""
    
    # Crop classification color scheme
    CROP_COLORS = {
        0: {'color': '#2ECC71', 'name': 'Paddy/Rice', 'emoji': '🌾'},        # Green
        1: {'color': '#F1C40F', 'name': 'Millets/Pulses', 'emoji': '🌾'},   # Yellow
        2: {'color': '#E91E63', 'name': 'Cash Crops', 'emoji': '🌾'},       # Pink
        3: {'color': '#95A5A6', 'name': 'Fallow/Barren', 'emoji': '⚪'}     # Grey
    }
    
    def __init__(self, boundary_handler: 'BoundaryHandler'):
        """
        Initialize the Folium map generator
        
        Args:
            boundary_handler: BoundaryHandler instance for accessing district/taluk data
        """
        self.boundary_handler = boundary_handler
        
    def create_interactive_map(
        self,
        district_name: str = 'Tumkur',
        crop_distribution: Optional[Dict] = None,
        crop_overlay_data: Optional[Dict] = None,
        center_lat: float = 13.34,
        center_lng: float = 77.10,
        zoom_start: int = 9
    ) -> folium.Map:
        """
        Create an interactive Folium map with district boundaries, crop overlays, and taluk markers
        
        Args:
            district_name: Name of the district (default: Tumkur)
            crop_distribution: Crop distribution statistics
            crop_overlay_data: GeoJSON data for crop classification overlay
            center_lat: Map center latitude
            center_lng: Map center longitude
            zoom_start: Initial zoom level
            
        Returns:
            Folium Map object with all interactive features
        """
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=zoom_start,
            tiles='OpenStreetMap',
            control_scale=True
        )
        
        # Add additional tile layers
        folium.TileLayer('CartoDB positron', name='Light Mode').add_to(m)
        folium.TileLayer('Esri WorldImagery', name='Satellite View').add_to(m)
        
        # Load and add district boundary
        district_boundary = self._load_district_boundary(district_name)
        if district_boundary:
            self._add_district_boundary_layer(m, district_boundary, district_name)
        
        # Add crop classification overlay if provided
        if crop_overlay_data:
            self._add_crop_overlay_layer(m, crop_overlay_data)
        
        # Add taluk markers with crop information
        self._add_taluk_markers(m, district_name)
        
        # Add custom legend with crop distribution statistics
        if crop_distribution:
            self._add_custom_legend(m, crop_distribution)
        
        # Add layer control
        folium.LayerControl(position='topright').add_to(m)
        
        # Add fullscreen button
        plugins.Fullscreen(
            position='topleft',
            title='Expand map',
            title_cancel='Exit fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        # Add mini map
        minimap = plugins.MiniMap(toggle_display=True, position='bottomleft')
        m.add_child(minimap)
        
        # Add responsive CSS and JavaScript for window resizing
        self._add_responsive_features(m)
        
        return m
    
    def _load_district_boundary(self, district_name: str) -> Optional[Dict]:
        """Load district boundary GeoJSON using BoundaryHandler"""
        try:
            # Use BoundaryHandler to get district boundary
            boundary = self.boundary_handler.get_district_boundary(district_name)
            if boundary:
                # Wrap in FeatureCollection if it's a single Feature
                if boundary.get('type') == 'Feature':
                    return {'type': 'FeatureCollection', 'features': [boundary]}
                return boundary
            return None
        except Exception as e:
            print(f"Error loading boundary for {district_name}: {e}")
            return None
    
    def _add_district_boundary_layer(
        self, 
        m: folium.Map, 
        boundary_data: Dict,
        district_name: str
    ):
        """Add district boundary layer with red dashed outline"""
        folium.GeoJson(
            boundary_data,
            name=f'{district_name} District Boundary',
            style_function=lambda feature: {
                'fillColor': 'transparent',
                'fillOpacity': 0,
                'color': '#FF0000',
                'weight': 3,
                'opacity': 0.8,
                'dashArray': '10, 5'
            },
            highlight_function=lambda feature: {
                'weight': 4,
                'color': '#FF0000',
                'opacity': 1.0
            },
            tooltip=folium.Tooltip(f'{district_name} District', sticky=True),
            popup=folium.Popup(
                f'<div style="font-size: 14px;"><b>{district_name} District</b><br>'
                f'Click to zoom to boundary</div>',
                max_width=200
            )
        ).add_to(m)
    
    def _add_crop_overlay_layer(self, m: folium.Map, crop_overlay_data: Dict):
        """Add color-coded crop classification overlay layer"""
        
        def style_function(feature):
            """Style function for crop overlay polygons"""
            props = feature.get('properties', {})
            crop_color = props.get('color', '#CCCCCC')
            return {
                'fillColor': crop_color,
                'fillOpacity': 0.6,
                'color': crop_color,
                'weight': 0.5,
                'opacity': 0.7
            }
        
        def highlight_function(feature):
            """Highlight function on hover"""
            return {
                'fillOpacity': 0.8,
                'weight': 2,
                'opacity': 1.0
            }
        
        # Add crop overlay as GeoJSON layer
        crop_layer = folium.GeoJson(
            crop_overlay_data,
            name='Crop Classification Overlay',
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=folium.GeoJsonTooltip(
                fields=['crop_name'],
                aliases=['Crop Type:'],
                style=('background-color: white; color: #333333; font-family: arial; '
                       'font-size: 12px; padding: 8px; border-radius: 5px;'),
                sticky=True
            ),
            popup=folium.GeoJsonPopup(
                fields=['crop_name', 'crop_id'],
                aliases=['Crop Type:', 'Crop ID:'],
                labels=True,
                style='background-color: white; border-radius: 5px; padding: 10px;'
            ),
            show=True
        )
        crop_layer.add_to(m)
    
    def _add_taluk_markers(self, m: folium.Map, district_name: str):
        """Add interactive markers for major taluks with crop information"""
        
        # Get taluk information from BoundaryHandler
        taluks = self.boundary_handler.get_taluk_info(district_name)
        
        if not taluks:
            print(f"No taluk information found for {district_name}")
            return
        
        # Create a feature group for taluk markers
        taluk_group = folium.FeatureGroup(name='Taluk Information Markers', show=True)
        
        for taluk in taluks:
            # Create custom icon (blue info circle)
            icon_html = f'''
            <div style="font-size: 24px; color: #2196F3;">
                <i class="fa fa-info-circle"></i>
            </div>
            '''
            
            # Calculate percentage of district area (approximate)
            district_total_area = 500000  # Approximate total area in hectares
            percentage = (taluk['area_ha'] / district_total_area) * 100
            
            # Create popup content with detailed information
            popup_html = f'''
            <div style="width: 250px; font-family: Arial, sans-serif;">
                <h4 style="margin: 0 0 10px 0; padding-bottom: 10px; border-bottom: 2px solid #2196F3; color: #2196F3;">
                    📍 {taluk['name']} Taluk
                </h4>
                <div style="margin: 8px 0;">
                    <strong style="color: #333;">Major Crops:</strong><br>
                    <span style="color: #4CAF50; font-weight: 500;">{taluk['major_crops']}</span>
                </div>
                <div style="margin: 8px 0; padding: 8px; background-color: #f5f5f5; border-radius: 4px;">
                    <strong style="color: #333;">Area Coverage:</strong><br>
                    <span style="font-size: 18px; color: #FF5722; font-weight: bold;">
                        {taluk['area_ha']:,} hectares
                    </span><br>
                    <small style="color: #666;">
                        (~{percentage:.2f}% of district)
                    </small>
                </div>
            </div>
            '''
            
            # Add marker with custom icon and popup
            folium.Marker(
                location=[taluk['lat'], taluk['lng']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"📍 {taluk['name']} Taluk - Click for details",
                icon=folium.Icon(
                    color='blue',
                    icon='info-sign',
                    prefix='glyphicon'
                )
            ).add_to(taluk_group)
        
        taluk_group.add_to(m)
    
    def _add_custom_legend(self, m: folium.Map, crop_distribution: Dict):
        """Add custom legend with crop distribution statistics"""
        
        crops = crop_distribution.get('crops', {})
        total_area = crop_distribution.get('total_area_hectares', 0)
        
        # Build legend HTML
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; 
                    width: 300px; 
                    background-color: white; 
                    border: 2px solid #333;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                    z-index: 9999;
                    font-family: Arial, sans-serif;
                    padding: 15px;">
            <h4 style="margin: 0 0 15px 0; 
                       padding-bottom: 10px; 
                       border-bottom: 2px solid #4CAF50;
                       color: #2E7D32;
                       font-size: 16px;">
                📊 Crop Distribution Legend
            </h4>
            <div style="font-size: 13px;">
        '''
        
        # Sort crops by area (descending)
        sorted_crops = sorted(
            crops.items(), 
            key=lambda x: x[1].get('area_hectares', 0),
            reverse=True
        )
        
        for crop_id_str, crop_data in sorted_crops:
            crop_id = int(crop_id_str)
            color = self.CROP_COLORS[crop_id]['color']
            emoji = self.CROP_COLORS[crop_id]['emoji']
            crop_name = crop_data.get('crop_name', f'Crop {crop_id}')
            area_ha = crop_data.get('area_hectares', 0)
            percentage = crop_data.get('percentage', 0)
            
            legend_html += f'''
            <div style="margin-bottom: 12px; 
                        display: flex; 
                        align-items: center; 
                        justify-content: space-between;
                        padding: 8px;
                        background-color: #f9f9f9;
                        border-radius: 5px;">
                <div style="display: flex; align-items: center;">
                    <div style="width: 20px; 
                                height: 20px; 
                                background-color: {color}; 
                                margin-right: 10px; 
                                border: 1px solid #333;
                                border-radius: 3px;">
                    </div>
                    <span style="font-weight: 500;">{emoji} {crop_name}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: bold; color: #333; font-size: 14px;">
                        {percentage:.1f}%
                    </div>
                    <div style="color: #666; font-size: 11px;">
                        {area_ha:,.0f} ha
                    </div>
                </div>
            </div>
            '''
        
        # Add total area
        legend_html += f'''
            <div style="margin-top: 15px; 
                        padding-top: 12px; 
                        border-top: 2px solid #ddd; 
                        font-weight: bold;
                        color: #333;
                        font-size: 14px;">
                <div style="display: flex; justify-content: space-between;">
                    <span>Total Area:</span>
                    <span style="color: #1976D2;">{total_area:,.0f} hectares</span>
                </div>
            </div>
        </div>
        </div>
        '''
        
        # Add legend to map
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def save_map(self, map_obj: folium.Map, output_path: str):
        """Save Folium map to HTML file"""
        try:
            map_obj.save(output_path)
            print(f"Map saved successfully to {output_path}")
            return True
        except Exception as e:
            print(f"Error saving map: {e}")
            return False
    
    def get_map_html(self, map_obj: folium.Map) -> str:
        """Get HTML representation of the map"""
        try:
            return map_obj._repr_html_()
        except Exception as e:
            print(f"Error getting map HTML: {e}")
            return ""
    
    def _add_responsive_features(self, m: folium.Map):
        """Add responsive CSS and JavaScript to make the map resize dynamically"""
        
        # Responsive CSS for map container
        responsive_css = '''
        <style>
            /* Make map container fully responsive */
            html, body {
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
            }
            
            #map {
                position: absolute !important;
                top: 0;
                left: 0;
                width: 100% !important;
                height: 100% !important;
                z-index: 1;
            }
            
            .folium-map {
                width: 100% !important;
                height: 100% !important;
            }
            
            /* Responsive legend adjustments */
            @media (max-width: 768px) {
                /* Make legend smaller on mobile */
                div[style*="bottom: 50px; right: 50px"] {
                    bottom: 10px !important;
                    right: 10px !important;
                    width: 250px !important;
                    font-size: 12px !important;
                }
            }
            
            @media (max-width: 480px) {
                /* Even smaller on very small screens */
                div[style*="bottom: 50px; right: 50px"] {
                    bottom: 5px !important;
                    right: 5px !important;
                    width: 200px !important;
                    font-size: 11px !important;
                    padding: 10px !important;
                }
            }
            
            /* Ensure all Leaflet controls are visible */
            .leaflet-control {
                z-index: 1000;
            }
            
            /* Make the map take full viewport */
            .leaflet-container {
                width: 100vw !important;
                height: 100vh !important;
            }
        </style>
        '''
        
        # Responsive JavaScript for window resize handling
        responsive_js = '''
        <script>
            // Wait for the map to be fully loaded
            document.addEventListener('DOMContentLoaded', function() {
                // Give the map time to initialize
                setTimeout(function() {
                    // Get the Leaflet map instance
                    var mapElement = document.querySelector('.folium-map');
                    if (mapElement && mapElement._leaflet_id) {
                        var map = window[mapElement._leaflet_id];
                        
                        if (map) {
                            // Initial resize
                            map.invalidateSize();
                            
                            // Add window resize listener with debouncing
                            var resizeTimeout;
                            window.addEventListener('resize', function() {
                                clearTimeout(resizeTimeout);
                                resizeTimeout = setTimeout(function() {
                                    if (map) {
                                        map.invalidateSize();
                                        console.log('Map resized to fit window');
                                    }
                                }, 250);
                            });
                            
                            // Handle orientation change on mobile devices
                            window.addEventListener('orientationchange', function() {
                                setTimeout(function() {
                                    if (map) {
                                        map.invalidateSize();
                                        console.log('Map resized for orientation change');
                                    }
                                }, 300);
                            });
                            
                            console.log('Responsive map features initialized');
                        }
                    }
                    
                    // Also try the global map variable approach
                    if (typeof map_obj !== 'undefined') {
                        map_obj.invalidateSize();
                        
                        var resizeTimeout2;
                        window.addEventListener('resize', function() {
                            clearTimeout(resizeTimeout2);
                            resizeTimeout2 = setTimeout(function() {
                                map_obj.invalidateSize();
                            }, 250);
                        });
                    }
                }, 500);
            });
            
            // Fallback: Try to get the map after everything loads
            window.addEventListener('load', function() {
                setTimeout(function() {
                    var allMaps = [];
                    
                    // Try to find all Leaflet map instances
                    for (var key in window) {
                        if (window[key] && typeof window[key] === 'object' && window[key]._container) {
                            allMaps.push(window[key]);
                        }
                    }
                    
                    // Resize all found maps
                    allMaps.forEach(function(mapInstance) {
                        mapInstance.invalidateSize();
                    });
                    
                    if (allMaps.length > 0) {
                        console.log('Found and resized ' + allMaps.length + ' map(s)');
                    }
                }, 1000);
            });
        </script>
        '''
        
        # Add responsive features to the map
        m.get_root().html.add_child(folium.Element(responsive_css))
        m.get_root().html.add_child(folium.Element(responsive_js))
