// Dashboard JavaScript functionality - Enhanced for Rangoon Middleware

let currentUser = null;
let websocket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Circuit Breaker State
let circuitBreakerState = {
    erp: 'closed',
    lastStateChange: null,
    failureCount: 0,
    lastCheck: null
};

// System Metrics
let systemMetrics = {
    activeConnections: 0,
    systemHealth: 'healthy',
    queueSize: 0,
    processingRate: 0
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    initializeNotificationSystem();
});

// Enhanced dashboard initialization
async function initializeDashboard() {
    try {
        console.log('🚀 Initializing Rangoon Middleware Dashboard...');
        
        // Check authentication
        await checkAuthentication();
        
        // Load all initial data in parallel
        await Promise.allSettled([
            loadDashboardData(),
            loadCircuitBreakerStatus(),
            loadRealTimeMetrics(),
            loadMappingsForModal()
        ]);
        
        // Initialize WebSocket connection
        initializeWebSocket();
        
        // Set up periodic data refresh
        setInterval(loadDashboardData, 30000); // Refresh every 30 seconds
        setInterval(loadCircuitBreakerStatus, 15000); // Circuit breaker checks every 15s
        setInterval(loadRealTimeMetrics, 10000); // Metrics every 10s
        
        // Initialize event listeners
        initializeEventListeners();
        
        console.log('✅ Dashboard initialized successfully');
        showNotification('Dashboard connected successfully', 'success');
        
    } catch (error) {
        console.error('❌ Dashboard initialization error:', error);
        showError('Failed to initialize dashboard. Please refresh the page.');
        
        // Try to reconnect after error
        setTimeout(initializeDashboard, 5000);
    }
}

