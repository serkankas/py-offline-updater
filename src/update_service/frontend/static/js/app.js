// Main application JavaScript
let currentJobId = null;
let eventSource = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadSystemInfo();
    setupUploadHandlers();
    checkRecoveryStatus();
});

// Load system information
async function loadSystemInfo() {
    try {
        const response = await fetch('/api/system-info');
        const data = await response.json();
        
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

// Upload file using chunked upload
async function uploadFile(file) {
    const uploadBtn = document.getElementById('upload-btn');
    const cancelBtn = document.getElementById('cancel-btn');
    const progressContainer = document.getElementById('upload-progress');
    const progressFill = document.getElementById('upload-progress-fill');
    const progressLabel = document.getElementById('upload-progress-label');
    const progressPercent = document.getElementById('upload-progress-percent');

    uploadBtn.disabled = true;
    cancelBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    progressContainer.style.display = 'block';

    try {
        // Step 1: Init chunked upload
        const initParams = new URLSearchParams({
            filename: file.name,
            total_size: file.size
        });
        const initResp = await fetch('/api/upload/init?' + initParams, { method: 'POST' });
        if (!initResp.ok) {
            const err = await initResp.json();
            throw new Error(err.detail || 'Init failed');
        }
        const initData = await initResp.json();
        const { upload_id, chunk_size, total_chunks } = initData;

        // Step 2: Send chunks
        for (let i = 0; i < total_chunks; i++) {
            const start = i * chunk_size;
            const end = Math.min(start + chunk_size, file.size);
            const chunk = file.slice(start, end);

            const formData = new FormData();
            formData.append('file', chunk);

            const chunkParams = new URLSearchParams({
                upload_id: upload_id,
                chunk_index: i
            });
            const chunkResp = await fetch('/api/upload/chunk?' + chunkParams, {
                method: 'POST',
                body: formData
            });

            if (!chunkResp.ok) {
                const err = await chunkResp.json();
                throw new Error(err.detail || `Chunk ${i} failed`);
            }

            const chunkData = await chunkResp.json();

            // Update progress
            const sentMB = (chunkData.received_bytes / 1024 / 1024).toFixed(1);
            const totalMB = (chunkData.total_bytes / 1024 / 1024).toFixed(1);
            progressFill.style.width = chunkData.percent + '%';
            progressLabel.textContent = `${sentMB} / ${totalMB} MB`;
            progressPercent.textContent = chunkData.percent + '%';
        }

        // Step 3: Finalize
        const finalParams = new URLSearchParams({ upload_id: upload_id });
        const finalResp = await fetch('/api/upload/finalize?' + finalParams, { method: 'POST' });
        if (!finalResp.ok) {
            const err = await finalResp.json();
            throw new Error(err.detail || 'Finalize failed');
        }

        const finalData = await finalResp.json();
        console.log('Upload successful:', finalData);

        // Start update
        await startUpdate(finalData.filename);

        hideFileInfo();
    } catch (error) {
        console.error('Upload error:', error);
        alert('Upload failed: ' + error.message);
    } finally {
        uploadBtn.disabled = false;
        cancelBtn.disabled = false;
        uploadBtn.textContent = 'Upload';
        progressContainer.style.display = 'none';
        progressFill.style.width = '0%';
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
        
        // Update complete
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

// Check for incomplete update after restart
async function checkRecoveryStatus() {
    try {
        const response = await fetch('/api/recovery-status');
        const data = await response.json();

        if (!data.has_incomplete_update) return;

        // Show recovery info in update section
        const section = document.getElementById('update-section');
        section.style.display = 'block';

        const statusBadge = document.getElementById('status-badge');
        const desc = document.getElementById('update-description');
        const action = document.getElementById('current-action');
        const logs = document.getElementById('logs');

        if (data.status === 'in_progress') {
            statusBadge.textContent = 'interrupted';
            statusBadge.className = 'badge failed';
            desc.textContent = data.description || 'Update was interrupted';
            action.textContent = data.current_action_name
                ? `Interrupted during: ${data.current_action_name}`
                : 'Interrupted during update';
        } else if (data.status === 'failed') {
            statusBadge.textContent = 'failed';
            statusBadge.className = 'badge failed';
            desc.textContent = data.description || 'Update failed';
            action.textContent = data.current_action_name
                ? `Failed at: ${data.current_action_name}`
                : 'Update failed';
        }

        const info = `Previous update was ${data.status === 'in_progress' ? 'interrupted (device restarted during update)' : 'failed'}. `
            + `${data.completed_actions} action(s) completed. `
            + `Last activity: ${data.last_updated || 'unknown'}`;

        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry warning';
        logEntry.textContent = info;
        logs.appendChild(logEntry);

        // Set progress bar
        if (data.completed_actions > 0) {
            document.getElementById('progress-fill').style.width = '50%';
            document.getElementById('progress-label').textContent =
                `${data.completed_actions} action(s) completed before interruption`;
            document.getElementById('progress-percent').textContent = '—';
        }
    } catch (error) {
        // Silent fail - recovery check is optional
        console.debug('Recovery check:', error);
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

