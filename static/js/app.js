let map, drawnItems, drawControl;
let currentBounds = null;
let regionsData = null;
let cropChart = null;
let cropMapLayer = null;
let satelliteLayer = null;
let streetLayer = null;
let locationMarkers = new L.FeatureGroup();
let markerMode = false;
let savedLocations = [];
let markerIdMap = new Map();
let nextMarkerId = 1;
let lastAnalysisData = null;

document.addEventListener('DOMContentLoaded', function() {
    initMap();
    loadRegions();
    setupEventListeners();
    loadSavedLocations();
});

function initMap() {
    map = L.map('map').setView([20.5937, 78.9629], 5);
    
    streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
    
    satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '© Esri, DigitalGlobe, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
        maxZoom: 18
    });
    
    drawnItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    map.addLayer(locationMarkers);
    
    drawControl = new L.Control.Draw({
        draw: {
            polygon: true,
            rectangle: true,
            circle: false,
            circlemarker: false,
            marker: false,
            polyline: false
        },
        edit: {
            featureGroup: drawnItems,
            remove: true
        }
    });
    map.addControl(drawControl);
    
    map.on(L.Draw.Event.CREATED, function(event) {
        drawnItems.clearLayers();
        const layer = event.layer;
        drawnItems.addLayer(layer);
        
        const bounds = layer.getBounds();
        currentBounds = [
            bounds.getSouth(),
            bounds.getWest(),
            bounds.getNorth(),
            bounds.getEast()
        ];
        
        updateAreaInfo(bounds);
        document.getElementById('analyzeBtn').disabled = false;
    });
    
    map.on(L.Draw.Event.DELETED, function() {
        currentBounds = null;
        document.getElementById('areaInfo').textContent = 'No area selected';
        document.getElementById('analyzeBtn').disabled = true;
    });
    
    map.on('click', function(e) {
        if (markerMode) {
            addLocationMarker(e.latlng);
        }
    });
}

function loadRegions() {
    fetch('/api/regions')
        .then(response => response.json())
        .then(data => {
            regionsData = data;
            populateStates(data.states);
        })
        .catch(error => {
            console.error('Error loading regions:', error);
            alert('Failed to load region data');
        });
}

function populateStates(states) {
    const stateSelect = document.getElementById('stateSelect');
    states.forEach(state => {
        const option = document.createElement('option');
        option.value = state.code;
        option.textContent = state.name;
        option.dataset.state = JSON.stringify(state);
        stateSelect.appendChild(option);
    });
}

function setupEventListeners() {
    document.getElementById('stateSelect').addEventListener('change', function() {
        const districtSelect = document.getElementById('districtSelect');
        const talukaSelect = document.getElementById('talukaSelect');
        
        districtSelect.innerHTML = '<option value="">Select District</option>';
        talukaSelect.innerHTML = '<option value="">Select Taluka</option>';
        districtSelect.disabled = true;
        talukaSelect.disabled = true;
        
        if (this.value) {
            const stateData = JSON.parse(this.options[this.selectedIndex].dataset.state);
            stateData.districts.forEach(district => {
                const option = document.createElement('option');
                option.value = district.code;
                option.textContent = district.name;
                option.dataset.district = JSON.stringify(district);
                districtSelect.appendChild(option);
            });
            districtSelect.disabled = false;
        }
    });
    
    document.getElementById('districtSelect').addEventListener('change', function() {
        const talukaSelect = document.getElementById('talukaSelect');
        talukaSelect.innerHTML = '<option value="">Select Taluka</option>';
        talukaSelect.disabled = true;
        
        if (this.value) {
            const districtData = JSON.parse(this.options[this.selectedIndex].dataset.district);
            
            map.setView(districtData.center, 10);
            
            const bounds = [
                [districtData.center[0] - 0.5, districtData.center[1] - 0.5],
                [districtData.center[0] + 0.5, districtData.center[1] + 0.5]
            ];
            
            drawnItems.clearLayers();
            const rectangle = L.rectangle(bounds, {color: "#4CAF50", weight: 2});
            drawnItems.addLayer(rectangle);
            map.fitBounds(bounds);
            
            currentBounds = [
                districtData.center[0] - 0.5,
                districtData.center[1] - 0.5,
                districtData.center[0] + 0.5,
                districtData.center[1] + 0.5
            ];
            
            updateAreaInfo(L.latLngBounds(bounds));
            document.getElementById('analyzeBtn').disabled = false;
            
            districtData.talukas.forEach(taluka => {
                const option = document.createElement('option');
                option.value = taluka;
                option.textContent = taluka;
                talukaSelect.appendChild(option);
            });
            talukaSelect.disabled = false;
        }
    });
    
    document.getElementById('analyzeBtn').addEventListener('click', analyzeCrops);
    document.getElementById('resetBtn').addEventListener('click', resetSelection);
    document.getElementById('closeResults').addEventListener('click', function() {
        document.getElementById('resultsPanel').style.display = 'none';
    });
}

