// Mapping Configuration JavaScript

let sourceColumns = [];
let targetColumns = [];

// Initialize form
document.addEventListener('DOMContentLoaded', function() {
    initializeForm();
});

function initializeForm() {
    // Add initial source and target columns
    addSourceColumn();
    addTargetColumn();
    
    // Set up form submission
    const mappingForm = document.getElementById('mappingForm');
    if (mappingForm) {
        mappingForm.addEventListener('submit', handleFormSubmit);
    }
}

// Source Column Management
function addSourceColumn() {
    const sourceColumnsDiv = document.getElementById('sourceColumns');
    if (!sourceColumnsDiv) return;
    
    const columnId = 'source_' + Date.now();
    
    const newRow = document.createElement('div');
    newRow.className = 'column-row';
    newRow.id = columnId;
    newRow.innerHTML = `
        <input type="text" placeholder="Column Name (e.g., Customer_ID)" 
               class="column-name" onchange="updateSourceMappings()" required>
        <select class="column-type">
            <option value="string">Text</option>
            <option value="number">Number</option>
            <option value="date">Date</option>
            <option value="boolean">Yes/No</option>
        </select>
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" class="column-required"> Required
        </label>
        <button type="button" onclick="removeColumn('${columnId}')" 
                class="btn btn-danger btn-sm">Remove</button>
    `;
    
    sourceColumnsDiv.appendChild(newRow);
    updateSourceMappings();
}

// Target Column Management
function addTargetColumn() {
    const targetColumnsDiv = document.getElementById('targetColumns');
    if (!targetColumnsDiv) return;
    
    const columnId = 'target_' + Date.now();
    
    const newRow = document.createElement('div');
    newRow.className = 'column-row';
    newRow.id = columnId;
    newRow.innerHTML = `
        <input type="text" placeholder="ERP Field Name (e.g., customer_code)" 
               class="target-field" required>
        <select class="source-mapping">
            <option value="">-- Map to Source --</option>
        </select>
        <select class="transformation">
            <option value="">No Transformation</option>
            <option value="uppercase">Uppercase</option>
            <option value="lowercase">Lowercase</option>
            <option value="title_case">Title Case</option>
            <option value="trim">Trim Spaces</option>
            <option value="phone_format">Phone Format</option>
            <option value="email_lower">Email Lowercase</option>
            <option value="remove_special_chars">Remove Special Chars</option>
        </select>
        <input type="text" placeholder="Default Value" class="default-value">
        <label style="display: flex; align-items: center; gap: 5px;">
            <input type="checkbox" class="field-required"> Required
        </label>
        <button type="button" onclick="removeColumn('${columnId}')" 
                class="btn btn-danger btn-sm">Remove</button>
    `;
    
    targetColumnsDiv.appendChild(newRow);
    updateSourceMappings();
}

// Remove Column
function removeColumn(columnId) {
    const element = document.getElementById(columnId);
    if (element) {
        element.remove();
        updateSourceMappings();
    }
}

