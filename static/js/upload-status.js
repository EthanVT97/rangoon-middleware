// Upload Status & Monitoring JavaScript

let websocket = null;
let currentUser = null;
let refreshInterval = null;

// Initialize status page
document.addEventListener('DOMContentLoaded', function() {
    initializeStatusPage();
});

async function initializeStatusPage() {
    try {
        // Check authentication
        await checkAuthentication();
        
        // Load initial data
        await loadStatusData();
        
        // Initialize WebSocket
        initializeWebSocket();
        
        // Set up auto-refresh
        refreshInterval = setInterval(loadStatusData, 10000); // Refresh every 10 seconds
        
        // Set up filters
        setupFilters();
        
    } catch (error) {
        console.error('Status page initialization error:', error);
        showError('Failed to initialize status page');
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
        } else {
            redirectToLogin();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        redirectToLogin();
    }
}

// Load status data
async function loadStatusData() {
    try {
        const token = localStorage.getItem('access_token');
        
        // Load metrics
        const metricsResponse = await fetch('/api/monitoring/metrics', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (metricsResponse.ok) {
            const metricsData = await metricsResponse.json();
            updateMetrics(metricsData.metrics);
        }
        
        // Load jobs
        const jobsResponse = await fetch('/api/import/jobs?limit=100', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (jobsResponse.ok) {
            const jobsData = await jobsResponse.json();
            updateJobsTable(jobsData.jobs);
            updateActiveJobs(jobsData.jobs);
        }
        
        // Load errors
        const errorsResponse = await fetch('/api/monitoring/errors', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (errorsResponse.ok) {
            const errorsData = await errorsResponse.json();
            updateRecentErrors(errorsData.errors);
        }
        
    } catch (error) {
        console.error('Error loading status data:', error);
    }
}

// Update metrics display
function updateMetrics(metrics) {
    if (!metrics) return;
    
    document.getElementById('totalJobs').textContent = metrics.total_jobs || 0;
    document.getElementById('successRate').textContent = `${metrics.success_rate || 0}%`;
    document.getElementById('activeJobs').textContent = metrics.processing_jobs || 0;
    document.getElementById('avgProcessingTime').textContent = '0s'; // Would calculate from actual data
}

// Update jobs table
function updateJobsTable(jobs) {
    const tableBody = document.getElementById('jobsTableBody');
    
    if (!jobs || jobs.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">No import jobs found</td>
            </tr>
        `;
        return;
    }
    
    // Apply filters
    const statusFilter = document.getElementById('statusFilter').value;
    const searchFilter = document.getElementById('searchJobs').value.toLowerCase();
    
    const filteredJobs = jobs.filter(job => {
        const matchesStatus = statusFilter === 'all' || job.status === statusFilter;
        const matchesSearch = !searchFilter || 
            job.filename.toLowerCase().includes(searchFilter) ||
            job.job_id.toLowerCase().includes(searchFilter) ||
            (job.column_mappings && job.column_mappings.mapping_name.toLowerCase().includes(searchFilter));
        
        return matchesStatus && matchesSearch;
    });
    
    tableBody.innerHTML = filteredJobs.map(job => `
        <tr>
            <td>
                <span class="job-id">${job.job_id}</span>
                <br>
                <small class="text-muted">${formatDate(job.created_at)}</small>
            </td>
            <td>${escapeHtml(job.filename)}</td>
            <td>${job.column_mappings ? escapeHtml(job.column_mappings.mapping_name) : 'N/A'}</td>
            <td>
                <span class="job-status status-${job.status}">${job.status}</span>
            </td>
            <td>
                ${job.status === 'processing' ? createProgressBar(job) : 
                  job.status === 'completed' ? '✅ Complete' : 
                  job.status === 'failed' ? '❌ Failed' : '⏳ Pending'}
            </td>
            <td>
                ${job.processed_records || 0}/${job.total_records || 0}
                ${job.failed_records > 0 ? `<br><small class="text-danger">${job.failed_records} failed</small>` : ''}
            </td>
            <td>${formatRelativeTime(job.created_at)}</td>
            <td>
                <button onclick="showJobDetails('${job.job_id}')" class="btn btn-outline btn-sm">
                    Details
                </button>
                ${job.status === 'failed' ? `
                    <button onclick="retryJob('${job.job_id}')" class="btn btn-primary btn-sm">
                        Retry
                    </button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

// Update active jobs list
function updateActiveJobs(jobs) {
    const activeJobsList = document.getElementById('activeJobsList');
    const activeJobs = jobs.filter(job => job.status === 'processing');
    
    if (activeJobs.length === 0) {
        activeJobsList.innerHTML = '<div class="empty-state">No active jobs at the moment</div>';
        return;
    }
    
    activeJobsList.innerHTML = activeJobs.map(job => `
        <div class="job-item">
            <div class="job-header">
                <span class="job-filename">${escapeHtml(job.filename)}</span>
                <span class="job-status status-processing">Processing</span>
            </div>
            <div class="job-details">
                <span>Job ID: ${job.job_id}</span>
                <span>Started: ${formatRelativeTime(job.created_at)}</span>
            </div>
            ${createProgressBar(job)}
            <div class="job-actions">
                <button onclick="showJobDetails('${job.job_id}')" class="btn btn-outline btn-sm">
                    View Details
                </button>
            </div>
        </div>
    `).join('');
}

// Update recent errors
function updateRecentErrors(errors) {
    const errorsContainer = document.getElementById('recentErrors');
    
    if (!errors || errors.length === 0) {
        errorsContainer.innerHTML = '<div class="empty-state">No recent errors</div>';
        return;
    }
    
    errorsContainer.innerHTML = errors.slice(0, 10).map(error => `
        <div class="error-item">
            <div class="error-header">
                <span class="error-filename">${escapeHtml(error.filename)}</span>
                <span class="error-time">${formatRelativeTime(error.timestamp)}</span>
            </div>
            <div class="error-details">
                <strong>Job:</strong> ${error.job_id}<br>
                <strong>Error:</strong> ${typeof error.error === 'object' ? JSON.stringify(error.error) : escapeHtml(error.error)}
            </div>
        </div>
    `).join('');
}

// Create progress bar
function createProgressBar(job) {
    const progress = calculateProgress(job);
    return `
        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" style="width: ${progress}%"></div>
            </div>
            <div class="progress-text">${progress}%</div>
        </div>
    `;
}

// Show job details
async function showJobDetails(jobId) {
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/monitoring/jobs/${jobId}/status`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            displayJobDetails(data.job);
        } else {
            alert('Error loading job details');
        }
    } catch (error) {
        alert('Error loading job details: ' + error.message);
    }
}

// Display job details in modal
function displayJobDetails(job) {
    const modalContent = document.getElementById('jobDetailsContent');
    
    modalContent.innerHTML = `
        <div class="job-detail-section">
            <h4>Basic Information</h4>
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Job ID:</label>
                    <span>${job.job_id}</span>
                </div>
                <div class="detail-item">
                    <label>Filename:</label>
                    <span>${escapeHtml(job.filename)}</span>
                </div>
                <div class="detail-item">
                    <label>Mapping:</label>
                    <span>${job.column_mappings ? escapeHtml(job.column_mappings.mapping_name) : 'N/A'}</span>
                </div>
                <div class="detail-item">
                    <label>Status:</label>
                    <span class="job-status status-${job.status}">${job.status}</span>
                </div>
                <div class="detail-item">
                    <label>Created:</label>
                    <span>${formatDate(job.created_at)}</span>
                </div>
                ${job.completed_at ? `
                <div class="detail-item">
                    <label>Completed:</label>
                    <span>${formatDate(job.completed_at)}</span>
                </div>
                ` : ''}
            </div>
        </div>
        
        <div class="job-detail-section">
            <h4>Progress & Statistics</h4>
            <div class="detail-grid">
                <div class="detail-item">
                    <label>Total Records:</label>
                    <span>${job.total_records || 0}</span>
                </div>
                <div class="detail-item">
                    <label>Processed:</label>
                    <span>${job.processed_records || 0}</span>
                </div>
                <div class="detail-item">
                    <label>Failed:</label>
                    <span class="${job.failed_records > 0 ? 'text-danger' : ''}">${job.failed_records || 0}</span>
                </div>
                <div class="detail-item">
                    <label>Success Rate:</label>
                    <span>${calculateSuccessRate(job)}%</span>
                </div>
            </div>
            ${job.status === 'processing' && job.is_active ? `
            <div class="progress-container" style="margin-top: 15px;">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${calculateProgress(job)}%"></div>
                </div>
                <div class="progress-text">${calculateProgress(job)}% - Active Monitoring</div>
            </div>
            ` : ''}
        </div>
        
        ${job.error_log && job.error_log.length > 0 ? `
        <div class="job-detail-section">
            <h4>Errors (${job.error_log.length})</h4>
            <div class="errors-list">
                ${job.error_log.map((error, index) => `
                    <div class="error-item">
                        <div class="error-header">
                            <strong>Row ${error.row || 'N/A'}:</strong>
                        </div>
                        <div class="error-message">
                            ${typeof error.error === 'object' ? JSON.stringify(error.error) : escapeHtml(error.error)}
                        </div>
                        ${error.data ? `
                        <div class="error-data">
                            <strong>Data:</strong> ${JSON.stringify(error.data)}
                        </div>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
        </div>
        ` : ''}
        
        ${job.erp_response && Object.keys(job.erp_response).length > 0 ? `
        <div class="job-detail-section">
            <h4>ERP Response</h4>
            <pre class="erp-response">${JSON.stringify(job.erp_response, null, 2)}</pre>
        </div>
        ` : ''}
        
        <div class="job-detail-actions">
            ${job.status === 'failed' ? `
                <button onclick="retryJob('${job.job_id}')" class="btn btn-primary">Retry Job</button>
            ` : ''}
            <button onclick="closeJobDetailsModal()" class="btn btn-outline">Close</button>
        </div>
    `;
    
    document.getElementById('jobDetailsModal').style.display = 'block';
}

// Close job details modal
function closeJobDetailsModal() {
    document.getElementById('jobDetailsModal').style.display = 'none';
}

// Retry job
async function retryJob(jobId) {
    if (!confirm('Are you sure you want to retry this job?')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch(`/api/import/jobs/${jobId}/retry`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            alert('Job retry initiated');
            closeJobDetailsModal();
            loadStatusData(); // Refresh data
        } else {
            alert('Error retrying job');
        }
    } catch (error) {
        alert('Error retrying job: ' + error.message);
    }
}

// WebSocket Functions
function initializeWebSocket() {
    if (!currentUser) return;
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/monitoring/ws/${currentUser.id}`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function() {
        updateWebSocketStatus(true);
        console.log('WebSocket connected for monitoring');
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
        statusElement.innerHTML = connected ? '🟢 Live Updates' : '🔴 Disconnected';
    }
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'job_update':
            // Refresh jobs data when we receive updates
            loadStatusData();
            break;
            
        case 'progress_update':
            // Update specific job progress
            updateJobProgress(message.job_id, message.progress);
            break;
            
        case 'system_message':
            console.log('System message:', message.message);
            showNotification(message.message);
            break;
            
        case 'connection_established':
            console.log('WebSocket connection established');
            break;
    }
}

function updateJobProgress(jobId, progress) {
    // Update progress for specific job in the UI
    const progressElements = document.querySelectorAll(`[data-job-id="${jobId}"] .progress-fill`);
    progressElements.forEach(element => {
        element.style.width = progress.percentage + '%';
    });
    
    // Also update the progress text
    const progressTextElements = document.querySelectorAll(`[data-job-id="${jobId}"] .progress-text`);
    progressTextElements.forEach(element => {
        element.textContent = progress.percentage + '%';
    });
}

// Filter Setup
function setupFilters() {
    const statusFilter = document.getElementById('statusFilter');
    const searchFilter = document.getElementById('searchJobs');
    
    statusFilter.addEventListener('change', loadStatusData);
    searchFilter.addEventListener('input', debounce(loadStatusData, 300));
}

// Utility Functions
function redirectToLogin() {
    localStorage.removeItem('access_token');
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

function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hr ago`;
    return `${diffDays} day ago`;
}

function calculateProgress(job) {
    if (!job.total_records) return 0;
    return Math.round((job.processed_records / job.total_records) * 100);
}

function calculateSuccessRate(job) {
    if (!job.total_records) return 0;
    return Math.round(((job.processed_records - job.failed_records) / job.total_records) * 100);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function showNotification(message) {
    // Simple notification - could be enhanced with a proper notification system
    console.log('Notification:', message);
}

function showError(message) {
    alert('Error: ' + message);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close();
    }
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Close modals when clicking outside
window.onclick = function(event) {
    const jobModal = document.getElementById('jobDetailsModal');
    if (event.target === jobModal) {
        closeJobDetailsModal();
    }
        }
