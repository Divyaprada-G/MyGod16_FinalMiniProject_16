/**
 * Interactive Folium Map Integration
 * Handles fetching and displaying enhanced district/taluk boundary visualization
 */

// Global variable to track current selected district
let selectedDistrictForMap = 'Tumkur';

/**
 * Open the interactive Folium map in a new window
 */
function openInteractiveMap() {
    // Check if a district is selected
    const districtSelect = document.getElementById('districtSelect');
    if (districtSelect && districtSelect.value) {
        selectedDistrictForMap = districtSelect.value;
    }
    
    // Also check enhanced district selector if available
    const enhancedDistrictSelect = document.getElementById('districtEnhancedSelect');
    if (enhancedDistrictSelect && enhancedDistrictSelect.value) {
        selectedDistrictForMap = enhancedDistrictSelect.value;
    }
    
    // Show loading message
    Swal.fire({
        title: 'Loading Interactive Map',
        html: `
            <div style="text-align: center; padding: 20px;">
                <i class="bi bi-map" style="font-size: 48px; color: #4CAF50;"></i>
                <p style="margin-top: 15px; font-size: 16px;">
                    Generating enhanced visualization for <strong>${selectedDistrictForMap}</strong> district...
                </p>
                <p style="color: #666; font-size: 14px;">
                    This may take a few moments
                </p>
            </div>
        `,
        allowOutsideClick: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    // Determine if we should include crop overlay data
    const includeCropOverlay = currentBounds ? true : false;
    
    // Prepare request data
    const requestData = {
        district: selectedDistrictForMap,
        bounds: currentBounds || null,
        include_crop_overlay: includeCropOverlay
    };
    
    // Fetch the Folium map HTML
    fetch('/api/folium-map', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        Swal.close();
        
        if (data.success && data.map_html) {
            // Open in a full-screen modal
            displayFoliumMapInModal(data.map_html, selectedDistrictForMap, data.has_crop_data);
        } else {
            throw new Error(data.error || 'Failed to generate map');
        }
    })
    .catch(error => {
        console.error('Error fetching interactive map:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error Loading Map',
            text: error.message || 'Failed to generate the interactive map. Please try again.',
            confirmButtonColor: '#d33'
        });
    });
}

/**
 * Display the Folium map HTML in a full-screen modal
 */
function displayFoliumMapInModal(mapHtml, districtName, hasCropData) {
    const cropDataInfo = hasCropData ? 
        '<span style="color: #4CAF50;"><i class="bi bi-check-circle-fill"></i> With Crop Classification Data</span>' :
        '<span style="color: #FF9800;"><i class="bi bi-info-circle-fill"></i> Boundary View Only</span>';
    
    Swal.fire({
        title: `${districtName} District - Enhanced Interactive Map`,
        html: `
            <div style="margin-bottom: 15px; padding: 10px; background-color: #f5f5f5; border-radius: 5px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>District:</strong> ${districtName}
                    </div>
                    <div>
                        ${cropDataInfo}
                    </div>
                </div>
                <p style="margin-top: 10px; margin-bottom: 0; font-size: 13px; color: #666;">
                    <i class="bi bi-info-circle"></i> Click taluk markers for detailed crop information. 
                    Use layer controls (top-right) to toggle views. Legend shows crop distribution (bottom-right).
                </p>
            </div>
            <div id="foliumMapContainer" style="width: 100%; height: 70vh; border: 2px solid #ddd; border-radius: 5px; overflow: hidden;">
                ${mapHtml}
            </div>
        `,
        width: '95%',
        showConfirmButton: true,
        confirmButtonText: '<i class="bi bi-x-circle"></i> Close Map',
        confirmButtonColor: '#6c757d',
        showCancelButton: true,
        cancelButtonText: '<i class="bi bi-box-arrow-up-right"></i> Open in New Tab',
        cancelButtonColor: '#0d6efd',
        customClass: {
            popup: 'folium-modal-popup',
            htmlContainer: 'folium-modal-content'
        },
        didOpen: () => {
            // Add custom styles for the modal
            const style = document.createElement('style');
            style.textContent = `
                .folium-modal-popup {
                    padding: 20px !important;
                    max-width: 95vw !important;
                }
                .folium-modal-content {
                    padding: 0 !important;
                    margin: 0 !important;
                    max-height: none !important;
                }
                #foliumMapContainer {
                    width: 100% !important;
                    height: 70vh !important;
                    position: relative !important;
                }
                #foliumMapContainer iframe {
                    width: 100% !important;
                    height: 100% !important;
                    border: none !important;
                }
                #foliumMapContainer > div {
                    width: 100% !important;
                    height: 100% !important;
                }
                
                /* Responsive adjustments for mobile */
                @media (max-width: 768px) {
                    .folium-modal-popup {
                        padding: 10px !important;
                        max-width: 98vw !important;
                    }
                    #foliumMapContainer {
                        height: 60vh !important;
                    }
                }
                
                @media (max-width: 480px) {
                    .folium-modal-popup {
                        padding: 5px !important;
                        max-width: 100vw !important;
                    }
                    #foliumMapContainer {
                        height: 55vh !important;
                    }
                }
            `;
            document.head.appendChild(style);
            
            // Add window resize listener for the modal map
            const resizeHandler = function() {
                const mapContainer = document.getElementById('foliumMapContainer');
                if (mapContainer) {
                    const iframe = mapContainer.querySelector('iframe');
                    if (iframe && iframe.contentWindow) {
                        // Try to trigger map resize in the iframe
                        try {
                            iframe.contentWindow.postMessage({type: 'resize'}, '*');
                        } catch (e) {
                            console.log('Could not send resize message to iframe');
                        }
                    }
                }
            };
            
            // Add resize listener
            window.addEventListener('resize', resizeHandler);
            
            // Initial resize after a short delay
            setTimeout(resizeHandler, 500);
        }
    }).then((result) => {
        // If user clicked "Open in New Tab" (cancel button)
        if (result.dismiss === Swal.DismissReason.cancel) {
            openInteractiveMapInNewTab(districtName);
        }
        // If user clicked "Close Map" (confirm button), modal will close automatically
    });
}

/**
 * Open the interactive map in a new browser tab
 */
function openInteractiveMapInNewTab(districtName) {
    const url = `/map/interactive/${encodeURIComponent(districtName)}`;
    window.open(url, '_blank');
    
    Swal.fire({
        icon: 'success',
        title: 'Map Opened',
        text: `Interactive map for ${districtName} district opened in a new tab`,
        timer: 2000,
        showConfirmButton: false
    });
}

/**
 * Quick access function to view Tumkur district map
 */
function viewTumkurMap() {
    selectedDistrictForMap = 'Tumkur';
    openInteractiveMap();
}

// Add keyboard shortcut to open interactive map (Ctrl+I or Cmd+I)
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'i') {
        e.preventDefault();
        openInteractiveMap();
    }
});

console.log('Interactive Folium Map integration loaded. Press Ctrl+I to open interactive map.');
