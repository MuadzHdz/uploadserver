"""
Advanced JavaScript features for UploadServer Pro
"""

class UploadServerPro {
    constructor() {
        this.socket = null;
        this.selectedFiles = new Set();
        this.currentUser = null;
        this.init();
    }

    init() {
        this.initializeSocket();
        this.initializeFileSelection();
        this.initializeDragAndDrop();
        this.initializeShortcuts();
        this.initializeBatchOperations();
        this.initializeRealTimeFeatures();
    }

    initializeSocket() {
        this.socket = io();
        
        // Connection events
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.showNotification('Connected to server', 'success');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Disconnected from server', 'error');
        });

        // File operation events
        this.socket.on('file_uploaded', (data) => {
            this.handleFileUploaded(data);
        });

        this.socket.on('file_operation_update', (data) => {
            this.handleFileOperation(data);
        });

        this.socket.on('user_typing', (data) => {
            this.handleUserTyping(data);
        });

        this.socket.on('user_stopped_typing', (data) => {
            this.handleUserStoppedTyping(data);
        });

        this.socket.on('new_comment', (data) => {
            this.handleNewComment(data);
        });

        this.socket.on('system_message', (data) => {
            this.showSystemNotification(data.message, data.type);
        });
    }

    initializeFileSelection() {
        // File selection for batch operations
        document.addEventListener('click', (e) => {
            const fileItem = e.target.closest('.file-item');
            if (!fileItem) return;

            const checkbox = fileItem.querySelector('.file-checkbox');
            const fileLink = fileItem.querySelector('.file-info a');
            
            if (checkbox && e.target !== checkbox && e.target !== fileLink) {
                // Toggle selection with Ctrl/Cmd
                if (e.ctrlKey || e.metaKey) {
                    checkbox.checked = !checkbox.checked;
                } else {
                    // Clear previous selection and select this one
                    document.querySelectorAll('.file-checkbox').forEach(cb => cb.checked = false);
                    checkbox.checked = true;
                }
                this.updateSelectedFiles();
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                document.querySelectorAll('.file-checkbox').forEach(cb => {
                    cb.checked = e.target.checked;
                });
                this.updateSelectedFiles();
            });
        }
    }

    initializeDragAndDrop() {
        const dropZones = document.querySelectorAll('.drop-zone');
        
        dropZones.forEach(zone => {
            zone.addEventListener('dragover', this.handleDragOver.bind(this));
            zone.addEventListener('drop', this.handleDrop.bind(this));
            zone.addEventListener('dragleave', this.handleDragLeave.bind(this));
        });
    }

    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const dropZone = e.currentTarget;
        dropZone.classList.add('drag-over');
        
        // Show visual feedback
        const draggedFiles = e.dataTransfer.items.length;
        this.updateDropZoneUI(dropZone, `Drop ${draggedFiles} file${draggedFiles > 1 ? 's' : ''}`);
    }

    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const dropZone = e.currentTarget;
        dropZone.classList.remove('drag-over');
        
        const files = Array.from(e.dataTransfer.files);
        this.uploadMultipleFiles(files, dropZone.dataset.path || '');
    }

    handleDragLeave(e) {
        const dropZone = e.currentTarget;
        
        // Only remove class if leaving the drop zone itself
        if (!dropZone.contains(e.relatedTarget)) {
            dropZone.classList.remove('drag-over');
            this.resetDropZoneUI(dropZone);
        }
    }

    initializeShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+A - Select all
            if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
                const selectAll = document.getElementById('select-all');
                if (selectAll) {
                    selectAll.checked = true;
                    selectAll.dispatchEvent(new Event('change'));
                    e.preventDefault();
                }
            }
            
            // Delete key - Delete selected files
            if (e.key === 'Delete') {
                this.deleteSelectedFiles();
            }
            
            // Ctrl+V - Paste files (if clipboard has files)
            if ((e.ctrlKey || e.metaKey) && e.key === 'v') {
                navigator.clipboard.read().then(clipboardItems => {
                    for (const item of clipboardItems) {
                        if (item.types.includes('Files')) {
                            const files = item.getAsFileSystemHandle ? [item.getAsFileSystemHandle()] : [];
                            if (files.length > 0) {
                                this.uploadMultipleFiles(files);
                                e.preventDefault();
                            }
                        }
                    }
                });
            }
            
            // Escape - Deselect all
            if (e.key === 'Escape') {
                document.querySelectorAll('.file-checkbox').forEach(cb => cb.checked = false);
                this.updateSelectedFiles();
            }
            
            // Ctrl+F - Focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                    e.preventDefault();
                }
            }
        });
    }

    initializeBatchOperations() {
        // Batch actions toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'batch-toolbar hidden';
        toolbar.innerHTML = `
            <div class="toolbar-content">
                <span class="selection-count">0 selected</span>
                <div class="toolbar-actions">
                    <button class="btn small-btn" onclick="uploadServerPro.downloadSelected()">
                        <span class="material-icons">download</span> Download
                    </button>
                    <button class="btn small-btn" onclick="uploadServerPro.moveSelected()">
                        <span class="material-icons">folder</span> Move
                    </button>
                    <button class="btn small-btn" onclick="uploadServerPro.copySelected()">
                        <span class="material-icons">content_copy</span> Copy
                    </button>
                    <button class="btn small-btn danger" onclick="uploadServerPro.deleteSelected()">
                        <span class="material-icons">delete</span> Delete
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(toolbar);
        this.batchToolbar = toolbar;
    }

    initializeRealTimeFeatures() {
        // Auto-refresh file list
        this.setupAutoRefresh();
        
        // Real-time collaboration indicators
        this.setupCollaborationIndicators();
        
        // Live notifications
        this.setupLiveNotifications();
    }

    updateSelectedFiles() {
        this.selectedFiles.clear();
        document.querySelectorAll('.file-checkbox:checked').forEach(checkbox => {
            const fileItem = checkbox.closest('.file-item');
            const fileId = fileItem.dataset.fileId;
            if (fileId) {
                this.selectedFiles.add(fileId);
            }
        });
        
        this.updateBatchToolbar();
        this.updateKeyboardShortcuts();
    }

    updateBatchToolbar() {
        if (this.selectedFiles.size === 0) {
            this.batchToolbar.classList.add('hidden');
        } else {
            this.batchToolbar.classList.remove('hidden');
            const selectionCount = this.batchToolbar.querySelector('.selection-count');
            selectionCount.textContent = `${this.selectedFiles.size} selected`;
        }
    }

    updateKeyboardShortcuts() {
        // Update keyboard shortcuts based on selection
        const hasSelection = this.selectedFiles.size > 0;
        
        // Enable/disable shortcut hints
        const shortcuts = document.querySelectorAll('.keyboard-shortcut');
        shortcuts.forEach(shortcut => {
            if (shortcut.dataset.requiresSelection) {
                shortcut.style.opacity = hasSelection ? '1' : '0.3';
            }
        });
    }

    uploadMultipleFiles(files, path = '') {
        const formData = new FormData();
        const progressContainer = this.createProgressContainer(files.length);
        
        files.forEach((file, index) => {
            formData.append('files[]', file);
        });
        formData.append('path', path);
        formData.append('batch_upload', 'true');
        
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload/batch');
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = (e.loaded / e.total) * 100;
                this.updateProgress(progressContainer, percent, index);
            }
        });
        
        xhr.addEventListener('load', () => {
            this.showNotification(`Uploaded ${files.length} files successfully`, 'success');
            setTimeout(() => this.closeProgressContainer(progressContainer), 2000);
            this.refreshFileList();
        });
        
        xhr.addEventListener('error', () => {
            this.showNotification('Error uploading files', 'error');
            this.closeProgressContainer(progressContainer);
        });
        
        xhr.send(formData);
    }

    createProgressContainer(fileCount) {
        const container = document.createElement('div');
        container.className = 'progress-container';
        container.innerHTML = `
            <div class="progress-header">
                <h3>Uploading ${fileCount} files</h3>
                <button class="close-btn" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="progress-list">
                ${Array.from({length: fileCount}, (_, i) => `
                    <div class="progress-item" data-index="${i}">
                        <div class="progress-filename">File ${i + 1}</div>
                        <div class="progress-bar">
                            <div class="progress-fill"></div>
                        </div>
                        <div class="progress-percent">0%</div>
                    </div>
                `).join('')}
            </div>
        `;
        
        document.body.appendChild(container);
        return container;
    }

    updateProgress(container, percent, fileIndex) {
        const progressItem = container.querySelector(`[data-index="${fileIndex}"]`);
        if (progressItem) {
            const fill = progressItem.querySelector('.progress-fill');
            const percentText = progressItem.querySelector('.progress-percent');
            
            fill.style.width = `${percent}%`;
            percentText.textContent = `${Math.round(percent)}%`;
        }
    }

    closeProgressContainer(container) {
        container.remove();
    }

    deleteSelectedFiles() {
        if (this.selectedFiles.size === 0) return;
        
        if (!confirm(`Are you sure you want to delete ${this.selectedFiles.size} file(s)?`)) {
            return;
        }
        
        const fileIds = Array.from(this.selectedFiles);
        
        fetch('/api/files/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                operation: 'delete',
                file_ids: fileIds
            })
        })
        .then(response => response.json())
        .then(data => {
            this.showNotification(`Deleted ${data.summary.success} file(s)`, 'success');
            this.refreshFileList();
        })
        .catch(error => {
            this.showNotification('Error deleting files', 'error');
        });
    }

    downloadSelected() {
        if (this.selectedFiles.size === 0) return;
        
        const fileIds = Array.from(this.selectedFiles);
        
        // Create a zip download request
        fetch('/api/files/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                operation: 'download',
                file_ids: fileIds
            })
        })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `files_${Date.now()}.zip`;
            a.click();
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            this.showNotification('Error downloading files', 'error');
        });
    }

    moveSelected() {
        if (this.selectedFiles.size === 0) return;
        
        const fileIds = Array.from(this.selectedFiles);
        
        // Show move dialog
        this.showMoveDialog(fileIds);
    }

    copySelected() {
        if (this.selectedFiles.size === 0) return;
        
        const fileIds = Array.from(this.selectedFiles);
        
        // Copy to clipboard
        navigator.clipboard.writeText(JSON.stringify(fileIds))
            .then(() => {
                this.showNotification('File references copied to clipboard', 'success');
            })
            .catch(() => {
                this.showNotification('Failed to copy to clipboard', 'error');
            });
    }

    showMoveDialog(fileIds) {
        const dialog = document.createElement('div');
        dialog.className = 'move-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Move ${fileIds.length} file(s)</h3>
                <div class="directory-browser">
                    <input type="text" id="move-path" placeholder="Enter destination path" />
                    <div class="directory-suggestions" id="directory-suggestions"></div>
                </div>
                <div class="dialog-actions">
                    <button class="btn secondary" onclick="uploadServerPro.closeMoveDialog()">Cancel</button>
                    <button class="btn" onclick="uploadServerPro.executeMove('${fileIds.join(',')}')">Move</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Load directory suggestions
        this.loadDirectorySuggestions('/' + (this.currentPath || ''));
        
        // Focus input
        document.getElementById('move-path').focus();
    }

    loadDirectorySuggestions(basePath) {
        // Load directory structure for suggestions
        fetch(`/api/directories?path=${encodeURIComponent(basePath)}`)
            .then(response => response.json())
            .then(data => {
                const suggestionsContainer = document.getElementById('directory-suggestions');
                if (suggestionsContainer) {
                    suggestionsContainer.innerHTML = data.directories.map(dir => 
                        `<div class="directory-item" onclick="uploadServerPro.selectDirectory('${dir.path}')">${dir.name}</div>`
                    ).join('');
                }
            })
            .catch(() => {
                // Silently fail if API doesn't exist
            });
    }

    selectDirectory(path) {
        const input = document.getElementById('move-path');
        if (input) {
            input.value = path;
        }
    }

    closeMoveDialog() {
        const dialog = document.querySelector('.move-dialog');
        if (dialog) {
            dialog.remove();
        }
    }

    executeMove(fileIds, path) {
        fetch('/api/files/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                operation: 'move',
                file_ids: fileIds.split(','),
                destination: path
            })
        })
        .then(response => response.json())
        .then(data => {
            this.showNotification(`Moved ${data.summary.success} file(s)`, 'success');
            this.closeMoveDialog();
            this.refreshFileList();
        })
        .catch(error => {
            this.showNotification('Error moving files', 'error');
        });
    }

    setupAutoRefresh() {
        // Auto-refresh file list every 30 seconds
        setInterval(() => {
            if (!document.hidden) {
                this.refreshFileList();
            }
        }, 30000);
        
        // Refresh when tab becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.refreshFileList();
            }
        });
    }

    refreshFileList() {
        const currentPath = this.getCurrentPath();
        if (currentPath) {
            fetch(`/api/files?path=${encodeURIComponent(currentPath)}`)
                .then(response => response.json())
                .then(data => {
                    this.updateFileListUI(data.files);
                })
                .catch(() => {
                    // Silently fail
                });
        }
    }

    updateFileListUI(files) {
        const fileListContainer = document.querySelector('.file-list');
        if (fileListContainer) {
            // Keep current selections and scroll position
            const scrollTop = fileListContainer.scrollTop;
            
            // Update UI with new files
            // This would need to be implemented based on your specific UI structure
            
            fileListContainer.scrollTop = scrollTop;
        }
    }

    setupCollaborationIndicators() {
        // Show active users in current directory
        setInterval(() => {
            this.updateActiveUsers();
        }, 5000);
    }

    updateActiveUsers() {
        const currentPath = this.getCurrentPath();
        
        // Emit user presence
        this.socket.emit('join_directory', {
            path: currentPath,
            user_id: this.currentUser?.id
        });
    }

    setupLiveNotifications() {
        // Request notification permission
        if ('Notification' in window) {
            Notification.requestPermission();
        }
    }

    showNotification(message, type = 'info') {
        // Show in-app notification
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.innerHTML = `
            <span class="material-icons">${this.getNotificationIcon(type)}</span>
            <span class="notification-text">${message}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
        
        // Show system notification if tab is hidden
        if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
            new Notification('UploadServer Pro', {
                body: message,
                icon: '/static/icon-192.png'
            });
        }
    }

    showSystemNotification(message, type = 'info') {
        // System-wide notifications (for admins)
        this.showNotification(`🔔 ${message}`, type);
    }

    getNotificationIcon(type) {
        const icons = {
            'success': 'check_circle',
            'error': 'error',
            'warning': 'warning',
            'info': 'info'
        };
        return icons[type] || icons.info;
    }

    getCsrfToken() {
        // Get CSRF token from meta tag or cookie
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Fallback to cookie
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return decodeURIComponent(value);
            }
        }
        return '';
    }

    getCurrentPath() {
        // Get current path from URL or data attribute
        return window.location.pathname.replace('/browse/', '') || '';
    }

    handleFileUploaded(data) {
        this.showNotification(`${data.file.original_filename} uploaded`, 'success');
        this.refreshFileList();
        
        // Update storage indicator
        this.updateStorageIndicator();
    }

    handleFileOperation(data) {
        this.showNotification(`${data.user.username} ${data.operation} ${data.details.filename || 'file'}`, 'info');
        this.refreshFileList();
    }

    handleUserTyping(data) {
        // Show typing indicator in collaboration mode
        const typingIndicator = document.getElementById(`typing-${data.user_id}`);
        if (typingIndicator) {
            typingIndicator.style.display = 'block';
            typingIndicator.textContent = `${data.username} is typing...`;
        }
    }

    handleUserStoppedTyping(data) {
        // Hide typing indicator
        const typingIndicator = document.getElementById(`typing-${data.user_id}`);
        if (typingIndicator) {
            typingIndicator.style.display = 'none';
        }
    }

    handleNewComment(data) {
        this.showNotification(`New comment on ${data.file.original_filename}`, 'info');
        // Update comment section if visible
        this.updateCommentSection(data);
    }

    updateCommentSection(data) {
        const commentSection = document.querySelector('.comments-section');
        if (commentSection) {
            // Add new comment to UI
            const commentElement = document.createElement('div');
            commentElement.className = 'comment-item';
            commentElement.innerHTML = `
                <div class="comment-header">
                    <strong>${data.username}</strong>
                    <span class="comment-time">${new Date(data.timestamp).toLocaleString()}</span>
                </div>
                <div class="comment-content">${data.comment.content}</div>
            `;
            commentSection.appendChild(commentElement);
        }
    }

    updateStorageIndicator() {
        // Update storage usage indicator
        fetch('/api/user/storage')
            .then(response => response.json())
            .then(data => {
                const storageElement = document.getElementById('storage-indicator');
                if (storageElement) {
                    storageElement.style.width = `${data.usage_percent}%`;
                    storageElement.setAttribute('title', `${data.total_size / 1024 / 1024} MB of ${data.quota / 1024 / 1024} MB used`);
                }
            });
    }
}

// Initialize the application
const uploadServerPro = new UploadServerPro();

// Global functions for onclick handlers
window.uploadServerPro = uploadServerPro;