// Mapping Configuration JavaScript

let sourceColumns = [];
let targetColumns = [];

// Add Source Column
function addSourceColumn() {
    const sourceColumnsDiv = document.getElementById('sourceColumns');
    const newRow = document.createElement('div');
    newRow.className = 'column-row';
    newRow.innerHTML = `
        <input type="text" placeholder="Column Name" class="column-name" onchange="updateSourceMappings()">
        <select class="column-type">
            <option value="string">Text</option>
            <option value="number">Number</option>
            <option value="date">Date</option>
            <option value="boolean">Yes/No</option>
        </select>
        <input type="checkbox" class="column-required"> Required
        <button type="button" onclick="removeColumn(this)" class="btn btn-danger btn-sm">Remove</button>
    `;
    sourceColumnsDiv.appendChild(newRow);
}

// Add Target Column
function addTargetColumn() {
    const targetColumnsDiv = document.getElementById('targetColumns');
    const newRow = document.createElement('div');
    newRow.className = 'column-row';
    newRow.innerHTML = `
        <input type="text" placeholder="ERP Field Name" class="target-field">
        <select class="source-mapping">
            <option value="">-- Map to Source --</option>
        </select>
        <select class="transformation">
            <option value="">No Transformation</option>
            <option value="uppercase">Uppercase</option>
            <option value="lowercase">Lowercase</option>
            <option value="trim">Trim Spaces</option>
            <option value="phone_format">Phone Format</option>
            <option value="email_lower">Email Lowercase</option>
        </select>
        <input type="text" placeholder="Default Value" class="default-value">
        <input type="checkbox" class="field-required"> Required
        <button type="button" onclick="removeColumn(this)" class="btn btn-danger btn-sm">Remove</button>
    `;
    targetColumnsDiv.appendChild(newRow);
    updateSourceMappings();
}

// Remove Column
function removeColumn(button) {
    button.parentElement.remove();
    updateSourceMappings();
}

// Update Source Mapping Options
function updateSourceMappings() {
    const sourceNames = Array.from(document.querySelectorAll('.column-name'))
        .map(input => input.value.trim())
        .filter(name => name !== '');
    
    const sourceSelects = document.querySelectorAll('.source-mapping');
    
    sourceSelects.forEach(select => {
        const currentValue = select.value;
        select.innerHTML = '<option value="">-- Map to Source --</option>';
        
        sourceNames.forEach(name => {
            const option = document.createElement('option');
            option.value = name;
            option.textContent = name;
            option.selected = (name === currentValue);
            select.appendChild(option);
        });
    });
}

// Validate Mapping Configuration
function validateMapping() {
    const mappingName = document.getElementById('mappingName').value.trim();
    const sourceColumns = Array.from(document.querySelectorAll('#sourceColumns .column-row'));
    const targetColumns = Array.from(document.querySelectorAll('#targetColumns .column-row'));
    
    const errors = [];
    
    if (!mappingName) {
        errors.push('Mapping name is required');
    }
    
    if (sourceColumns.length === 0) {
        errors.push('At least one source column is required');
    }
    
    if (targetColumns.length === 0) {
        errors.push('At least one target field is required');
    }
    
    // Check source columns
    sourceColumns.forEach((row, index) => {
        const nameInput = row.querySelector('.column-name');
        if (!nameInput.value.trim()) {
            errors.push(`Source column ${index + 1} must have a name`);
        }
    });
    
    // Check target columns
    targetColumns.forEach((row, index) => {
        const fieldInput = row.querySelector('.target-field');
        const mappingSelect = row.querySelector('.source-mapping');
        const requiredCheckbox = row.querySelector('.field-required');
        
        if (!fieldInput.value.trim()) {
            errors.push(`Target field ${index + 1} must have a name`);
        }
        
        if (requiredCheckbox.checked && !mappingSelect.value) {
            errors.push(`Required target field "${fieldInput.value}" must have a source mapping`);
        }
    });
    
    if (errors.length > 0) {
        alert('Validation Errors:\n\n' + errors.join('\n'));
        return false;
    } else {
        alert('Mapping configuration is valid!');
        return true;
    }
}

// Save Mapping Configuration
document.getElementById('mappingForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateMapping()) {
        return;
    }
    
    // Collect source columns
    const sourceColumns = Array.from(document.querySelectorAll('#sourceColumns .column-row')).map(row => {
        return {
            name: row.querySelector('.column-name').value.trim(),
            type: row.querySelector('.column-type').value,
            required: row.querySelector('.column-required').checked
        };
    });
    
    // Collect target columns
    const targetColumns = {};
    Array.from(document.querySelectorAll('#targetColumns .column-row')).forEach(row => {
        const fieldName = row.querySelector('.target-field').value.trim();
        targetColumns[fieldName] = {
            source_column: row.querySelector('.source-mapping').value,
            transformation: row.querySelector('.transformation').value || null,
            default_value: row.querySelector('.default-value').value || null,
            required: row.querySelector('.field-required').checked
        };
    });
    
    // ERP configuration
    const erpEndpoint = document.getElementById('erpEndpoint').value;
    
    const mappingData = {
        mapping_name: document.getElementById('mappingName').value.trim(),
        source_columns: sourceColumns,
        target_columns: targetColumns,
        mapping_rules: {
            erp_endpoint: erpEndpoint
        }
    };
    
    try {
        const response = await fetch('/api/mappings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(mappingData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            alert('Mapping created successfully!');
            window.location.href = '/';
        } else {
            alert('Error creating mapping: ' + (result.detail || 'Unknown error'));
        }
    } catch (error) {
        alert('Error saving mapping: ' + error.message);
    }
});

// Initialize with one row each
document.addEventListener('DOMContentLoaded', function() {
    addSourceColumn();
    addTargetColumn();
});
