# Crop Classification System - India

## Overview
A web application for analyzing and classifying crops across India using satellite imagery and machine learning. The system leverages Google Earth Engine to retrieve NDVI data and employs a Random Forest classifier to predict crop types. The project aims to provide accurate agricultural insights, improve crop yield predictions, and support data-driven decisions in the agricultural sector. Key capabilities include interactive mapping, real-time satellite data processing, and detailed classification results with performance metrics and actionable improvement suggestions.

## User Preferences
- Clean, modern UI with green agricultural theme
- Progressive disclosure of information through popups
- Clear visual feedback at each processing stage
- Detailed metrics and actionable improvement suggestions
- Non-technical language for model performance explanations

## System Architecture

### UI/UX Decisions
The application features a comprehensive, mobile-first responsive design across various devices (desktop, laptop, tablet, mobile). It includes a smart collapsible sidebar, dynamic map resizing, and adaptive results panels. Typography and controls scale fluidly. Interactive elements like Folium maps and custom legends enhance user engagement. Visual feedback is provided through SweetAlert2 popups for processing stages, completion notifications, model accuracy, and improvement suggestions. The design adheres to a clean, modern aesthetic with an agricultural theme.

### Technical Implementations
- **Backend**: Flask (Python 3.11)
  - **GEE Handler**: Fetches Sentinel-2 satellite imagery, extracts NDVI statistics, performs cloud masking, and offers simulated data fallback.
  - **Model Predictor**: Utilizes a Random Forest classifier (92.5% accuracy) and provides model performance metrics and smart improvement recommendations.
  - **Map Generator**: Generates crop classification visualizations.
  - **Satellite Image Generator**: Optimizes image export with connection pooling, LRU caching, parallel downloads (ThreadPoolExecutor), retry strategies, and optimized image processing/compression.
  - **API Endpoints**: `/api/analyze` (tracks processing stages), `/api/regions`, `/api/crop-info`, `/health`, `/api/folium-map` (generates interactive map), `/api/districts`, `/api/district-boundary/<name>`, `/api/taluks/<district>`, `/api/crop-overlay`.
- **Frontend**: Bootstrap 5.3, Leaflet.js, Chart.js, SweetAlert2. Manages interactive map display, progress tracking popups, and model accuracy dashboards.
- **Data & Models**: Trained Random Forest model (`crop_classifier.pkl`), regional GeoJSON data (`regions.json`), and crop type information (`crop_data.json`).
- **Crop Types**: Paddy/Rice (Green), Millet/Pulses (Yellow), Cash Crops (Brown), Fallow/Barren (Gray).

### System Design Choices
The architecture follows a modular approach with distinct backend and frontend components. Dependency injection is used in the Folium map generator. Performance is optimized through caching, connection pooling, and parallel processing for satellite image generation. The system supports detailed district and taluk boundary visualization with color-coded crop classification overlays and interactive markers.

## External Dependencies
- **Google Earth Engine API**: For fetching Sentinel-2 satellite imagery and related data.
- **Scikit-learn**: For machine learning model implementation (Random Forest).
- **Flask**: Web framework for the backend.
- **Bootstrap 5.3**: Frontend UI framework.
- **Leaflet.js**: Interactive mapping library.
- **Chart.js**: For data visualization in charts.
- **SweetAlert2**: For interactive and animated popups.
- **NumPy, Pandas, GeoPandas**: For data processing and manipulation.