// Enhanced authentication check
async function checkAuthentication() {
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (!token) {
        redirectToLogin();
        return;
    }
    
    try {
        const response = await fetchWithRetry('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            updateUserInterface();
        } else if (response.status === 401 && refreshToken) {
            // Try to refresh token
            await refreshAccessToken();
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        redirectToLogin();
    }
}

// Token refresh functionality
async function refreshAccessToken() {
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        
        if (response.ok) {
            const data = await response.json();
            localStorage.setItem('access_token', data.access_token);
            // Retry the original request
            await checkAuthentication();
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Token refresh error:', error);
        redirectToLogin();
    }
}

// Update user interface after authentication
function updateUserInterface() {
    const userWelcome = document.getElementById('userWelcome');
    const userRole = document.getElementById('userRole');
    
    if (userWelcome) {
        userWelcome.textContent = `Welcome, ${currentUser.full_name || currentUser.email}`;
    }
    
    if (userRole && currentUser.role) {
        userRole.textContent = `(${currentUser.role})`;
    }
}

// Enhanced dashboard data loading with retry logic
async function loadDashboardData() {
    try {
        const token = localStorage.getItem('access_token');
        
        // Load overview data
        const overviewResponse = await fetchWithRetry('/api/dashboard/overview', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (overviewResponse.ok) {
            const overviewData = await overviewResponse.json();
            updateDashboardMetrics(overviewData);
        }
        
        // Load recent jobs
        const jobsResponse = await fetchWithRetry('/api/dashboard/jobs?limit=5', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (jobsResponse.ok) {
            const jobsData = await jobsResponse.json();
            updateRecentJobs(jobsData.jobs);
        }
        
        // Load mappings
        const mappingsResponse = await fetchWithRetry('/api/mappings/', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (mappingsResponse.ok) {
            const mappingsData = await mappingsResponse.json();
            updateMappingsList(mappingsData.mappings);
        }
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        if (error.message.includes('failed after')) {
            showNotification('Connection unstable. Some data may not be current.', 'warning');
        }
    }
}

// Update dashboard metrics with enhanced visual feedback
function updateDashboardMetrics(data) {
    if (data.metrics) {
        const metrics = data.metrics;
        
        // Update metric values with animation
        animateValue('totalImports', metrics.total_jobs || 0);
        animateValue('todayJobs', metrics.today_jobs || 0);
        animateValue('activeMonitoring', metrics.active_monitoring || 0);
        
        // Update success rate with color coding
        const successRateElement = document.getElementById('successRate');
        if (successRateElement) {
            const successRate = metrics.success_rate || 0;
            successRateElement.textContent = `${successRate}%`;
            
            // Color code based on success rate
            if (successRate >= 90) {
                successRateElement.style.color = '#28a745';
            } else if (successRate >= 75) {
                successRateElement.style.color = '#ffc107';
            } else {
                successRateElement.style.color = '#dc3545';
            }
        }
        
        // Update additional metrics if available
        if (metrics.average_processing_time) {
            const processingTimeElement = document.getElementById('avgProcessingTime');
            if (processingTimeElement) {
                processingTimeElement.textContent = `${metrics.average_processing_time}s`;
            }
        }
    }
}

// Animate value changes
function animateValue(elementId, targetValue, duration = 1000) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const startValue = parseInt(element.textContent) || 0;
    const startTime = performance.now();
    
    function updateValue(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentValue = Math.floor(startValue + (targetValue - startValue) * progress);
        element.textContent = currentValue;
        
        if (progress < 1) {
            requestAnimationFrame(updateValue);
        }
    }
    
    requestAnimationFrame(updateValue);
}

// Enhanced recent jobs list with real-time updates
function updateRecentJobs(jobs) {
    const jobsContainer = document.getElementById('recentJobs');
    
    if (!jobs || jobs.length === 0) {
        jobsContainer.innerHTML = `
            <div class="empty-state">
                <p>No recent import jobs</p>
                <button onclick="showImportModal()" class="btn btn-primary" style="margin-top: 10px;">
                    Start Your First Import
                </button>
            </div>
        `;
        return;
    }
    
    jobsContainer.innerHTML = jobs.map(job => `
        <div class="job-item" data-job-id="${job.id}">
            <div class="job-header">
                <span class="job-filename" title="${escapeHtml(job.filename)}">
                    ${escapeHtml(truncateFilename(job.filename))}
                </span>
                <span class="job-status status-${job.status} status-pulse">
                    ${job.status}
                </span>
            </div>
            <div class="job-details">
                <span class="progress-text">Records: ${job.processed_records || 0}/${job.total_records || 0}</span>
                <span>${formatDate(job.created_at)}</span>
            </div>
            ${job.status === 'processing' ? `
                <div class="progress-container">
                    <div class="progress-bar animated">
                        <div class="progress-fill" style="width: ${calculateProgress(job)}%"></div>
                    </div>
                </div>
            ` : ''}
            ${job.error_message ? `
                <div class="job-error" style="color: #dc3545; font-size: 12px; margin-top: 8px;">
                    ${escapeHtml(job.error_message)}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Enhanced mappings list
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
        <div class="mapping-item" data-mapping-id="${mapping.id}">
            <h4>${escapeHtml(mapping.mapping_name)}</h4>
            <p>${escapeHtml(mapping.description || 'No description provided')}</p>
            <div class="mapping-stats">
                <span>ERP: ${mapping.erp_endpoint}</span>
                <span>Fields: ${Object.keys(mapping.target_columns || {}).length}</span>
                <span>Used: ${mapping.usage_count || 0} times</span>
            </div>
            <div class="mapping-actions" style="display: flex; gap: 8px; margin-top: 10px;">
                <button onclick="useMapping('${mapping.id}')" class="btn btn-outline btn-sm">
                    Use This Mapping
                </button>
                <button onclick="testMapping('${mapping.id}')" class="btn btn-info btn-sm">
                    Test
                </button>
            </div>
        </div>
    `).join('');
}

// Load mappings for import modal with enhanced error handling
async function loadMappingsForModal() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetchWithRetry('/api/mappings/', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('mappingSelect');
            
            if (select) {
                select.innerHTML = '<option value="">Choose a mapping configuration...</option>' +
                    data.mappings.map(mapping => 
                        `<option value="${mapping.id}" data-erp="${mapping.erp_endpoint}">
                            ${escapeHtml(mapping.mapping_name)} (${mapping.erp_endpoint})
                         </option>`
                    ).join('');
                
                // Add change event to show ERP endpoint info
                select.addEventListener('change', function() {
                    updateMappingInfo(this.value, this.options[this.selectedIndex]?.dataset.erp);
                });
            }
        }
    } catch (error) {
        console.error('Error loading mappings for modal:', error);
        showNotification('Failed to load mapping configurations', 'error');
    }
}

function updateMappingInfo(mappingId, erpEndpoint) {
    const mappingInfo = document.getElementById('mappingInfo');
    if (mappingInfo) {
        if (mappingId && erpEndpoint) {
            mappingInfo.innerHTML = `
                <div style="background: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 10px;">
                    <strong>ERP Endpoint:</strong> ${escapeHtml(erpEndpoint)}<br>
                    <small>This mapping will send data to the specified ERP system</small>
                </div>
            `;
        } else {
            mappingInfo.innerHTML = '';
        }
    }
}

// Circuit Breaker Functions
async function loadCircuitBreakerStatus() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetchWithRetry('/api/monitoring/circuit-breaker', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            circuitBreakerState = data.circuit_breaker;
            updateCircuitBreakerUI();
        }
    } catch (error) {
        console.error('Error loading circuit breaker status:', error);
    }
}

function updateCircuitBreakerUI() {
    const circuitStatusElement = document.getElementById('circuitBreakerStatus');
    if (circuitStatusElement) {
        circuitStatusElement.className = `circuit-status circuit-${circuitBreakerState.erp}`;
        circuitStatusElement.innerHTML = `
            <span class="circuit-status-icon"></span>
            ERP: ${circuitBreakerState.erp.toUpperCase()}
            ${circuitBreakerState.failureCount > 0 ? 
                `<small style="display: block; font-size: 10px;">Failures: ${circuitBreakerState.failureCount}</small>` : 
                ''
            }
        `;
        
        // Update tooltip or additional info
        circuitStatusElement.title = `Last state change: ${formatDate(circuitBreakerState.lastStateChange)}`;
    }
}

// Real-time Metrics Functions
async function loadRealTimeMetrics() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetchWithRetry('/api/monitoring/metrics', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            systemMetrics = data.metrics;
            updateRealTimeMetricsUI();
        }
    } catch (error) {
        console.error('Error loading real-time metrics:', error);
    }
}

function updateRealTimeMetricsUI() {
    // Update active connections
    const connectionsElement = document.getElementById('activeConnections');
    if (connectionsElement && systemMetrics.activeConnections !== undefined) {
        connectionsElement.textContent = systemMetrics.activeConnections;
    }
    
    // Update system health
    const healthElement = document.getElementById('systemHealth');
    if (healthElement && systemMetrics.systemHealth) {
        healthElement.textContent = systemMetrics.systemHealth;
        healthElement.className = `health-status ${systemMetrics.systemHealth}`;
    }
    
    // Update additional metrics
    if (systemMetrics.queueSize !== undefined) {
        const queueElement = document.getElementById('queueSize');
        if (queueElement) {
            queueElement.textContent = systemMetrics.queueSize;
        }
    }
    
    if (systemMetrics.processingRate !== undefined) {
        const rateElement = document.getElementById('processingRate');
        if (rateElement) {
            rateElement.textContent = `${systemMetrics.processingRate}/sec`;
        }
    }
}

// Enhanced WebSocket Functions
function initializeWebSocket() {
    if (!currentUser) {
        console.log('No current user, skipping WebSocket initialization');
        return;
    }
    
    // Close existing connection if any
    if (websocket && (websocket.readyState === WebSocket.OPEN || websocket.readyState === WebSocket.CONNECTING)) {
        websocket.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/monitoring/ws/${currentUser.id}`;
    
    console.log('🔌 Connecting to WebSocket:', wsUrl);
    
    try {
        websocket = new WebSocket(wsUrl);
        
        websocket.onopen = function() {
            console.log('✅ WebSocket connected successfully');
            reconnectAttempts = 0;
            updateWebSocketStatus(true);
            
            // Subscribe to channels
            websocket.send(JSON.stringify({
                type: 'subscribe',
                channels: ['job_updates', 'system_health', 'circuit_breaker', 'connection_stats']
            }));
            
            showNotification('Real-time monitoring connected', 'success');
        };
        
        websocket.onclose = function(event) {
            console.log('🔌 WebSocket disconnected:', event.code, event.reason);
            updateWebSocketStatus(false);
            
            if (event.code !== 1000) { // Not a normal closure
                attemptReconnect();
            }
        };
        
        websocket.onmessage = function(event) {
            try {
                const message = JSON.parse(event.data);
                console.log('📨 WebSocket message received:', message.type);
                handleWebSocketMessage(message);
            } catch (error) {
                console.error('❌ Error parsing WebSocket message:', error);
            }
        };
        
        websocket.onerror = function(error) {
            console.error('❌ WebSocket error:', error);
            updateWebSocketStatus(false);
        };
        
    } catch (error) {
        console.error('❌ Error initializing WebSocket:', error);
        updateWebSocketStatus(false);
        attemptReconnect();
    }
}

function attemptReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
        
        console.log(`🔄 Attempting to reconnect... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}) in ${delay}ms`);
        
        showNotification(`Connection lost. Reconnecting in ${delay/1000}s...`, 'warning');
        
        setTimeout(() => {
            initializeWebSocket();
        }, delay);
    } else {
        console.error('❌ Max reconnection attempts reached');
        showNotification('Real-time connection failed. Please refresh the page.', 'error');
    }
}

function updateWebSocketStatus(connected) {
    const statusElement = document.getElementById('websocketStatus');
    if (statusElement) {
        statusElement.className = `websocket-status ${connected ? 'connected' : 'disconnected'}`;
        statusElement.innerHTML = connected ? 
            '🟢 Real-time Connected' : 
            '🔴 Real-time Disconnected';
        
        // Update title with connection info
        statusElement.title = connected ? 
            'Connected to real-time monitoring service' : 
            'Disconnected - updates will be delayed';
    }
}

// Enhanced WebSocket message handling
function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'job_update':
            console.log('📊 Job update received:', message.data.id);
            updateJobInUI(message.data);
            break;
            
        case 'progress_update':
            console.log('📈 Progress update:', message.job_id, message.progress);
            updateJobProgress(message.job_id, message.progress);
            break;
            
        case 'circuit_breaker_update':
            console.log('⚡ Circuit breaker update:', message.data.erp);
            circuitBreakerState = message.data;
            updateCircuitBreakerUI();
            showNotification(`Circuit Breaker: ${message.data.erp.toUpperCase()} state`, 'info');
            break;
            
        case 'system_health':
            console.log('🏥 System health update:', message.data);
            systemMetrics.systemHealth = message.data.overall;
            updateRealTimeMetricsUI();
            break;
            
        case 'connection_count':
            console.log('👥 Connection count:', message.count);
            systemMetrics.activeConnections = message.count;
            updateRealTimeMetricsUI();
            break;
            
        case 'batch_complete':
            console.log('✅ Batch complete:', message.batch_id);
            showNotification(`Batch ${message.batch_id} completed successfully`, 'success');
            loadDashboardData(); // Refresh data
            break;
            
        case 'error':
            console.error('❌ WebSocket error:', message.data);
            showNotification(`System Error: ${message.data}`, 'error');
            break;
            
        default:
            console.log('📨 Unknown message type:', message.type, message);
    }
}

