// Dashboard JavaScript functionality

let currentUser = null;
let websocket = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
});

async function initializeDashboard() {
    try {
        // Check authentication
        await checkAuthentication();
        
        // Load dashboard data
        await loadDashboardData();
        
        // Initialize WebSocket connection
        initializeWebSocket();
        
        // Set up periodic data refresh
        setInterval(loadDashboardData, 30000); // Refresh every 30 seconds
        
    } catch (error) {
        console.error('Dashboard initialization error:', error);
        showError('Failed to initialize dashboard');
    }
}

// Authentication check
async function checkAuthentication() {
    const token = localStorage.getItem('access_token');
    
    if (!token) {
        redirectToLogin();
        return;
    }
    
    try {
        const response = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            document.getElementById('userWelcome').textContent = `Welcome, ${currentUser.full_name}`;
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        redirectToLogin();
    }
}

// Load dashboard data
async function loadDashboardData() {
    try {
        const token = localStorage.getItem('access_token');
        
        // Load overview data
        const overviewResponse = await fetch('/api/dashboard/overview', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (overviewResponse.ok) {
            const overviewData = await overviewResponse.json();
            updateDashboardMetrics(overviewData);
        }
        
        // Load recent jobs
        const jobsResponse = await fetch('/api/dashboard/jobs?limit=5', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (jobsResponse.ok) {
            const jobsData = await jobsResponse.json();
            updateRecentJobs(jobsData.jobs);
        }
        
        // Load mappings
        const mappingsResponse = await fetch('/api/mappings/', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (mappingsResponse.ok) {
            const mappingsData = await mappingsResponse.json();
            updateMappingsList(mappingsData.mappings);
        }
        
        // Load mappings for import modal
        await loadMappingsForModal();
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

// Update dashboard metrics
function updateDashboardMetrics(data) {
    if (data.metrics) {
        document.getElementById('totalImports').textContent = data.metrics.total_jobs || 0;
        document.getElementById('successRate').textContent = `${data.metrics.success_rate || 0}%`;
        document.getElementById('todayJobs').textContent = data.metrics.today_jobs || 0;
        document.getElementById('activeMonitoring').textContent = data.metrics.active_monitoring || 0;
    }
}

// Update recent jobs list
function updateRecentJobs(jobs) {
    const jobsContainer = document.getElementById('recentJobs');
    
    if (!jobs || jobs.length === 0) {
        jobsContainer.innerHTML = '<div class="empty-state">No recent import jobs</div>';
        return;
    }
    
    jobsContainer.innerHTML = jobs.map(job => `
        <div class="job-item">
            <div class="job-header">
                <span class="job-filename">${escapeHtml(job.filename)}</span>
                <span class="job-status status-${job.status}">${job.status}</span>
            </div>
            <div class="job-details">
                <span>Records: ${job.processed_records || 0}/${job.total_records || 0}</span>
                <span>${formatDate(job.created_at)}</span>
            </div>
            ${job.status === 'processing' ? '<div class="progress-bar"><div class="progress-fill" style="width: ${calculateProgress(job)}%"></div></div>' : ''}
        </div>
    `).join('');
}

// Update mappings list
function updateMappingsList(mappings) {
    const mappingsContainer = document.getElementById('mappingsList');
    
    if (!mappings || mappings.length === 0) {
        mappingsContainer.innerHTML = `
            <div class="empty-state">
                <p>No column mappings yet</p>
                <button onclick="location.href='/mapping/create'" class="btn btn-primary" style="margin-top: 10px;">
                    Create Your First Mapping
                </button>
            </div>
        `;
        return;
    }
    
    mappingsContainer.innerHTML = mappings.map(mapping => `
        <div class="mapping-item">
            <h4>${escapeHtml(mapping.mapping_name)}</h4>
            <p>${escapeHtml(mapping.description || 'No description')}</p>
            <div class="mapping-stats">
                <span>ERP: ${mapping.erp_endpoint}</span>
                <span>Fields: ${Object.keys(mapping.target_columns || {}).length}</span>
            </div>
            <button onclick="useMapping('${mapping.id}')" class="btn btn-outline btn-sm">
                Use This Mapping
            </button>
        </div>
    `).join('');
}

// Load mappings for import modal
async function loadMappingsForModal() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/mappings/', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('mappingSelect');
            
            select.innerHTML = '<option value="">Choose a mapping configuration...</option>' +
                data.mappings.map(mapping => 
                    `<option value="${mapping.id}">${escapeHtml(mapping.mapping_name)}</option>`
                ).join('');
        }
    } catch (error) {
        console.error('Error loading mappings for modal:', error);
    }
}

// Import Modal Functions
function showImportModal() {
    document.getElementById('importModal').style.display = 'block';
}

function closeImportModal() {
    document.getElementById('importModal').style.display = 'none';
    document.getElementById('importForm').reset();
}

// Use specific mapping
function useMapping(mappingId) {
    document.getElementById('mappingSelect').value = mappingId;
    showImportModal();
}

// Test ERP Connection
async function testERPConnection() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/monitoring/system/health', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const erpStatus = data.health.erp_connection;
            
            if (erpStatus === 'healthy' || erpStatus === 'not configured') {
                alert(`ERP Connection: ${erpStatus === 'healthy' ? '✅ Connected and healthy' : 'ℹ️ Not configured'}`);
            } else {
                alert(`❌ ERP Connection issue: ${erpStatus}`);
            }
        } else {
            alert('Error testing ERP connection');
        }
    } catch (error) {
        alert('Error testing ERP connection: ' + error.message);
    }
}

