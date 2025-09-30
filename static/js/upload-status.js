// Upload Status & Monitoring JavaScript - Enhanced for Rangoon Middleware v2.0.0

let websocket = null;
let currentUser = null;
let refreshInterval = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// Initialize status page
document.addEventListener('DOMContentLoaded', function() {
    initializeStatusPage();
});

async function initializeStatusPage() {
    try {
        // Check authentication with enhanced security
        await checkAuthentication();
        
        // Load initial data with error handling
        await loadStatusData();
        
        // Initialize WebSocket with secure connection
        initializeWebSocket();
        
        // Set up auto-refresh with circuit breaker
        refreshInterval = setInterval(() => {
            loadStatusData().catch(error => {
                console.warn('Auto-refresh failed, will retry:', error);
            });
        }, 10000);
        
        // Set up enhanced filters
        setupFilters();
        
        // Initialize real-time metrics
        initializeRealTimeMetrics();
        
    } catch (error) {
        console.error('Status page initialization error:', error);
        showError('Failed to initialize status page: ' + error.message);
    }
}

// Enhanced Authentication check with token validation
async function checkAuthentication() {
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (!token) {
        redirectToLogin();
        return;
    }
    
    try {
        const response = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const userData = await response.json();
            currentUser = userData.user;
            
            // Update UI with user info
            updateUserInterface(userData.user);
        } else if (response.status === 401 && refreshToken) {
            // Attempt token refresh
            await refreshTokenAndRetry();
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        if (error.name !== 'TypeError') { // Skip network errors for retry
            redirectToLogin();
        }
    }
}

// Token refresh logic
async function refreshTokenAndRetry() {
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${refreshToken}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const tokenData = await response.json();
            localStorage.setItem('access_token', tokenData.access_token);
            localStorage.setItem('refresh_token', tokenData.refresh_token);
            
            // Retry original request
            await checkAuthentication();
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Token refresh error:', error);
        redirectToLogin();
    }
}

// Enhanced status data loading with batching
async function loadStatusData() {
    try {
        const token = localStorage.getItem('access_token');
        
        // Use Promise.all for parallel loading with error handling
        const [metricsResponse, jobsResponse, errorsResponse] = await Promise.allSettled([
            fetch('/api/monitoring/metrics', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'X-Request-ID': generateRequestId()
                }
            }),
            fetch('/api/import/jobs?limit=100&include=mappings,errors', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'X-Request-ID': generateRequestId()
                }
            }),
            fetch('/api/monitoring/errors?limit=20&severity=high,critical', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'X-Request-ID': generateRequestId()
                }
            })
        ]);

        // Process metrics
        if (metricsResponse.status === 'fulfilled' && metricsResponse.value.ok) {
            const metricsData = await metricsResponse.value.json();
            updateMetrics(metricsData.metrics);
            updateSystemHealth(metricsData.system_health);
        }

        // Process jobs
        if (jobsResponse.status === 'fulfilled' && jobsResponse.value.ok) {
            const jobsData = await jobsResponse.value.json();
            updateJobsTable(jobsData.jobs);
            updateActiveJobs(jobsData.jobs);
            updateJobStatistics(jobsData.statistics);
        }

        // Process errors
        if (errorsResponse.status === 'fulfilled' && errorsResponse.value.ok) {
            const errorsData = await errorsResponse.value.json();
            updateRecentErrors(errorsData.errors);
            updateErrorStatistics(errorsData.statistics);
        }

        // Handle failed requests
        handleFailedRequests([metricsResponse, jobsResponse, errorsResponse]);

    } catch (error) {
        console.error('Error loading status data:', error);
        showNotification('Failed to load some data. Retrying...', 'warning');
    }
}