function updateJobInUI(jobData) {
    // Find and update specific job in the UI
    const jobElement = document.querySelector(`[data-job-id="${jobData.id}"]`);
    if (jobElement) {
        const statusElement = jobElement.querySelector('.job-status');
        const progressText = jobElement.querySelector('.progress-text');
        
        if (statusElement) {
            statusElement.className = `job-status status-${jobData.status}`;
            statusElement.textContent = jobData.status;
        }
        
        if (progressText) {
            progressText.textContent = `Records: ${jobData.processed_records || 0}/${jobData.total_records || 0}`;
        }
        
        // Update progress bar
        if (jobData.status === 'processing') {
            const progressFill = jobElement.querySelector('.progress-fill');
            if (progressFill) {
                const progress = calculateProgress(jobData);
                progressFill.style.width = `${progress}%`;
            }
        }
        
        // Add error message if present
        if (jobData.error_message && !jobElement.querySelector('.job-error')) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'job-error';
            errorDiv.style.cssText = 'color: #dc3545; font-size: 12px; margin-top: 8px;';
            errorDiv.textContent = jobData.error_message;
            jobElement.appendChild(errorDiv);
        }
    } else {
        // Job not in current list, refresh the list
        loadDashboardData();
    }
}

function updateJobProgress(jobId, progress) {
    const jobElement = document.querySelector(`[data-job-id="${jobId}"]`);
    if (jobElement) {
        const progressBar = jobElement.querySelector('.progress-fill');
        const progressText = jobElement.querySelector('.progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${progress.percentage}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${progress.processed}/${progress.total} records`;
        }
        
        // Add pulse animation for active processing
        jobElement.classList.add('processing-active');
    }
}