function updateAreaInfo(bounds) {
    const latDiff = Math.abs(bounds.getNorth() - bounds.getSouth());
    const lonDiff = Math.abs(bounds.getEast() - bounds.getWest());
    const areaKm2 = latDiff * lonDiff * 111 * 111;
    const areaHectares = areaKm2 * 100;
    
    document.getElementById('areaInfo').innerHTML = `
        <strong>Selected Area:</strong><br>
        ${areaKm2.toFixed(2)} km²<br>
        ${areaHectares.toFixed(2)} hectares
    `;
}

function analyzeCrops() {
    if (!currentBounds) {
        Swal.fire({
            icon: 'warning',
            title: 'No Area Selected',
            text: 'Please select an area on the map first!',
            confirmButtonColor: '#198754'
        });
        return;
    }
    
    let currentStage = 0;
    const stages = [
        { icon: 'satellite-dish', title: 'Fetching Satellite Data', text: 'Connecting to Google Earth Engine...' },
        { icon: 'gear', title: 'Preprocessing Data', text: 'Extracting NDVI features...' },
        { icon: 'brain', title: 'Model Prediction', text: 'Running Random Forest classifier...' },
        { icon: 'map', title: 'Generating Visualization', text: 'Creating crop distribution map...' }
    ];
    
    Swal.fire({
        title: stages[currentStage].title,
        html: `<i class="bi bi-${stages[currentStage].icon} fs-1"></i><br>${stages[currentStage].text}`,
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    document.getElementById('progressContainer').style.display = 'block';
    document.getElementById('analyzeBtn').disabled = true;
    
    const stageInterval = setInterval(() => {
        currentStage = (currentStage + 1) % stages.length;
        if (Swal.isVisible()) {
            Swal.update({
                title: stages[currentStage].title,
                html: `<i class="bi bi-${stages[currentStage].icon} fs-1"></i><br>${stages[currentStage].text}`
            });
        }
    }, 2000);
    
    fetch('/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            bounds: currentBounds
        })
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(stageInterval);
        if (data.success) {
            showProcessingStagesPopup(data);
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Analysis Failed',
                text: data.error || 'Unknown error occurred',
                confirmButtonColor: '#198754'
            });
        }
    })
    .catch(error => {
        clearInterval(stageInterval);
        console.error('Error:', error);
        Swal.fire({
            icon: 'error',
            title: 'Network Error',
            text: 'Failed to analyze crops: ' + error.message,
            confirmButtonColor: '#198754'
        });
    })
    .finally(() => {
        document.getElementById('progressContainer').style.display = 'none';
        document.getElementById('analyzeBtn').disabled = false;
    });
}

function displayResults(data) {
    const primaryCrop = data.primary_crop;
    
    lastAnalysisData = {
        bounds: currentBounds,
        crop_map: data.crop_map,
        area_statistics: data.area_statistics
    };
    
    document.getElementById('primaryCropInfo').innerHTML = `
        <div class="crop-badge" style="background-color: ${primaryCrop.color}">
            ${primaryCrop.name}
        </div>
        <div class="confidence-bar" style="width: ${primaryCrop.confidence}%; background: ${primaryCrop.color}">
            ${primaryCrop.confidence}% Confidence
        </div>
    `;
    
    let areaStatsHTML = `<p><strong>Total Area:</strong> ${data.total_area_hectares.toFixed(2)} hectares</p>`;
    document.getElementById('areaStats').innerHTML = areaStatsHTML;
    
    let detailedStatsHTML = '<table class="table-crop">';
    data.area_statistics.forEach(stat => {
        detailedStatsHTML += `
            <tr>
                <td>
                    <span class="crop-indicator" style="background-color: ${stat.color}"></span>
                    ${stat.crop_name}
                </td>
                <td>${stat.area_hectares} ha</td>
                <td>${stat.percentage}%</td>
            </tr>
        `;
    });
    detailedStatsHTML += '</table>';
    document.getElementById('detailedStats').innerHTML = detailedStatsHTML;
    
    createCropChart(data.area_statistics);
    
    if (data.crop_map) {
        displayCropMapVisualization(data.crop_map);
    }
    
    document.getElementById('resultsPanel').style.display = 'block';
}