// Enhanced metrics display with system health
function updateMetrics(metrics) {
    if (!metrics) return;
    
    // Basic metrics
    document.getElementById('totalJobs').textContent = metrics.total_jobs || 0;
    document.getElementById('successRate').textContent = `${metrics.success_rate || 0}%`;
    document.getElementById('activeJobs').textContent = metrics.processing_jobs || 0;
    document.getElementById('avgProcessingTime').textContent = formatProcessingTime(metrics.avg_processing_time);
    
    // Enhanced metrics for Rangoon Middleware
    if (metrics.erp_integration) {
        updateERPIntegrationMetrics(metrics.erp_integration);
    }
    
    if (metrics.circuit_breaker) {
        updateCircuitBreakerMetrics(metrics.circuit_breaker);
    }
}

// Update system health indicators
function updateSystemHealth(health) {
    if (!health) return;
    
    const healthElement = document.getElementById('systemHealth');
    if (healthElement) {
        const status = health.status || 'unknown';
        healthElement.className = `system-health status-${status}`;
        healthElement.innerHTML = `
            <span class="health-indicator"></span>
            ${status.toUpperCase()} 
            ${health.message ? `- ${health.message}` : ''}
        `;
    }
}

// Enhanced jobs table with mapping engine info
function updateJobsTable(jobs) {
    const tableBody = document.getElementById('jobsTableBody');
    
    if (!jobs || jobs.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="empty-icon">📊</div>
                    No import jobs found
                </td>
            </tr>
        `;
        return;
    }
    
    // Apply enhanced filters
    const statusFilter = document.getElementById('statusFilter').value;
    const searchFilter = document.getElementById('searchJobs').value.toLowerCase();
    const mappingFilter = document.getElementById('mappingFilter').value;
    
    const filteredJobs = jobs.filter(job => {
        const matchesStatus = statusFilter === 'all' || job.status === statusFilter;
        const matchesSearch = !searchFilter || 
            job.filename.toLowerCase().includes(searchFilter) ||
            job.job_id.toLowerCase().includes(searchFilter) ||
            (job.column_mappings && job.column_mappings.mapping_name.toLowerCase().includes(searchFilter));
        const matchesMapping = mappingFilter === 'all' || 
            (job.column_mappings && job.column_mappings.mapping_name === mappingFilter);
        
        return matchesStatus && matchesSearch && matchesMapping;
    });
    
    tableBody.innerHTML = filteredJobs.map(job => `
        <tr data-job-id="${job.job_id}" class="job-row status-${job.status}">
            <td>
                <span class="job-id">${job.job_id}</span>
                <br>
                <small class="text-muted">${formatDate(job.created_at)}</small>
            </td>
            <td>
                <div class="file-info">
                    <span class="filename">${escapeHtml(job.filename)}</span>
                    ${job.file_size ? `<br><small class="text-muted">${formatFileSize(job.file_size)}</small>` : ''}
                </div>
            </td>
            <td>
                ${job.column_mappings ? `
                    <span class="mapping-badge">${escapeHtml(job.column_mappings.mapping_name)}</span>
                    ${job.column_mappings.version ? `<br><small class="text-muted">v${job.column_mappings.version}</small>` : ''}
                ` : 'N/A'}
            </td>
            <td>
                <span class="job-status status-${job.status}">
                    <span class="status-dot"></span>
                    ${formatStatus(job.status)}
                </span>
                ${job.is_active ? '<span class="live-indicator" title="Live Monitoring">🔴</span>' : ''}
            </td>
            <td>
                ${job.status === 'processing' ? createEnhancedProgressBar(job) : 
                  job.status === 'completed' ? createCompletionBadge(job) : 
                  job.status === 'failed' ? createFailureBadge(job) : 
                  job.status === 'validating' ? createValidationBadge(job) : '⏳ Pending'}
            </td>
            <td>
                <div class="record-stats">
                    <span>${job.processed_records || 0}/${job.total_records || 0}</span>
                    ${job.failed_records > 0 ? `
                        <br><small class="text-danger">${job.failed_records} failed</small>
                    ` : ''}
                    ${job.erp_success_count > 0 ? `
                        <br><small class="text-success">${job.erp_success_count} ERP success</small>
                    ` : ''}
                </div>
            </td>
            <td>${formatRelativeTime(job.created_at)}</td>
            <td>
                <div class="job-actions">
                    <button onclick="showJobDetails('${job.job_id}')" class="btn btn-outline btn-sm" title="View Details">
                        <i class="icon-eye"></i> Details
                    </button>
                    ${job.status === 'failed' ? `
                        <button onclick="retryJob('${job.job_id}')" class="btn btn-primary btn-sm" title="Retry Job">
                            <i class="icon-refresh"></i> Retry
                        </button>
                    ` : ''}
                    ${job.status === 'processing' ? `
                        <button onclick="cancelJob('${job.job_id}')" class="btn btn-warning btn-sm" title="Cancel Job">
                            <i class="icon-cancel"></i> Cancel
                        </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

// Enhanced WebSocket with secure reconnection
function initializeWebSocket() {
    if (!currentUser) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/monitoring/ws/${currentUser.id}?token=${localStorage.getItem('access_token')}`;
    
    try {
        websocket = new WebSocket(wsUrl);
        
        websocket.onopen = function() {
            reconnectAttempts = 0;
            updateWebSocketStatus(true);
            console.log('WebSocket connected for real-time monitoring');
            
            // Subscribe to channels
            subscribeToChannels();
        };
        
        websocket.onclose = function(event) {
            updateWebSocketStatus(false);
            console.log(`WebSocket disconnected: ${event.code} - ${event.reason}`);
            
            // Enhanced reconnection logic with backoff
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                const backoffTime = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                console.log(`Reconnecting in ${backoffTime}ms...`);
                setTimeout(initializeWebSocket, backoffTime);
                reconnectAttempts++;
            } else {
                console.error('Max reconnection attempts reached');
                showNotification('Real-time updates disconnected. Please refresh the page.', 'error');
            }
        };
        
        websocket.onmessage = function(event) {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            updateWebSocketStatus(false);
        };
        
    } catch (error) {
        console.error('WebSocket initialization error:', error);
    }
}

// Subscribe to monitoring channels
function subscribeToChannels() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        const subscriptions = {
            type: 'subscribe',
            channels: [
                'job_updates',
                'progress_updates', 
                'system_alerts',
                'erp_integration',
                'circuit_breaker'
            ]
        };
        websocket.send(JSON.stringify(subscriptions));
    }
}