// Modal Functions
function showImportModal() {
    document.getElementById('importModal').style.display = 'block';
    document.getElementById('mappingInfo').innerHTML = '';
}

function closeImportModal() {
    document.getElementById('importModal').style.display = 'none';
    document.getElementById('importForm').reset();
    document.getElementById('mappingInfo').innerHTML = '';
    document.getElementById('fileInfo').innerHTML = '';
}

function useMapping(mappingId) {
    const select = document.getElementById('mappingSelect');
    if (select) {
        select.value = mappingId;
        // Trigger change event to update mapping info
        const event = new Event('change');
        select.dispatchEvent(event);
    }
    showImportModal();
}

// Test mapping functionality
async function testMapping(mappingId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/mappings/${mappingId}/test`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showNotification('Mapping test completed successfully', 'success');
        } else {
            const error = await response.json();
            showNotification(`Mapping test failed: ${error.detail}`, 'error');
        }
    } catch (error) {
        showNotification('Error testing mapping: ' + error.message, 'error');
    }
}

// Enhanced file input handling
function initializeEventListeners() {
    const fileInput = document.getElementById('excelFile');
    const importForm = document.getElementById('importForm');
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            const fileInfo = document.getElementById('fileInfo');
            
            if (file) {
                const fileSize = (file.size / 1024 / 1024).toFixed(2);
                fileInfo.innerHTML = `
                    <div style="background: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 10px;">
                        <strong>Selected file:</strong> ${escapeHtml(file.name)}<br>
                        <strong>Size:</strong> ${fileSize} MB<br>
                        <strong>Type:</strong> ${file.type || 'Unknown'}
                    </div>
                `;
            } else {
                fileInfo.innerHTML = '';
            }
        });
    }
    
    // Enhanced import form submission
    if (importForm) {
        importForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            const mappingId = document.getElementById('mappingSelect').value;
            const fileInput = document.getElementById('excelFile');
            const file = fileInput.files[0];
            
            // Validation
            if (!mappingId) {
                showNotification('Please select a mapping configuration', 'error');
                return;
            }
            
            if (!file) {
                showNotification('Please select a file to upload', 'error');
                return;
            }
            
            // Check file type
            const validTypes = [
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/csv'
            ];
            
            if (!validTypes.includes(file.type) && !file.name.match(/\.(xlsx|xls|csv)$/i)) {
                showNotification('Please select a valid Excel or CSV file', 'error');
                return;
            }
            
            // Check file size (max 50MB)
            if (file.size > 50 * 1024 * 1024) {
                showNotification('File size must be less than 50MB', 'error');
                return;
            }
            
            // Update button state
            submitBtn.innerHTML = '<span class="loading-spinner"></span> Starting Import...';
            submitBtn.disabled = true;
            
            const formData = new FormData();
            formData.append('mapping_id', mappingId);
            formData.append('file', file);
            
            try {
                const token = localStorage.getItem('access_token');
                const response = await fetch('/api/import/excel', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`
                        // Note: Don't set Content-Type for FormData, let browser set it
                    },
                    body: formData
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showNotification(`✅ Import started! Job ID: ${result.job_id}`, 'success');
                    closeImportModal();
                    
                    // Redirect to status page after a short delay
                    setTimeout(() => {
                        window.location.href = `/upload/status?job_id=${result.job_id}`;
                    }, 1500);
                    
                } else {
                    throw new Error(result.detail || `HTTP ${response.status}: ${response.statusText}`);
                }
            } catch (error) {
                console.error('Import error:', error);
                showNotification('❌ Import failed: ' + error.message, 'error');
            } finally {
                // Restore button state
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }
}

