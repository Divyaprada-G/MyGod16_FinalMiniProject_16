// Enhanced District Boundary and Taluk Visualization Features

let districtBoundaryLayer = null;
let talukMarkers = new L.FeatureGroup();
let cropOverlayLayer = null;
let legendControl = null;

// Initialize boundary features
function initBoundaryFeatures() {
    map.addLayer(talukMarkers);
    addDistrictSelector();
    addLegendControl();
}

// Add district selector to the interface
function addDistrictSelector() {
    fetch('/api/districts')
        .then(response => response.json())
        .then(data => {
            const districts = data.districts || [];
            console.log('Available districts:', districts);
            
            if (districts.length > 0) {
                addDistrictSelectControl(districts);
            }
        })
        .catch(error => {
            console.error('Error loading districts:', error);
        });
}

// Add district select control to sidebar
function addDistrictSelectControl(districts) {
    const regionSection = document.querySelector('.sidebar-section');
    if (!regionSection) return;
    
    const districtHTML = `
        <div class="mt-3 pt-3 border-top">
            <h6>Enhanced Visualization</h6>
            <div class="mb-2">
                <label for="districtEnhancedSelect" class="form-label">Select District for Enhanced View</label>
                <select class="form-select" id="districtEnhancedSelect">
                    <option value="">-- Select District --</option>
                    ${districts.map(d => `<option value="${d}">${d}</option>`).join('')}
                </select>
            </div>
            <button class="btn btn-primary w-100" id="loadBoundaryBtn" disabled>
                Load District Boundary
            </button>
            <button class="btn btn-info w-100 mt-2" id="showTaluksBtn" disabled>
                Show Taluks
            </button>
        </div>
    `;
    
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = districtHTML;
    regionSection.appendChild(tempDiv.firstElementChild);
    
    document.getElementById('districtEnhancedSelect').addEventListener('change', function() {
        const selected = this.value;
        document.getElementById('loadBoundaryBtn').disabled = !selected;
        document.getElementById('showTaluksBtn').disabled = !selected;
    });
    
    document.getElementById('loadBoundaryBtn').addEventListener('click', loadDistrictBoundary);
    document.getElementById('showTaluksBtn').addEventListener('click', loadAndShowTaluks);
}