// Enhanced WebSocket message handling
function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'job_update':
            handleJobUpdate(message.data);
            break;
            
        case 'progress_update':
            handleProgressUpdate(message.data);
            break;
            
        case 'erp_batch_update':
            handleERPBatchUpdate(message.data);
            break;
            
        case 'circuit_breaker_status':
            handleCircuitBreakerStatus(message.data);
            break;
            
        case 'system_alert':
            handleSystemAlert(message.data);
            break;
            
        case 'validation_result':
            handleValidationResult(message.data);
            break;
            
        case 'connection_established':
            console.log('WebSocket connection established with session:', message.session_id);
            break;
            
        default:
            console.log('Unknown message type:', message.type);
    }
}

// Handle specific message types
function handleJobUpdate(jobData) {
    // Update specific job in the table
    const jobRow = document.querySelector(`[data-job-id="${jobData.job_id}"]`);
    if (jobRow) {
        // Update the row with new data
        loadStatusData(); // Refresh for now, could be optimized
    }
}

function handleProgressUpdate(progressData) {
    updateJobProgress(progressData.job_id, progressData);
    
    // Update metrics if available
    if (progressData.metrics) {
        updateMetrics(progressData.metrics);
    }
}

function handleERPBatchUpdate(batchData) {
    console.log('ERP Batch Update:', batchData);
    showNotification(`ERP Batch ${batchData.batch_id} ${batchData.status}`, 'info');
}

function handleCircuitBreakerStatus(cbStatus) {
    const cbElement = document.getElementById('circuitBreakerStatus');
    if (cbElement) {
        cbElement.className = `circuit-breaker-status status-${cbStatus.state}`;
        cbElement.innerHTML = `
            <span class="cb-indicator"></span>
            ERP Integration: ${cbStatus.state.toUpperCase()}
            ${cbState.failures ? ` (${cbStatus.failures} failures)` : ''}
        `;
    }
}