// Update Source Mapping Options
function updateSourceMappings() {
    const sourceNames = Array.from(document.querySelectorAll('#sourceColumns .column-name'))
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
    const mappingName = document.getElementById('mappingName')?.value.trim();
    const erpEndpoint = document.getElementById('erpEndpoint')?.value;
    const sourceColumns = Array.from(document.querySelectorAll('#sourceColumns .column-row'));
    const targetColumns = Array.from(document.querySelectorAll('#targetColumns .column-row'));
    
    const errors = [];
    const warnings = [];
    
    // Basic validation
    if (!mappingName) {
        errors.push('Mapping name is required');
    }
    
    if (!erpEndpoint) {
        errors.push('ERP endpoint is required');
    }
    
    if (sourceColumns.length === 0) {
        errors.push('At least one source column is required');
    }
    
    if (targetColumns.length === 0) {
        errors.push('At least one target field is required');
    }
    
    // Validate source columns
    sourceColumns.forEach((row, index) => {
        const nameInput = row.querySelector('.column-name');
        const name = nameInput?.value.trim();
        
        if (!name) {
            errors.push(`Source column ${index + 1} must have a name`);
        }
        
        // Check for duplicate names
        const sameNameColumns = sourceColumns.filter((r, i) => 
            i !== index && r.querySelector('.column-name')?.value.trim() === name
        );
        if (sameNameColumns.length > 0) {
            errors.push(`Duplicate source column name: "${name}"`);
        }
    });
    
    // Validate target columns
    targetColumns.forEach((row, index) => {
        const fieldInput = row.querySelector('.target-field');
        const fieldName = fieldInput?.value.trim();
        const mappingSelect = row.querySelector('.source-mapping');
        const requiredCheckbox = row.querySelector('.field-required');
        
        if (!fieldName) {
            errors.push(`Target field ${index + 1} must have a name`);
        }
        
        // Check for duplicate field names
        const sameFieldColumns = targetColumns.filter((r, i) => 
            i !== index && r.querySelector('.target-field')?.value.trim() === fieldName
        );
        if (sameFieldColumns.length > 0) {
            errors.push(`Duplicate target field name: "${fieldName}"`);
        }
        
        if (requiredCheckbox?.checked && !mappingSelect?.value) {
            errors.push(`Required target field "${fieldName}" must have a source column mapping`);
        }
        
        // Warn if target field has no source mapping
        if (!mappingSelect?.value && !row.querySelector('.default-value')?.value) {
            warnings.push(`Target field "${fieldName}" has no source mapping and no default value`);
        }
    });
    
    // Display validation results
    const resultsDiv = document.getElementById('validationResults');
    const errorsDiv = document.getElementById('validationErrors');
    const warningsDiv = document.getElementById('validationWarnings');
    
    if (resultsDiv) {
        resultsDiv.style.display = 'block';
    }
    
    if (errorsDiv) {
        if (errors.length > 0) {
            errorsDiv.innerHTML = '<strong>Errors:</strong><br>' + 
                errors.map(error => `• ${error}`).join('<br>');
        } else {
            errorsDiv.innerHTML = '';
        }
    }
    
    if (warningsDiv) {
        if (warnings.length > 0) {
            warningsDiv.innerHTML = '<strong>Warnings:</strong><br>' + 
                warnings.map(warning => `• ${warning}`).join('<br>');
        } else {
            warningsDiv.innerHTML = '';
        }
    }
    
    // Scroll to validation results
    if (resultsDiv) {
        resultsDiv.scrollIntoView({ behavior: 'smooth' });
    }
    
    return {
        isValid: errors.length === 0,
        errors: errors,
        warnings: warnings
    };
}

// Handle Form Submission
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const validation = validateMapping();
    
    if (!validation.isValid) {
        alert('Please fix the errors before saving the mapping.');
        return;
    }
    
    // Collect form data
    const mappingData = {
        mapping_name: document.getElementById('mappingName')?.value.trim(),
        description: document.getElementById('mappingDescription')?.value.trim(),
        erp_endpoint: document.getElementById('erpEndpoint')?.value,
        source_columns: collectSourceColumns(),
        target_columns: collectTargetColumns(),
        mapping_rules: {} // Can be extended with additional rules
    };
    
    try {
        const token = localStorage.getItem('access_token');
        const response = await fetch('/api/mappings/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(mappingData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            let message = '✅ Mapping created successfully!';
            if (validation.warnings.length > 0) {
                message += '\n\nWarnings:\n' + validation.warnings.join('\n');
            }
            
            alert(message);
            
            // Redirect to dashboard
            window.location.href = '/';
            
        } else {
            let errorMessage = 'Error creating mapping';
            if (result.detail) {
                if (typeof result.detail === 'string') {
                    errorMessage = result.detail;
                } else if (result.detail.message) {
                    errorMessage = result.detail.message;
                    if (result.detail.errors) {
                        errorMessage += '\n\nErrors:\n' + result.detail.errors.join('\n');
                    }
                }
            }
            alert('❌ ' + errorMessage);
        }
    } catch (error) {
        alert('Error saving mapping: ' + error.message);
    }
}

// Collect Source Columns Data
function collectSourceColumns() {
    return Array.from(document.querySelectorAll('#sourceColumns .column-row')).map(row => {
        return {
            name: row.querySelector('.column-name')?.value.trim() || '',
            type: row.querySelector('.column-type')?.value || 'string',
            required: row.querySelector('.column-required')?.checked || false
        };
    });
}

// Collect Target Columns Data
function collectTargetColumns() {
    const targetColumns = {};
    
    Array.from(document.querySelectorAll('#targetColumns .column-row')).forEach(row => {
        const fieldName = row.querySelector('.target-field')?.value.trim();
        if (fieldName) {
            targetColumns[fieldName] = {
                source_column: row.querySelector('.source-mapping')?.value || null,
                transformation: row.querySelector('.transformation')?.value || null,
                default_value: row.querySelector('.default-value')?.value || null,
                required: row.querySelector('.field-required')?.checked || false
            };
        }
    });
    
    return targetColumns;
}