// Load and display district boundary
function loadDistrictBoundary() {
    const district = document.getElementById('districtEnhancedSelect').value;
    if (!district) return;
    
    const btn = document.getElementById('loadBoundaryBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Loading...';
    
    fetch(`/api/district-boundary/${encodeURIComponent(district)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Remove existing boundary if any
            if (districtBoundaryLayer) {
                map.removeLayer(districtBoundaryLayer);
            }
            
            // Add new boundary
            districtBoundaryLayer = L.geoJSON(data, {
                style: {
                    fillColor: 'transparent',
                    fillOpacity: 0,
                    color: '#FF0000',
                    weight: 3,
                    opacity: 0.8,
                    dashArray: '10, 5'
                }
            }).addTo(map);
            
            // Fit map to boundary
            map.fitBounds(districtBoundaryLayer.getBounds());
            
            // Update current bounds for analysis
            const bounds = districtBoundaryLayer.getBounds();
            currentBounds = [
                bounds.getSouth(),
                bounds.getWest(),
                bounds.getNorth(),
                bounds.getEast()
            ];
            
            document.getElementById('analyzeBtn').disabled = false;
            updateAreaInfo(bounds);
            
            btn.disabled = false;
            btn.innerHTML = 'Load District Boundary';
            
            Swal.fire({
                icon: 'success',
                title: 'Boundary Loaded',
                text: `${district} district boundary loaded successfully!`,
                timer: 2000,
                showConfirmButton: false
            });
            
        })
        .catch(error => {
            console.error('Error loading boundary:', error);
            btn.disabled = false;
            btn.innerHTML = 'Load District Boundary';
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: `Failed to load boundary: ${error.message}`
            });
        });
}

// Load and display taluks with crop information
function loadAndShowTaluks() {
    const district = document.getElementById('districtEnhancedSelect').value;
    if (!district) return;
    
    const btn = document.getElementById('showTaluksBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Loading...';
    
    fetch(`/api/taluks/${encodeURIComponent(district)}`)
        .then(response => response.json())
        .then(data => {
            const taluks = data.taluks || [];
            
            // Clear existing taluk markers
            talukMarkers.clearLayers();
            
            // Add markers for each taluk
            taluks.forEach(taluk => {
                const marker = L.marker([taluk.lat, taluk.lng], {
                    icon: L.divIcon({
                        className: 'taluk-marker',
                        html: `<div class="taluk-marker-icon">
                                   <i class="bi bi-info-circle-fill" style="color: #2196F3; font-size: 24px;"></i>
                               </div>`,
                        iconSize: [30, 30],
                        iconAnchor: [15, 15]
                    })
                }).addTo(talukMarkers);
                
                const cropPercentage = ((taluk.area_ha / 500000) * 100).toFixed(2);
                
                marker.bindPopup(`
                    <div class="taluk-popup" style="min-width: 200px;">
                        <h6 class="mb-2 border-bottom pb-2">${taluk.name} Taluk</h6>
                        <div class="mb-1">
                            <strong>Major Crops:</strong><br>
                            ${taluk.major_crops}
                        </div>
                        <div class="mt-2">
                            <strong>Area Coverage:</strong><br>
                            ${taluk.area_ha.toLocaleString()} hectares
                            <br>
                            <small class="text-muted">(~${cropPercentage}% of district)</small>
                        </div>
                    </div>
                `, {
                    maxWidth: 300
                });
                
                // Add hover effect
                marker.on('mouseover', function() {
                    this.openPopup();
                });
            });
            
            btn.disabled = false;
            btn.innerHTML = 'Show Taluks';
            
            Swal.fire({
                icon: 'success',
                title: 'Taluks Loaded',
                text: `${taluks.length} taluks displayed with crop information`,
                timer: 2000,
                showConfirmButton: false
            });
            
        })
        .catch(error => {
            console.error('Error loading taluks:', error);
            btn.disabled = false;
            btn.innerHTML = 'Show Taluks';
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Failed to load taluks information'
            });
        });
}

// Add custom legend control
function addLegendControl() {
    // Create legend control
    const LegendControl = L.Control.extend({
        options: {
            position: 'bottomright'
        },
        
        onAdd: function(map) {
            const container = L.DomUtil.create('div', 'crop-legend-control');
            container.innerHTML = `
                <div class="legend-content" style="background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);">
                    <h6 style="margin: 0 0 10px 0; font-size: 14px; font-weight: bold;">Crop Distribution Legend</h6>
                    <div id="legendItems" style="font-size: 12px;">
                        <div style="color: #666;">Select and analyze a region to view crop distribution</div>
                    </div>
                </div>
            `;
            
            // Prevent map clicks when interacting with legend
            L.DomEvent.disableClickPropagation(container);
            
            return container;
        }
    });
    
    legendControl = new LegendControl();
    map.addControl(legendControl);
}

// Update legend with crop distribution data
function updateLegend(distribution) {
    const legendItems = document.getElementById('legendItems');
    if (!legendItems) return;
    
    const crops = distribution.crops || {};
    const totalArea = distribution.total_area_hectares || 0;
    
    let legendHTML = '';
    
    // Sort crops by area descending
    const sortedCrops = Object.entries(crops).sort((a, b) => b[1].area_hectares - a[1].area_hectares);
    
    sortedCrops.forEach(([cropId, cropData]) => {
        const emoji = {
            'Cash Crops': '🌾',
            'Millets/Pulses': '🌾',
            'Paddy/Rice': '🌾',
            'Fallow/Barren': '⚪'
        }[cropData.crop_name] || '🌾';
        
        legendHTML += `
            <div style="margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center;">
                    <div style="width: 16px; height: 16px; background: ${cropData.color}; margin-right: 8px; border: 1px solid #999; border-radius: 2px;"></div>
                    <span>${emoji} ${cropData.crop_name}</span>
                </div>
                <div style="text-align: right; margin-left: 10px;">
                    <strong>${cropData.percentage}%</strong><br>
                    <small style="color: #666;">${cropData.area_hectares.toLocaleString()} ha</small>
                </div>
            </div>
        `;
    });
    
    legendHTML += `
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd; font-weight: bold;">
            Total Area: ${totalArea.toLocaleString()} ha
        </div>
    `;
    
    legendItems.innerHTML = legendHTML;
}

// Load enhanced crop overlay with boundaries
function loadCropOverlayWithBoundary() {
    const district = document.getElementById('districtEnhancedSelect').value;
    
    if (!currentBounds) {
        Swal.fire({
            icon: 'warning',
            title: 'No Area Selected',
            text: 'Please select a district boundary first!'
        });
        return;
    }
    
    Swal.fire({
        title: 'Generating Enhanced Crop Overlay',
        html: '<i class="bi bi-gear-fill fs-1"></i><br>Processing satellite data...',
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    fetch('/api/crop-overlay', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            bounds: currentBounds,
            district: district,
            grid_size: 30
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Remove existing overlay if any
            if (cropOverlayLayer) {
                map.removeLayer(cropOverlayLayer);
            }
            
            // Add crop overlay
            cropOverlayLayer = L.geoJSON(data.crop_overlay, {
                style: function(feature) {
                    return {
                        fillColor: feature.properties.color,
                        fillOpacity: 0.5,
                        color: feature.properties.color,
                        weight: 0.5,
                        opacity: 0.7
                    };
                },
                onEachFeature: function(feature, layer) {
                    layer.bindPopup(`
                        <strong>${feature.properties.crop_name}</strong>
                    `);
                }
            }).addTo(map);
            
            // Update legend
            updateLegend(data.distribution);
            
            Swal.fire({
                icon: 'success',
                title: 'Overlay Complete',
                html: `
                    <div style="text-align: left;">
                        <h6>Crop Distribution Loaded</h6>
                        <p>Primary Crop: <strong>${data.distribution.crops[data.primary_crop_id].crop_name}</strong></p>
                        <p>Total Area Analyzed: <strong>${data.distribution.total_area_hectares.toLocaleString()} hectares</strong></p>
                    </div>
                `,
                confirmButtonColor: '#198754'
            });
            
        } else {
            throw new Error(data.error || 'Unknown error');
        }
    })
    .catch(error => {
        console.error('Error generating overlay:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Failed to generate crop overlay: ' + error.message
        });
    });
}

// Initialize boundary features when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for main map to initialize
    setTimeout(initBoundaryFeatures, 1000);
});

// Add button to trigger enhanced overlay from existing analyze button
const originalAnalyzeCrops = window.analyzeCrops;
window.analyzeCropsEnhanced = function() {
    const district = document.getElementById('districtEnhancedSelect');
    if (district && district.value) {
        loadCropOverlayWithBoundary();
    } else {
        originalAnalyzeCrops();
    }
};