// Handle Import Form Submission
document.getElementById('importForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const mappingId = document.getElementById('mappingSelect').value;
    const fileInput = document.getElementById('excelFile');
    
    if (!mappingId) {
        alert('Please select a mapping configuration');
        return;
    }
    
    if (!fileInput.files[0]) {
        alert('Please select a file to upload');
        return;
    }
    
    const formData = new FormData();
    formData.append('mapping_id', mappingId);
    formData.append('file', fileInput.files[0]);
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/import/excel', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(`✅ Import started!\nJob ID: ${result.job_id}`);
            closeImportModal();
            
            // Redirect to status page
            setTimeout(() => {
                window.location.href = '/upload/status';
            }, 1000);
            
        } else {
            alert('❌ Import failed: ' + (result.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error starting import: ' + error.message);
    }
});

// WebSocket Functions
function initializeWebSocket() {
    if (!currentUser) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/monitoring/ws/${currentUser.id}`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function() {
        updateWebSocketStatus(true);
        console.log('WebSocket connected');
    };
    
    websocket.onclose = function() {
        updateWebSocketStatus(false);
        console.log('WebSocket disconnected');
        
        // Attempt reconnect after 5 seconds
        setTimeout(initializeWebSocket, 5000);
    };
    
    websocket.onmessage = function(event) {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
    };
    
    websocket.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateWebSocketStatus(false);
    };
}

function updateWebSocketStatus(connected) {
    const statusElement = document.getElementById('websocketStatus');
    if (statusElement) {
        statusElement.className = `websocket-status ${connected ? 'connected' : 'disconnected'}`;
        statusElement.innerHTML = connected ? '🟢 Connected' : '🔴 Disconnected';
    }
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'job_update':
            // Update specific job in the UI
            updateJobInUI(message.data);
            break;
            
        case 'progress_update':
            // Update progress for a job
            updateJobProgress(message.job_id, message.progress);
            break;
            
        case 'system_message':
            console.log('System message:', message.message);
            break;
            
        case 'error':
            console.error('WebSocket error:', message.data);
            break;
    }
}

function updateJobInUI(jobData) {
    // Implementation would update specific job in the jobs list
    console.log('Job update:', jobData);
}

function updateJobProgress(jobId, progress) {
    // Implementation would update progress bar for specific job
    console.log('Progress update:', jobId, progress);
}

// Utility Functions
function redirectToLogin() {
    // Clear stored token
    localStorage.removeItem('access_token');
    // Redirect to login (would be implemented in a real app)
    alert('Please log in again');
    // window.location.href = '/login';
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function calculateProgress(job) {
    if (!job.total_records) return 0;
    return Math.round((job.processed_records / job.total_records) * 100);
}

function showError(message) {
    // Simple error display - could be enhanced with a proper notification system
    alert('Error: ' + message);
}

// Logout functionality
document.getElementById('logoutBtn').addEventListener('click', async function() {
    try {
        const token = localStorage.getItem('access_token');
        
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        // Clear local storage and redirect
        localStorage.removeItem('access_token');
        redirectToLogin();
    }
});

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('importModal');
    if (event.target === modal) {
        closeImportModal();
    }
    }