function handleSystemAlert(alert) {
    showNotification(`System Alert: ${alert.message}`, alert.severity);
    
    // Update system health if needed
    if (alert.affects_health) {
        loadStatusData();
    }
}

function handleValidationResult(validation) {
    if (validation.job_id) {
        // Update specific job validation status
        updateJobValidation(validation.job_id, validation);
    }
}

// Enhanced progress bar with more details
function createEnhancedProgressBar(job) {
    const progress = calculateProgress(job);
    const processingStage = job.current_stage || 'processing';
    
    return `
        <div class="progress-container enhanced">
            <div class="progress-stage">${formatStage(processingStage)}</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
            <div class="progress-details">
                <span class="progress-text">${progress}%</span>
                ${job.current_operation ? `
                    <span class="progress-operation">${job.current_operation}</span>
                ` : ''}
            </div>
        </div>
    `;
}

// Enhanced filter setup
function setupFilters() {
    const statusFilter = document.getElementById('statusFilter');
    const searchFilter = document.getElementById('searchJobs');
    const mappingFilter = document.getElementById('mappingFilter');
    const dateFilter = document.getElementById('dateFilter');
    
    statusFilter.addEventListener('change', loadStatusData);
    searchFilter.addEventListener('input', debounce(loadStatusData, 500));
    mappingFilter.addEventListener('change', loadStatusData);
    dateFilter.addEventListener('change', loadStatusData);
    
    // Load available mappings for filter
    loadMappingOptions();
}

// Load available column mappings for filter
async function loadMappingOptions() {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/mappings', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const mappings = await response.json();
            updateMappingFilter(mappings);
        }
    } catch (error) {
        console.error('Error loading mappings:', error);
    }
}

// New utility functions
function generateRequestId() {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function formatProcessingTime(seconds) {
    if (!seconds) return '0s';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

function formatStatus(status) {
    const statusMap = {
        'processing': 'Processing',
        'completed': 'Completed', 
        'failed': 'Failed',
        'validating': 'Validating',
        'pending': 'Pending',
        'cancelled': 'Cancelled'
    };
    return statusMap[status] || status;
}

function formatStage(stage) {
    const stageMap = {
        'processing': '🔄 Processing',
        'validating': '🔍 Validating',
        'mapping': '🗺️ Mapping',
        'erp_sending': '📤 Sending to ERP',
        'erp_processing': '⚙️ ERP Processing',
        'cleaning': '🧹 Cleaning Data'
    };
    return stageMap[stage] || stage;
}

function updateUserInterface(user) {
    // Update UI elements with user information
    const userElement = document.getElementById('currentUser');
    if (userElement) {
        userElement.textContent = user.username || user.email;
    }
}

// Initialize real-time metrics chart
function initializeRealTimeMetrics() {
    // Would integrate with charts library for real-time metrics
    console.log('Initializing real-time metrics...');
}

// Enhanced error handling for failed requests
function handleFailedRequests(responses) {
    responses.forEach((response, index) => {
        if (response.status === 'rejected') {
            console.error(`Request ${index} failed:`, response.reason);
        }
    });
}

// Cancel job function
async function cancelJob(jobId) {
    if (!confirm('Are you sure you want to cancel this job?')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/import/jobs/${jobId}/cancel`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            showNotification('Job cancellation requested', 'info');
            loadStatusData();
        } else {
            const error = await response.json();
            showNotification(`Failed to cancel job: ${error.message}`, 'error');
        }
    } catch (error) {
        showNotification('Error cancelling job: ' + error.message, 'error');
    }
}

// Keep the existing utility functions (escapeHtml, formatDate, formatRelativeTime, etc.)
// and add the new enhancements...

// Enhanced notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close(1000, 'Page navigation');
    }
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Export functions for global access
window.showJobDetails = showJobDetails;
window.closeJobDetailsModal = closeJobDetailsModal;
window.retryJob = retryJob;
window.cancelJob = cancelJob;
     