// Test ERP Connection with enhanced feedback
async function testERPConnection() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetchWithRetry('/api/monitoring/system/health', {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const erpStatus = data.health.erp_connection;
            
            let message, type;
            if (erpStatus === 'healthy') {
                message = '✅ ERP Connection: Connected and healthy';
                type = 'success';
            } else if (erpStatus === 'not configured') {
                message = 'ℹ️ ERP Connection: Not configured';
                type = 'info';
            } else {
                message = `❌ ERP Connection issue: ${erpStatus}`;
                type = 'error';
            }
            
            showNotification(message, type);
        } else {
            throw new Error('Failed to check ERP connection');
        }
    } catch (error) {
        showNotification('Error testing ERP connection: ' + error.message, 'error');
    }
}

// Enhanced utility functions
function fetchWithRetry(url, options = {}, maxRetries = 3) {
    return new Promise((resolve, reject) => {
        const attempt = (retryCount) => {
            fetch(url, options)
                .then(response => {
                    if (response.ok) {
                        resolve(response);
                    } else if (retryCount < maxRetries && response.status >= 500) {
                        // Retry on server errors
                        setTimeout(() => attempt(retryCount + 1), 1000 * retryCount);
                    } else {
                        resolve(response); // Resolve even with error to handle in caller
                    }
                })
                .catch(error => {
                    if (retryCount < maxRetries) {
                        setTimeout(() => attempt(retryCount + 1), 1000 * retryCount);
                    } else {
                        reject(error);
                    }
                });
        };
        
        attempt(0);
    });
}