function displayCropMapVisualization(cropMapData) {
    if (cropMapLayer) {
        map.removeLayer(cropMapLayer);
    }
    
    cropMapLayer = L.geoJSON(cropMapData, {
        style: function(feature) {
            return {
                fillColor: feature.properties.color,
                fillOpacity: 0.6,
                color: feature.properties.color,
                weight: 1,
                opacity: 0.8
            };
        },
        onEachFeature: function(feature, layer) {
            layer.bindPopup(`
                <strong>${feature.properties.crop_name}</strong><br>
                Crop ID: ${feature.properties.crop_id}
            `);
        }
    }).addTo(map);
}

function createCropChart(statistics) {
    const ctx = document.getElementById('cropChart').getContext('2d');
    
    if (cropChart) {
        cropChart.destroy();
    }
    
    cropChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: statistics.map(s => s.crop_name),
            datasets: [{
                data: statistics.map(s => s.percentage),
                backgroundColor: statistics.map(s => s.color),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    });
}

function resetSelection() {
    drawnItems.clearLayers();
    
    if (cropMapLayer) {
        map.removeLayer(cropMapLayer);
        cropMapLayer = null;
    }
    
    currentBounds = null;
    document.getElementById('areaInfo').textContent = 'No area selected';
    document.getElementById('analyzeBtn').disabled = true;
    document.getElementById('stateSelect').value = '';
    document.getElementById('districtSelect').innerHTML = '<option value="">Select District</option>';
    document.getElementById('districtSelect').disabled = true;
    document.getElementById('talukaSelect').innerHTML = '<option value="">Select Taluka</option>';
    document.getElementById('talukaSelect').disabled = true;
    document.getElementById('resultsPanel').style.display = 'none';
    map.setView([20.5937, 78.9629], 5);
}

function toggleSatelliteView() {
    if (map.hasLayer(satelliteLayer)) {
        map.removeLayer(satelliteLayer);
        map.addLayer(streetLayer);
        document.getElementById('satelliteToggle').innerHTML = '<i class="bi bi-globe"></i> Satellite View';
        document.getElementById('satelliteToggle').classList.remove('btn-primary');
        document.getElementById('satelliteToggle').classList.add('btn-outline-primary');
    } else {
        map.removeLayer(streetLayer);
        map.addLayer(satelliteLayer);
        document.getElementById('satelliteToggle').innerHTML = '<i class="bi bi-map"></i> Street View';
        document.getElementById('satelliteToggle').classList.remove('btn-outline-primary');
        document.getElementById('satelliteToggle').classList.add('btn-primary');
    }
}

function toggleMarkerMode() {
    markerMode = !markerMode;
    updateMarkerModeUI();
}

function updateMarkerModeUI() {
    const btn = document.getElementById('markerModeToggle');
    if (markerMode) {
        btn.classList.remove('btn-outline-success');
        btn.classList.add('btn-success');
        btn.innerHTML = '<i class="bi bi-geo-alt-fill"></i> Click Map to Add Location';
        map.getContainer().style.cursor = 'crosshair';
    } else {
        btn.classList.remove('btn-success');
        btn.classList.add('btn-outline-success');
        btn.innerHTML = '<i class="bi bi-geo-alt"></i> Add Location Labels';
        map.getContainer().style.cursor = '';
    }
}

function addLocationMarker(latlng) {
    const locationName = prompt('Enter location name:', '');
    if (locationName && locationName.trim() !== '') {
        const stableId = 'marker_' + nextMarkerId++;
        const marker = L.marker(latlng, {
            icon: L.divIcon({
                className: 'custom-location-marker',
                html: `<div class="marker-pin"><i class="bi bi-geo-alt-fill"></i></div>
                       <div class="marker-label">${locationName}</div>`,
                iconSize: [30, 42],
                iconAnchor: [15, 42],
                popupAnchor: [0, -42]
            })
        }).addTo(locationMarkers);
        
        markerIdMap.set(stableId, marker);
        
        marker.bindPopup(`
            <div style="text-align: center;">
                <strong>${locationName}</strong><br>
                <small>Lat: ${latlng.lat.toFixed(4)}, Lng: ${latlng.lng.toFixed(4)}</small><br>
                <button onclick="removeMarker('${stableId}')" class="btn btn-sm btn-danger mt-2">Remove</button>
            </div>
        `);
        
        const locationData = {
            id: stableId,
            name: locationName,
            lat: latlng.lat,
            lng: latlng.lng
        };
        savedLocations.push(locationData);
        saveLocations();
    }
    markerMode = false;
    updateMarkerModeUI();
}

