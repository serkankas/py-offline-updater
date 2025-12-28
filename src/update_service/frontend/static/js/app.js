// Main application JavaScript
let currentJobId = null;
let eventSource = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    loadBackups();
    setupUploadHandlers();
});

// Load system information
async function loadSystemInfo() {
    try {
        const response = await fetch('/api/system-info');
        const data = await response.json();
        
        document.getElementById('hostname').textContent = data.hostname;
        
        const diskPercent = data.disk_usage.percent.toFixed(1);
        const diskFree = formatBytes(data.disk_usage.free);
        document.getElementById('disk-usage').textContent = `${diskPercent}% used (${diskFree} free)`;
        
        const memPercent = data.memory.percent.toFixed(1);
        const memAvailable = formatBytes(data.memory.available);
        document.getElementById('memory').textContent = `${memPercent}% used (${memAvailable} available)`;
    } catch (error) {
        console.error('Failed to load system info:', error);
    }
}

// Load backups list
async function loadBackups() {
    try {
        const response = await fetch('/api/backups');
        const backups = await response.json();
        
        const backupsList = document.getElementById('backups-list');
        
        if (backups.length === 0) {
            backupsList.innerHTML = '<p class="loading">No backups available</p>';
            return;
        }
        
        backupsList.innerHTML = backups.map(backup => `
            <div class="backup-item">
                <div class="backup-info">
                    <h4>${backup.name}</h4>
                    <p>Created: ${new Date(backup.created_at).toLocaleString()}</p>
                    <p>Sources: ${backup.sources.length} item(s)</p>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load backups:', error);
        document.getElementById('backups-list').innerHTML = '<p class="loading">Failed to load backups</p>';
    }
}

// Setup upload handlers
function setupUploadHandlers() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    const uploadBtn = document.getElementById('upload-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    
    // Click to upload
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // File selected
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            showFileInfo(file);
        }
    });
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        if (file) {
            fileInput.files = e.dataTransfer.files;
            showFileInfo(file);
        }
    });
    
    // Upload button
    uploadBtn.addEventListener('click', () => {
        uploadFile(fileInput.files[0]);
    });
    
    // Cancel button
    cancelBtn.addEventListener('click', () => {
        hideFileInfo();
        fileInput.value = '';
    });
}

// Show file info
function showFileInfo(file) {
    document.getElementById('filename').textContent = file.name;
    document.getElementById('filesize').textContent = formatBytes(file.size);
    document.getElementById('upload-area').style.display = 'none';
    document.getElementById('file-info').style.display = 'block';
}

// Hide file info
function hideFileInfo() {
    document.getElementById('upload-area').style.display = 'block';
    document.getElementById('file-info').style.display = 'none';
}

// Upload file
async function uploadFile(file) {
    const uploadBtn = document.getElementById('upload-btn');
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/upload-update', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Upload failed');
        }
        
        const data = await response.json();
        console.log('Upload successful:', data);
        
        // Start update
        await startUpdate(data.filename);
        
        hideFileInfo();
    } catch (error) {
        console.error('Upload error:', error);
        alert('Upload failed: ' + error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
    }
}

// Start update
async function startUpdate(filename) {
    try {
        const response = await fetch('/api/apply-update?filename=' + encodeURIComponent(filename), {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to start update');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Show update section
        document.getElementById('update-section').style.display = 'block';
        
        // Start streaming updates
        streamUpdateProgress(currentJobId);
    } catch (error) {
        console.error('Start update error:', error);
        alert('Failed to start update: ' + error.message);
    }
}

// Stream update progress via SSE
function streamUpdateProgress(jobId) {
    if (eventSource) {
        eventSource.close();
    }
    
    eventSource = new EventSource(`/api/update-stream/${jobId}`);
    
    eventSource.addEventListener('status', (e) => {
        const job = JSON.parse(e.data);
        updateStatus(job);
    });
    
    eventSource.addEventListener('log', (e) => {
        addLog(e.data);
    });
    
    eventSource.addEventListener('complete', (e) => {
        const job = JSON.parse(e.data);
        updateStatus(job);
        eventSource.close();
        
        // Reload backups
        loadBackups();
    });
    
    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
    };
}

// Update status display
function updateStatus(job) {
    const statusBadge = document.getElementById('status-badge');
    statusBadge.textContent = job.status;
    statusBadge.className = 'badge ' + job.status;
    
    if (job.description) {
        document.getElementById('update-description').textContent = job.description;
    }
    
    if (job.progress) {
        const progress = job.progress;
        const percent = progress.total_actions > 0 
            ? (progress.completed_actions / progress.total_actions * 100).toFixed(0)
            : 0;
        
        document.getElementById('progress-fill').style.width = percent + '%';
        document.getElementById('progress-label').textContent = 
            `${progress.completed_actions} / ${progress.total_actions} actions`;
        document.getElementById('progress-percent').textContent = percent + '%';
        
        if (progress.current_action_name) {
            document.getElementById('current-action').textContent = 
                `Current: ${progress.current_action_name}`;
        }
    }
    
    // Show rollback button if failed
    if (job.status === 'failed') {
        const rollbackBtn = document.getElementById('rollback-btn');
        rollbackBtn.style.display = 'block';
        rollbackBtn.onclick = () => rollbackUpdate(job.job_id);
    }
}

// Add log entry
function addLog(logText) {
    const logsDiv = document.getElementById('logs');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    // Colorize based on log level
    if (logText.includes('ERROR')) {
        logEntry.classList.add('error');
    } else if (logText.includes('WARNING')) {
        logEntry.classList.add('warning');
    } else if (logText.includes('completed successfully')) {
        logEntry.classList.add('success');
    }
    
    logEntry.textContent = logText;
    logsDiv.appendChild(logEntry);
    
    // Auto-scroll to bottom
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

// Rollback update
async function rollbackUpdate(jobId) {
    if (!confirm('Are you sure you want to rollback this update?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/rollback/${jobId}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Rollback failed');
        }
        
        const data = await response.json();
        alert(data.message);
        
        // Reload page
        location.reload();
    } catch (error) {
        console.error('Rollback error:', error);
        alert('Rollback failed: ' + error.message);
    }
}

// Format bytes to human readable
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Refresh system info periodically
setInterval(loadSystemInfo, 30000); // Every 30 seconds

