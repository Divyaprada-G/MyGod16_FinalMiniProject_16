from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
import io
from functools import lru_cache
import hashlib
from utils.gee_handler import GEEHandler
from utils.model_predictor import CropPredictor
from utils.map_generator import MapGenerator
from utils.satellite_image_generator import SatelliteImageGenerator
from utils.boundary_handler import BoundaryHandler
from utils.folium_map_generator import FoliumMapGenerator

app = Flask(__name__)
CORS(app)

analysis_cache = {}

gee_handler = GEEHandler()
crop_predictor = CropPredictor()
map_generator = MapGenerator()
satellite_image_generator = SatelliteImageGenerator()
boundary_handler = BoundaryHandler()
folium_map_generator = FoliumMapGenerator(boundary_handler)

gee_handler.initialize()
crop_predictor.load_model()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/regions', methods=['GET'])
def get_regions():
    try:
        with open('data/regions.json', 'r') as f:
            regions_data = json.load(f)
        return jsonify(regions_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_region():
    try:
        data = request.json
        bounds = data.get('bounds')
        
        if not bounds or len(bounds) != 4:
            return jsonify({'error': 'Invalid bounds provided'}), 400
        
        processing_stages = []
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        stage_start = datetime.now()
        ndvi_data = gee_handler.get_ndvi_data(
            bounds,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        stage_duration = (datetime.now() - stage_start).total_seconds()
        processing_stages.append({
            'name': 'Data Fetching from Satellite',
            'status': 'completed',
            'duration_seconds': round(stage_duration, 2),
            'details': f"Fetched NDVI data from {ndvi_data.get('image_count', 0)} satellite images"
        })
        
        stage_start = datetime.now()
        features = gee_handler.extract_features(ndvi_data)
        stage_duration = (datetime.now() - stage_start).total_seconds()
        processing_stages.append({
            'name': 'Preprocessing & Feature Extraction',
            'status': 'completed',
            'duration_seconds': round(stage_duration, 2),
            'details': f"Extracted {len(features[0])} features including NDVI statistics and temporal data"
        })
        
        stage_start = datetime.now()
        crop_id, probabilities = crop_predictor.predict(features)
        stage_duration = (datetime.now() - stage_start).total_seconds()
        
        if crop_id is None:
            return jsonify({'error': 'Prediction failed'}), 500
        
        crop_info = crop_predictor.get_crop_info(crop_id)
        confidence = probabilities[crop_id] * 100
        
        processing_stages.append({
            'name': 'Model Prediction',
            'status': 'completed',
            'duration_seconds': round(stage_duration, 2),
            'details': f"Predicted crop: {crop_info['name']} with {round(confidence, 2)}% confidence"
        })
        
        lat_diff = abs(bounds[2] - bounds[0])
        lon_diff = abs(bounds[3] - bounds[1])
        area_hectares = lat_diff * lon_diff * 111 * 111 * 100
        
        area_statistics = crop_predictor.calculate_area_statistics(crop_id, area_hectares)
        
        stage_start = datetime.now()
        crop_map_geojson = map_generator.generate_crop_map_geojson(bounds, area_statistics, crop_predictor)
        stage_duration = (datetime.now() - stage_start).total_seconds()
        processing_stages.append({
            'name': 'Map Generation & Visualization',
            'status': 'completed',
            'duration_seconds': round(stage_duration, 2),
            'details': f"Generated crop distribution map for {round(area_hectares, 2)} hectares"
        })
        
        model_accuracy = crop_predictor.get_model_accuracy()
        accuracy_improvement_suggestions = crop_predictor.get_improvement_suggestions(confidence)
        
        result = {
            'success': True,
            'processing_stages': processing_stages,
            'model_performance': {
                'current_accuracy': model_accuracy['accuracy'],
                'baseline_accuracy': model_accuracy['baseline'],
                'improvement_percentage': model_accuracy['improvement'],
                'confidence_score': round(confidence, 2),
                'model_type': model_accuracy['model_type'],
                'feature_count': len(features[0])
            },
            'improvement_suggestions': accuracy_improvement_suggestions,
            'primary_crop': {
                'id': crop_id,
                'name': crop_info['name'],
                'color': crop_info['color'],
                'confidence': round(confidence, 2)
            },
            'all_probabilities': [
                {
                    'crop_id': i,
                    'crop_name': crop_predictor.get_crop_info(i)['name'],
                    'probability': round(prob * 100, 2)
                }
                for i, prob in enumerate(probabilities)
            ],
            'area_statistics': area_statistics,
            'total_area_hectares': round(area_hectares, 2),
            'ndvi_data': ndvi_data,
            'crop_map': crop_map_geojson,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/crop-info', methods=['GET'])
def get_crop_info():
    try:
        with open('data/crop_data.json', 'r') as f:
            crop_data = json.load(f)
        return jsonify(crop_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'gee_initialized': gee_handler.initialized,
        'model_loaded': crop_predictor.model is not None
    })

@app.route('/api/save-locations', methods=['POST'])
def save_locations():
    try:
        data = request.json
        locations = data.get('locations', [])
        
        os.makedirs('data', exist_ok=True)
        with open('data/saved_locations.json', 'w') as f:
            json.dump({'locations': locations}, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Locations saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-locations', methods=['GET'])
def get_locations():
    try:
        if os.path.exists('data/saved_locations.json'):
            with open('data/saved_locations.json', 'r') as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({'locations': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-satellite-image', methods=['POST'])
def export_satellite_image():
    try:
        data = request.json
        bounds = data.get('bounds')
        crop_map = data.get('crop_map')
        area_statistics = data.get('area_statistics')
        locations = data.get('locations', [])
        
        if not bounds or not crop_map or not area_statistics:
            return jsonify({'error': 'Missing required data'}), 400
        
        annotated_image = satellite_image_generator.generate_annotated_satellite_image(
            bounds=bounds,
            crop_map_data=crop_map,
            area_statistics=area_statistics,
            location_labels=locations,
            width=1024,
            height=768
        )
        
        img_io = io.BytesIO()
        annotated_image.save(img_io, 'PNG', quality=85, optimize=True)
        img_io.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'crop-analysis-satellite-{timestamp}.png'
        
        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error generating satellite image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/districts', methods=['GET'])
def get_districts():
    """Get list of all available districts"""
    try:
        districts = boundary_handler.get_all_districts()
        return jsonify({'districts': districts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/district-boundary/<district_name>', methods=['GET'])
def get_district_boundary(district_name):
    """Get boundary GeoJSON for a specific district"""
    try:
        boundary = boundary_handler.get_district_boundary(district_name)
        if boundary:
            return jsonify(boundary)
        else:
            return jsonify({'error': f'District {district_name} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/taluks/<district_name>', methods=['GET'])
def get_taluks(district_name):
    """Get taluk information for a district"""
    try:
        taluks = boundary_handler.get_taluk_info(district_name)
        return jsonify({'taluks': taluks, 'district': district_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/crop-overlay', methods=['POST'])
def get_crop_overlay():
    """Get crop classification overlay with district boundaries"""
    try:
        data = request.json
        bounds = data.get('bounds')
        district = data.get('district', '')
        grid_size = data.get('grid_size', 20)
        
        if not bounds or len(bounds) != 4:
            return jsonify({'error': 'Invalid bounds provided'}), 400
        
        ndvi_data = gee_handler.get_ndvi_data(
            bounds,
            (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        
        features = gee_handler.extract_features(ndvi_data)
        crop_id, probabilities = crop_predictor.predict(features)
        
        confidence = float(probabilities[crop_id])
        
        crop_overlay = boundary_handler.create_crop_overlay_geojson(
            bounds, 
            int(crop_id),
            grid_size
        )
        
        distribution = boundary_handler.calculate_crop_distribution(
            bounds,
            int(crop_id),
            confidence
        )
        
        district_boundary = None
        if district:
            district_boundary = boundary_handler.get_district_boundary(district)
        
        taluks = boundary_handler.get_taluk_info(district) if district else []
        
        return jsonify({
            'success': True,
            'crop_overlay': crop_overlay,
            'distribution': distribution,
            'district_boundary': district_boundary,
            'taluks': taluks,
            'primary_crop_id': int(crop_id),
            'probabilities': probabilities.tolist()
        })
        
    except Exception as e:
        print(f"Error generating crop overlay: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/folium-map', methods=['POST'])
def generate_folium_map():
    """Generate interactive Folium map with district boundaries, crop overlays, and taluk markers"""
    try:
        data = request.json
        district = data.get('district', 'Tumkur')
        bounds = data.get('bounds')
        include_crop_overlay = data.get('include_crop_overlay', True)
        
        # Calculate center and zoom from bounds if provided
        if bounds and len(bounds) == 4:
            center_lat = (bounds[0] + bounds[2]) / 2
            center_lng = (bounds[1] + bounds[3]) / 2
            zoom_start = 10
        else:
            # Default center for Tumkur
            center_lat = 13.34
            center_lng = 77.10
            zoom_start = 9
        
        # Get crop distribution and overlay data if requested
        crop_distribution = None
        crop_overlay_data = None
        
        if include_crop_overlay and bounds:
            # Get NDVI data and make prediction
            ndvi_data = gee_handler.get_ndvi_data(
                bounds,
                (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                datetime.now().strftime('%Y-%m-%d')
            )
            
            features = gee_handler.extract_features(ndvi_data)
            crop_id, probabilities = crop_predictor.predict(features)
            
            if crop_id is not None:
                confidence = float(probabilities[crop_id])
                
                # Generate crop overlay and distribution
                crop_overlay_data = boundary_handler.create_crop_overlay_geojson(
                    bounds, 
                    int(crop_id),
                    grid_size=30
                )
                
                crop_distribution = boundary_handler.calculate_crop_distribution(
                    bounds,
                    int(crop_id),
                    confidence
                )
        
        # Generate Folium map
        folium_map = folium_map_generator.create_interactive_map(
            district_name=district,
            crop_distribution=crop_distribution,
            crop_overlay_data=crop_overlay_data,
            center_lat=center_lat,
            center_lng=center_lng,
            zoom_start=zoom_start
        )
        
        # Get HTML representation
        map_html = folium_map._repr_html_()
        
        return jsonify({
            'success': True,
            'map_html': map_html,
            'district': district,
            'has_crop_data': crop_distribution is not None
        })
        
    except Exception as e:
        print(f"Error generating Folium map: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/map/interactive/<district>', methods=['GET'])
def view_interactive_map(district):
    """Serve standalone interactive Folium map page"""
    try:
        # Get bounds for the district
        district_boundary = boundary_handler.get_district_boundary(district)
        
        bounds = None
        if district_boundary:
            from shapely.geometry import shape
            geom = shape(district_boundary.get('geometry'))
            bbox = geom.bounds  # (minx, miny, maxx, maxy)
            bounds = [bbox[1], bbox[0], bbox[3], bbox[2]]  # [min_lat, min_lon, max_lat, max_lon]
        
        # Generate the Folium map
        folium_map = folium_map_generator.create_interactive_map(
            district_name=district,
            crop_distribution=None,
            crop_overlay_data=None,
            center_lat=(bounds[0] + bounds[2]) / 2 if bounds else 13.34,
            center_lng=(bounds[1] + bounds[3]) / 2 if bounds else 77.10,
            zoom_start=9
        )
        
        # Return HTML directly
        return folium_map._repr_html_()
        
    except Exception as e:
        print(f"Error serving interactive map: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>", 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