function removeMarker(markerId) {
    const marker = markerIdMap.get(markerId);
    if (marker) {
        locationMarkers.removeLayer(marker);
        markerIdMap.delete(markerId);
    }
    savedLocations = savedLocations.filter(loc => loc.id !== markerId);
    saveLocations();
    map.closePopup();
}

function clearAllMarkers() {
    if (confirm('Are you sure you want to remove all location labels?')) {
        locationMarkers.clearLayers();
        markerIdMap.clear();
        savedLocations = [];
        saveLocations();
    }
}

function saveLocations() {
    fetch('/api/save-locations', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ locations: savedLocations })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Locations saved:', data);
    })
    .catch(error => {
        console.error('Error saving locations:', error);
    });
}

function loadSavedLocations() {
    fetch('/api/get-locations')
        .then(response => response.json())
        .then(data => {
            if (data.locations && Array.isArray(data.locations)) {
                savedLocations = data.locations;
                data.locations.forEach(loc => {
                    const marker = L.marker([loc.lat, loc.lng], {
                        icon: L.divIcon({
                            className: 'custom-location-marker',
                            html: `<div class="marker-pin"><i class="bi bi-geo-alt-fill"></i></div>
                                   <div class="marker-label">${loc.name}</div>`,
                            iconSize: [30, 42],
                            iconAnchor: [15, 42],
                            popupAnchor: [0, -42]
                        })
                    }).addTo(locationMarkers);
                    
                    markerIdMap.set(loc.id, marker);
                    
                    const markerIdNum = parseInt(loc.id.replace('marker_', ''));
                    if (markerIdNum >= nextMarkerId) {
                        nextMarkerId = markerIdNum + 1;
                    }
                    
                    marker.bindPopup(`
                        <div style="text-align: center;">
                            <strong>${loc.name}</strong><br>
                            <small>Lat: ${loc.lat.toFixed(4)}, Lng: ${loc.lng.toFixed(4)}</small><br>
                            <button onclick="removeMarker('${loc.id}')" class="btn btn-sm btn-danger mt-2">Remove</button>
                        </div>
                    `);
                });
            }
        })
        .catch(error => {
            console.log('No saved locations found or error loading:', error);
        });
}

function exportMap() {
    if (!lastAnalysisData) {
        alert('Please analyze a region first before exporting.');
        return;
    }
    
    const exportBtn = document.getElementById('exportMapBtn');
    exportBtn.disabled = true;
    exportBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Generating Satellite Image...';
    
    const exportData = {
        bounds: lastAnalysisData.bounds,
        crop_map: lastAnalysisData.crop_map,
        area_statistics: lastAnalysisData.area_statistics,
        locations: savedLocations
    };
    
    fetch('/api/export-satellite-image', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(exportData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to generate satellite image');
        }
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        link.download = `crop-analysis-satellite-${timestamp}.png`;
        link.href = url;
        link.click();
        window.URL.revokeObjectURL(url);
        
        exportBtn.disabled = false;
        exportBtn.innerHTML = '<i class="bi bi-download"></i> Export Map';
    })
    .catch(error => {
        console.error('Error exporting satellite image:', error);
        alert('Error exporting satellite image. Please try again.');
        exportBtn.disabled = false;
        exportBtn.innerHTML = '<i class="bi bi-download"></i> Export Map';
    });
}

function showProcessingStagesPopup(data) {
    const stages = data.processing_stages || [];
    let stagesHTML = '<div style="text-align: left; max-width: 600px; margin: 0 auto;">';
    stagesHTML += '<h5 class="mb-3 text-center">Processing Complete!</h5>';
    stagesHTML += '<div class="list-group">';
    
    stages.forEach((stage, index) => {
        stagesHTML += `
            <div class="list-group-item">
                <div class="d-flex w-100 justify-content-between align-items-center">
                    <div>
                        <i class="bi bi-check-circle-fill text-success me-2"></i>
                        <strong>${stage.name}</strong>
                    </div>
                    <small class="text-muted">${stage.duration_seconds}s</small>
                </div>
                <p class="mb-0 mt-1 text-muted small">${stage.details}</p>
            </div>
        `;
    });
    
    stagesHTML += '</div></div>';
    
    Swal.fire({
        title: 'All Processing Stages Completed!',
        html: stagesHTML,
        icon: 'success',
        confirmButtonText: 'View Model Accuracy',
        confirmButtonColor: '#198754',
        width: '700px'
    }).then((result) => {
        if (result.isConfirmed) {
            showModelAccuracyPopup(data);
        } else {
            displayResults(data);
        }
    });
}