// Template Loading
async function loadTemplate(templateType) {
    try {
        const response = await fetch(`/api/mappings/templates/${templateType}`);
        
        if (response.ok) {
            const data = await response.json();
            populateFormWithTemplate(data.template);
        } else {
            alert('Error loading template');
        }
    } catch (error) {
        alert('Error loading template: ' + error.message);
    }
}

function populateFormWithTemplate(template) {
    // Clear existing form
    clearForm();
    
    // Set basic information
    const mappingName = document.getElementById('mappingName');
    const mappingDescription = document.getElementById('mappingDescription');
    const erpEndpoint = document.getElementById('erpEndpoint');
    
    if (mappingName) mappingName.value = template.mapping_name;
    if (mappingDescription) mappingDescription.value = template.description || '';
    if (erpEndpoint) erpEndpoint.value = template.erp_endpoint;
    
    // Add source columns
    if (template.source_columns && Array.isArray(template.source_columns)) {
        template.source_columns.forEach((col, index) => {
            if (index > 0) addSourceColumn();
            const rows = document.querySelectorAll('#sourceColumns .column-row');
            const row = rows[rows.length - 1];
            
            if (row) {
                const nameInput = row.querySelector('.column-name');
                const typeSelect = row.querySelector('.column-type');
                const requiredCheck = row.querySelector('.column-required');
                
                if (nameInput) nameInput.value = col.name;
                if (typeSelect) typeSelect.value = col.type;
                if (requiredCheck) requiredCheck.checked = col.required || false;
            }
        });
    }
    
    // Add target columns
    if (template.target_columns && typeof template.target_columns === 'object') {
        Object.entries(template.target_columns).forEach(([fieldName, mapping], index) => {
            if (index > 0) addTargetColumn();
            const rows = document.querySelectorAll('#targetColumns .column-row');
            const row = rows[rows.length - 1];
            
            if (row) {
                const fieldInput = row.querySelector('.target-field');
                const sourceSelect = row.querySelector('.source-mapping');
                const transformSelect = row.querySelector('.transformation');
                const defaultInput = row.querySelector('.default-value');
                const requiredCheck = row.querySelector('.field-required');
                
                if (fieldInput) fieldInput.value = fieldName;
                if (sourceSelect && mapping.source_column) sourceSelect.value = mapping.source_column;
                if (transformSelect && mapping.transformation) transformSelect.value = mapping.transformation;
                if (defaultInput && mapping.default_value) defaultInput.value = mapping.default_value;
                if (requiredCheck) requiredCheck.checked = mapping.required || false;
            }
        });
    }
    
    updateSourceMappings();
    
    alert('Template loaded successfully! Please review and customize the mapping.');
}

// Clear Form
function clearForm() {
    const mappingForm = document.getElementById('mappingForm');
    if (mappingForm) {
        mappingForm.reset();
    }
    
    // Remove all but first source and target columns
    const sourceRows = document.querySelectorAll('#sourceColumns .column-row');
    const targetRows = document.querySelectorAll('#targetColumns .column-row');
    
    sourceRows.forEach((row, index) => {
        if (index > 0) row.remove();
    });
    
    targetRows.forEach((row, index) => {
        if (index > 0) row.remove();
    });
    
    // Clear first rows
    if (sourceRows[0]) {
        const nameInput = sourceRows[0].querySelector('.column-name');
        const typeSelect = sourceRows[0].querySelector('.column-type');
        const requiredCheck = sourceRows[0].querySelector('.column-required');
        
        if (nameInput) nameInput.value = '';
        if (typeSelect) typeSelect.value = 'string';
        if (requiredCheck) requiredCheck.checked = false;
    }
    
    if (targetRows[0]) {
        const fieldInput = targetRows[0].querySelector('.target-field');
        const sourceSelect = targetRows[0].querySelector('.source-mapping');
        const transformSelect = targetRows[0].querySelector('.transformation');
        const defaultInput = targetRows[0].querySelector('.default-value');
        const requiredCheck = targetRows[0].querySelector('.field-required');
        
        if (fieldInput) fieldInput.value = '';
        if (sourceSelect) sourceSelect.value = '';
        if (transformSelect) transformSelect.value = '';
        if (defaultInput) defaultInput.value = '';
        if (requiredCheck) requiredCheck.checked = false;
    }
    
    // Hide validation results
    const validationResults = document.getElementById('validationResults');
    if (validationResults) {
        validationResults.style.display = 'none';
    }
}
