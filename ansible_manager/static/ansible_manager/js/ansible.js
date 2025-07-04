// Ansible Manager JavaScript

// Global variables
let refreshInterval;
let executionStatusInterval;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeAnsible();
});

function initializeAnsible() {
    // Initialize CodeMirror editors
    initializeCodeMirror();
    
    // Initialize form handlers
    initializeFormHandlers();
    
    // Initialize auto-refresh for running executions
    initializeAutoRefresh();
    
    // Initialize filter handlers
    initializeFilters();
    
    // Initialize modal handlers
    initializeModals();
    
    // Initialize tooltips
    initializeTooltips();
}

// CodeMirror initialization
function initializeCodeMirror() {
    // YAML editor for playbooks
    const yamlEditor = document.getElementById('id_content');
    if (yamlEditor) {
        window.yamlCodeMirror = CodeMirror.fromTextArea(yamlEditor, {
            mode: 'yaml',
            theme: 'default',
            lineNumbers: true,
            indentUnit: 2,
            tabSize: 2,
            lineWrapping: true,
            foldGutter: true,
            gutters: ['CodeMirror-linenumbers', 'CodeMirror-foldgutter'],
            extraKeys: {
                'Ctrl-Space': 'autocomplete',
                'Tab': function(cm) {
                    if (cm.somethingSelected()) {
                        cm.indentSelection('add');
                    } else {
                        cm.replaceSelection('  ');
                    }
                }
            }
        });
        
        // Add validation
        window.yamlCodeMirror.on('change', function(cm) {
            validateYAML(cm.getValue());
        });
    }
    
    // JSON editor for variables
    const jsonEditor = document.getElementById('id_variables');
    if (jsonEditor) {
        window.jsonCodeMirror = CodeMirror.fromTextArea(jsonEditor, {
            mode: 'application/json',
            theme: 'default',
            lineNumbers: true,
            indentUnit: 2,
            tabSize: 2,
            lineWrapping: true,
            foldGutter: true,
            gutters: ['CodeMirror-linenumbers', 'CodeMirror-foldgutter'],
            extraKeys: {
                'Ctrl-Space': 'autocomplete'
            }
        });
        
        // Add validation
        window.jsonCodeMirror.on('change', function(cm) {
            validateJSON(cm.getValue());
        });
    }
    
    // Inventory editor
    const inventoryEditor = document.getElementById('id_content');
    if (inventoryEditor && window.location.pathname.includes('inventory')) {
        window.inventoryCodeMirror = CodeMirror.fromTextArea(inventoryEditor, {
            mode: 'yaml',
            theme: 'default',
            lineNumbers: true,
            indentUnit: 2,
            tabSize: 2,
            lineWrapping: true
        });
    }
}

// YAML validation
function validateYAML(content) {
    const errorDiv = document.getElementById('yaml-error');
    if (!errorDiv) return;
    
    if (!content.trim()) {
        errorDiv.style.display = 'none';
        return;
    }
    
    try {
        // Basic YAML validation (you might want to use a proper YAML parser)
        if (content.includes('\t')) {
            throw new Error('YAML should not contain tabs. Use spaces for indentation.');
        }
        
        errorDiv.style.display = 'none';
        errorDiv.className = 'alert alert-success';
        errorDiv.textContent = 'YAML syntax is valid';
    } catch (error) {
        errorDiv.style.display = 'block';
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = 'YAML Error: ' + error.message;
    }
}

// JSON validation
function validateJSON(content) {
    const errorDiv = document.getElementById('json-error');
    if (!errorDiv) return;
    
    if (!content.trim()) {
        errorDiv.style.display = 'none';
        return;
    }
    
    try {
        JSON.parse(content);
        errorDiv.style.display = 'none';
    } catch (error) {
        errorDiv.style.display = 'block';
        errorDiv.className = 'alert alert-danger';
        errorDiv.textContent = 'JSON Error: ' + error.message;
    }
}

// Form handlers
function initializeFormHandlers() {
    // Playbook template selection
    const templateSelect = document.getElementById('playbook-template');
    if (templateSelect) {
        templateSelect.addEventListener('change', function() {
            loadPlaybookTemplate(this.value);
        });
    }
    
    // Form submission with CodeMirror sync
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            // Sync CodeMirror content back to textareas
            if (window.yamlCodeMirror) {
                window.yamlCodeMirror.save();
            }
            if (window.jsonCodeMirror) {
                window.jsonCodeMirror.save();
            }
            if (window.inventoryCodeMirror) {
                window.inventoryCodeMirror.save();
            }
        });
    });
}