function redirectToLogin() {
    // Clear stored tokens
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    // Redirect to login page
    window.location.href = '/login';
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return isNaN(date.getTime()) ? 'Invalid Date' : 
        date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function calculateProgress(job) {
    if (!job.total_records || job.total_records === 0) return 0;
    return Math.round(((job.processed_records || 0) / job.total_records) * 100);
}

function truncateFilename(filename, maxLength = 30) {
    if (!filename || filename.length <= maxLength) return filename;
    const extension = filename.split('.').pop();
    const name = filename.substring(0, filename.lastIndexOf('.'));
    const truncateLength = maxLength - extension.length - 4;
    return name.substring(0, truncateLength) + '...' + extension;
}

// Notification System
function initializeNotificationSystem() {
    // Create notification container if it doesn't exist
    if (!document.getElementById('notificationContainer')) {
        const container = document.createElement('div');
        container.id = 'notificationContainer';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 400px;
        `;
        document.body.appendChild(container);
    }
}

function showNotification(message, type = 'info') {
    const container = document.getElementById('notificationContainer');
    if (!container) return;
    
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : type === 'warning' ? '#fff3cd' : '#d1ecf1'};
        color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : type === 'warning' ? '#856404' : '#0c5460'};
        border: 1px solid ${type === 'success' ? '#c3e6cb' : type === 'error' ? '#f5c6cb' : type === 'warning' ? '#ffeaa7' : '#bee5eb'};
        padding: 12px 20px;
        margin-bottom: 10px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    
    container.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 5000);
}

function showError(message) {
    showNotification(message, 'error');
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .loading-spinner {
        display: inline-block;
        width: 14px;
        height: 14px;
        border: 2px solid rgba(255,255,255,0.3);
        border-radius: 50%;
        border-top-color: white;
        animation: spin 0.6s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    .processing-active {
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
`;
document.head.appendChild(style);

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.close();
    }
});

// Close modals when clicking outside
window.onclick = function(event) {
    const importModal = document.getElementById('importModal');
    if (event.target === importModal) {
        closeImportModal();
    }
};
