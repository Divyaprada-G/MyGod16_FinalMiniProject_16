// enhanced-crop-map.js
class EnhancedCropMap {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.map = null;
        this.satelliteLayer = null;
        this.cropLayers = {};
        this.currentView = 'satellite';
        this.init();
    }

    init() {
        this.createMap();
        this.addControls();
        this.loadCropData();
        this.addEventListeners();
    }

    createMap() {
        // Initialize map with satellite view
        this.map = L.map(this.container).setView([20.5937, 78.9629], 5);

        // Satellite layer
        this.satelliteLayer = L.tileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            {
                attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DigitalGlobe, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
                maxZoom: 18
            }
        ).addTo(this.map);

        // Standard map layer
        this.standardLayer = L.tileLayer(
            'https://{s}.tile.openstreetmap.org/{z}/{y}/{x}.png',
            {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18
            }
        );

        this.addBaseLayers();
    }

    addBaseLayers() {
        // Add different base layers
        const baseLayers = {
            "Satellite": this.satelliteLayer,
            "Standard": this.standardLayer
        };

        // Add overlay layers for different crops
        const overlayLayers = {};

        // Add layer control
        L.control.layers(baseLayers, overlayLayers).addTo(this.map);
    }

    addControls() {
        // Create custom control container
        const controlContainer = L.control({ position: 'topright' });
        
        controlContainer.onAdd = () => {
            const div = L.DomUtil.create('div', 'map-controls');
            div.innerHTML = `
                <div class="control-panel">
                    <h4>Crop Map Controls</h4>
                    <div class="view-buttons">
                        <button class="view-btn active" data-view="satellite">Satellite</button>
                        <button class="view-btn" data-view="standard">Standard</button>
                        <button class="view-btn" data-view="hybrid">Hybrid</button>
                    </div>
                    <div class="crop-filters">
                        <label><input type="checkbox" value="wheat" checked> Wheat</label>
                        <label><input type="checkbox" value="rice" checked> Rice</label>
                        <label><input type="checkbox" value="corn" checked> Corn</label>
                        <label><input type="checkbox" value="cotton" checked> Cotton</label>
                    </div>
                    <div class="map-tools">
                        <button class="tool-btn" id="measureTool">Measure Area</button>
                        <button class="tool-btn" id="drawTool">Draw Field</button>
                        <button class="tool-btn" id="clearAll">Clear All</button>
                    </div>
                </div>
            `;
            return div;
        };
        
        controlContainer.addTo(this.map);
    }

    loadCropData() {
        // Sample crop data - replace with your actual data
        const cropData = [
            { id: 1, type: 'wheat', coordinates: [[28.6139, 77.2090], [28.6149, 77.2190], [28.6159, 77.2095]], area: '50 acres', yield: 'High' },
            { id: 2, type: 'rice', coordinates: [[19.0760, 72.8777], [19.0770, 72.8787], [19.0780, 72.8767]], area: '30 acres', yield: 'Medium' },
            { id: 3, type: 'corn', coordinates: [[12.9716, 77.5946], [12.9726, 77.5956], [12.9736, 77.5936]], area: '40 acres', yield: 'High' }
        ];

        this.displayCropAreas(cropData);
    }

    displayCropAreas(cropData) {
        const cropColors = {
            wheat: '#FFD700',
            rice: '#00FF00',
            corn: '#FFA500',
            cotton: '#FFFFFF'
        };

        cropData.forEach(crop => {
            const polygon = L.polygon(crop.coordinates, {
                color: cropColors[crop.type] || '#3388ff',
                fillColor: cropColors[crop.type] || '#3388ff',
                fillOpacity: 0.4,
                weight: 2
            }).addTo(this.map);

            // Add popup with crop information
            polygon.bindPopup(`
                <div class="crop-popup">
                    <h3>${crop.type.toUpperCase()} Field</h3>
                    <p><strong>Area:</strong> ${crop.area}</p>
                    <p><strong>Yield:</strong> ${crop.yield}</p>
                    <p><strong>Crop Type:</strong> ${crop.type}</p>
                    <button onclick="analyzeCrop(${crop.id})">Analyze</button>
                </div>
            `);

            // Add to crop layers
            if (!this.cropLayers[crop.type]) {
                this.cropLayers[crop.type] = L.layerGroup();
            }
            this.cropLayers[crop.type].addLayer(polygon);
        });
    }

    addEventListeners() {
        // View switching
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('view-btn')) {
                document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
                e.target.classList.add('active');
                this.switchView(e.target.dataset.view);
            }
        });

        // Crop filters
        document.addEventListener('change', (e) => {
            if (e.target.type === 'checkbox') {
                this.toggleCropLayer(e.target.value, e.target.checked);
            }
        });

        // Tool buttons
        document.addEventListener('click', (e) => {
            if (e.target.id === 'measureTool') {
                this.enableMeasureTool();
            } else if (e.target.id === 'drawTool') {
                this.enableDrawTool();
            } else if (e.target.id === 'clearAll') {
                this.clearAll();
            }
        });
    }

    switchView(view) {
        this.currentView = view;
        
        switch(view) {
            case 'satellite':
                this.map.removeLayer(this.standardLayer);
                this.satelliteLayer.addTo(this.map);
                break;
            case 'standard':
                this.map.removeLayer(this.satelliteLayer);
                this.standardLayer.addTo(this.map);
                break;
            case 'hybrid':
                // You can add hybrid view logic here
                break;
        }
    }

    toggleCropLayer(cropType, visible) {
        if (this.cropLayers[cropType]) {
            if (visible) {
                this.map.addLayer(this.cropLayers[cropType]);
            } else {
                this.map.removeLayer(this.cropLayers[cropType]);
            }
        }
    }

    enableMeasureTool() {
        // Implement measurement tool
        alert('Measure tool activated - Click on map to measure distances');
    }

    enableDrawTool() {
        // Implement drawing tool
        alert('Draw tool activated - Draw fields on the map');
    }

    clearAll() {
        // Clear all drawn elements
        Object.values(this.cropLayers).forEach(layer => {
            this.map.removeLayer(layer);
        });
    }
}

// Global function for crop analysis
function analyzeCrop(cropId) {
    alert(`Analyzing crop with ID: ${cropId}\nThis would show detailed analysis in a real implementation.`);
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.cropMap = new EnhancedCropMap('map-container');
});