function showModelAccuracyPopup(data) {
    const performance = data.model_performance || {};
    const suggestions = data.improvement_suggestions || [];
    
    let accuracyHTML = '<div style="text-align: left; max-width: 700px; margin: 0 auto;">';
    
    accuracyHTML += '<div class="card mb-3">';
    accuracyHTML += '<div class="card-body">';
    accuracyHTML += '<h6 class="card-title"><i class="bi bi-graph-up"></i> Model Performance Metrics</h6>';
    accuracyHTML += '<div class="row text-center mb-3">';
    accuracyHTML += `
        <div class="col-md-4">
            <div class="p-3 border rounded">
                <div class="fs-2 fw-bold text-success">${performance.current_accuracy}%</div>
                <small class="text-muted">Current Accuracy</small>
            </div>
        </div>
        <div class="col-md-4">
            <div class="p-3 border rounded">
                <div class="fs-2 fw-bold text-primary">${performance.confidence_score}%</div>
                <small class="text-muted">Confidence</small>
            </div>
        </div>
        <div class="col-md-4">
            <div class="p-3 border rounded">
                <div class="fs-2 fw-bold text-info">${performance.improvement_percentage}%</div>
                <small class="text-muted">Improvement</small>
            </div>
        </div>
    `;
    accuracyHTML += '</div>';
    accuracyHTML += `<p class="mb-0"><strong>Model Type:</strong> ${performance.model_type}</p>`;
    accuracyHTML += `<p class="mb-0"><strong>Features Used:</strong> ${performance.feature_count}</p>`;
    accuracyHTML += `<p class="mb-0"><strong>Baseline Accuracy:</strong> ${performance.baseline_accuracy}%</p>`;
    accuracyHTML += '</div></div>';
    
    accuracyHTML += '<div class="card">';
    accuracyHTML += '<div class="card-body">';
    accuracyHTML += '<h6 class="card-title"><i class="bi bi-lightbulb"></i> How to Improve Model Accuracy</h6>';
    accuracyHTML += '<div class="accordion" id="suggestionsAccordion">';
    
    suggestions.forEach((suggestion, index) => {
        const priorityColors = {
            'high': 'danger',
            'medium': 'warning',
            'low': 'info'
        };
        const priorityColor = priorityColors[suggestion.priority] || 'secondary';
        
        accuracyHTML += `
            <div class="accordion-item">
                <h2 class="accordion-header" id="heading${index}">
                    <button class="accordion-button ${index === 0 ? '' : 'collapsed'}" type="button" 
                            data-bs-toggle="collapse" data-bs-target="#collapse${index}" 
                            aria-expanded="${index === 0 ? 'true' : 'false'}" aria-controls="collapse${index}">
                        <span class="badge bg-${priorityColor} me-2">${suggestion.priority.toUpperCase()}</span>
                        ${suggestion.suggestion}
                        <span class="badge bg-success ms-auto">${suggestion.expected_improvement}</span>
                    </button>
                </h2>
                <div id="collapse${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" 
                     aria-labelledby="heading${index}" data-bs-parent="#suggestionsAccordion">
                    <div class="accordion-body">
                        ${suggestion.details}
                    </div>
                </div>
            </div>
        `;
    });
    
    accuracyHTML += '</div></div></div>';
    accuracyHTML += '</div>';
    
    Swal.fire({
        title: 'Model Accuracy Analysis',
        html: accuracyHTML,
        icon: 'info',
        confirmButtonText: 'View Results',
        confirmButtonColor: '#198754',
        width: '800px',
        customClass: {
            htmlContainer: 'text-start'
        }
    }).then(() => {
        displayResults(data);
    });
}

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('active');
    
    if (sidebar.classList.contains('active')) {
        document.querySelector('.sidebar-toggle').innerHTML = '<i class="bi bi-x"></i> Close';
    } else {
        document.querySelector('.sidebar-toggle').innerHTML = '<i class="bi bi-list"></i> Menu';
    }
}

window.addEventListener('resize', function() {
    if (map) {
        setTimeout(function() {
            map.invalidateSize();
        }, 400);
    }
    
    if (window.innerWidth > 768) {
        const sidebar = document.querySelector('.sidebar');
        if (sidebar) {
            sidebar.classList.remove('active');
            document.querySelector('.sidebar-toggle').innerHTML = '<i class="bi bi-list"></i> Menu';
        }
    }
});

document.addEventListener('click', function(e) {
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    
    if (window.innerWidth <= 768 && 
        sidebar && 
        sidebar.classList.contains('active') && 
        !sidebar.contains(e.target) && 
        !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('active');
        sidebarToggle.innerHTML = '<i class="bi bi-list"></i> Menu';
    }
});
