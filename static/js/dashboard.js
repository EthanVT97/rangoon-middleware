// Import Modal Functions
function showImportModal() {
    document.getElementById('importModal').style.display = 'block';
}

function closeImportModal() {
    document.getElementById('importModal').style.display = 'none';
}

// Use Mapping
function useMapping(mappingId) {
    document.getElementById('mappingSelect').value = mappingId;
    showImportModal();
}

// Test ERP Connection
async function testERPConnection() {
    try {
        const response = await fetch('/api/erp/test');
        const result = await response.json();
        
        if (result.success) {
            alert('ERP Connection Test: SUCCESS');
        } else {
            alert(`ERP Connection Test: FAILED\nError: ${result.error}`);
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
    
    if (!mappingId || !fileInput.files[0]) {
        alert('Please select both a mapping and a file');
        return;
    }
    
    const formData = new FormData();
    formData.append('mapping_id', mappingId);
    formData.append('file', fileInput.files[0]);
    
    try {
        const response = await fetch('/api/import', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert(`Import started! Job ID: ${result.job_id}`);
            closeImportModal();
            // Redirect to job status page or refresh
            setTimeout(() => location.reload(), 2000);
        } else {
            alert('Import failed: ' + (result.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error starting import: ' + error.message);
    }
});

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('importModal');
    if (event.target === modal) {
        closeImportModal();
    }
}