// Load playbook template
function loadPlaybookTemplate(templateName) {
    if (!templateName || !window.yamlCodeMirror) return;
    
    const templates = {
        'basic': `---\n- name: Basic Playbook\n  hosts: all\n  become: yes\n  tasks:\n    - name: Ensure a package is installed\n      package:\n        name: htop\n        state: present`,
        'web_server': `---\n- name: Setup Web Server\n  hosts: web_servers\n  become: yes\n  tasks:\n    - name: Install Apache\n      package:\n        name: apache2\n        state: present\n    \n    - name: Start Apache service\n      service:\n        name: apache2\n        state: started\n        enabled: yes`,
        'database': `---\n- name: Setup Database Server\n  hosts: db_servers\n  become: yes\n  tasks:\n    - name: Install MySQL\n      package:\n        name: mysql-server\n        state: present\n    \n    - name: Start MySQL service\n      service:\n        name: mysql\n        state: started\n        enabled: yes`
    };
    
    if (templates[templateName]) {
        window.yamlCodeMirror.setValue(templates[templateName]);
    }
}

// Auto-refresh functionality
function initializeAutoRefresh() {
    const refreshCheckbox = document.getElementById('auto-refresh');
    if (refreshCheckbox) {
        refreshCheckbox.addEventListener('change', function() {
            if (this.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
        
        // Start auto-refresh if there are running executions
        if (document.querySelectorAll('.status-running').length > 0) {
            refreshCheckbox.checked = true;
            startAutoRefresh();
        }
    }
}

function startAutoRefresh() {
    stopAutoRefresh(); // Clear any existing interval
    
    refreshInterval = setInterval(function() {
        refreshRunningExecutions();
    }, 5000); // Refresh every 5 seconds
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

function refreshRunningExecutions() {
    const runningRows = document.querySelectorAll('.status-running');
    if (runningRows.length === 0) {
        stopAutoRefresh();
        document.getElementById('auto-refresh').checked = false;
        return;
    }
    
    // Fetch updated execution data
    fetch(window.location.pathname + '?ajax=1')
        .then(response => response.json())
        .then(data => {
            updateExecutionTable(data.executions);
        })
        .catch(error => {
            console.error('Error refreshing executions:', error);
        });
}

function updateExecutionTable(executions) {
    executions.forEach(execution => {
        const row = document.querySelector(`tr[data-execution-id="${execution.id}"]`);
        if (row) {
            // Update status
            const statusCell = row.querySelector('.execution-status');
            if (statusCell) {
                statusCell.className = `execution-status status-${execution.status}`;
                statusCell.textContent = execution.status.charAt(0).toUpperCase() + execution.status.slice(1);
            }
            
            // Update progress
            const progressCell = row.querySelector('.execution-progress');
            if (progressCell && execution.progress !== undefined) {
                progressCell.innerHTML = `
                    <div class="progress">
                        <div class="progress-bar" style="width: ${execution.progress}%"></div>
                    </div>
                    <small>${execution.progress}%</small>
                `;
            }
            
            // Update duration
            const durationCell = row.querySelector('.execution-duration');
            if (durationCell && execution.duration) {
                durationCell.textContent = execution.duration;
            }
        }
    });
}

// Filter handlers
function initializeFilters() {
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        const inputs = filterForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                filterForm.submit();
            });
        });
    }
}

// Modal handlers
function initializeModals() {
    // Execution modal
    const executionModal = document.getElementById('executionModal');
    if (executionModal) {
        executionModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const playbookId = button.getAttribute('data-playbook-id');
            loadExecutionForm(playbookId);
        });
    }
    
    // Delete confirmation modals
    const deleteButtons = document.querySelectorAll('[data-bs-target="#deleteModal"]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const itemType = this.getAttribute('data-item-type');
            const itemName = this.getAttribute('data-item-name');
            const deleteUrl = this.getAttribute('data-delete-url');
            
            document.getElementById('delete-item-type').textContent = itemType;
            document.getElementById('delete-item-name').textContent = itemName;
            document.getElementById('confirm-delete').setAttribute('href', deleteUrl);
        });
    });
}

// Load execution form
function loadExecutionForm(playbookId) {
    fetch(`/ansible/api/playbooks/${playbookId}/execution-form/`)
        .then(response => response.text())
        .then(html => {
            document.getElementById('execution-form-container').innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading execution form:', error);
        });
}

// Tooltip initialization
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// API functions
function executePlaybook(playbookId, inventoryId, extraVars = {}) {
    const data = {
        playbook_id: playbookId,
        inventory_id: inventoryId,
        extra_vars: extraVars
    };
    
    return fetch('/ansible/api/executions/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json());
}

function cancelExecution(executionId) {
    return fetch(`/ansible/api/executions/${executionId}/cancel/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json());
}

function rerunExecution(executionId) {
    return fetch(`/ansible/api/executions/${executionId}/rerun/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json());
}

function syncInventory(inventoryId) {
    return fetch(`/ansible/api/inventories/${inventoryId}/sync/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken()
        }
    })
    .then(response => response.json());
}

// Utility functions
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

// Export functions for global access
window.ansibleManager = {
    executePlaybook,
    cancelExecution,
    rerunExecution,
    syncInventory,
    showNotification,
    formatDuration
};