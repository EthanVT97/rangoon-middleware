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
        
