// AI Engine Dashboard JavaScript

// Global variables
let startTime = Date.now();
let refreshInterval;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Engine Dashboard loaded');
    updateDashboard();
    refreshInterval = setInterval(updateDashboard, 30000); // Update every 30 seconds
});

// Update dashboard data
async function updateDashboard() {
    try {
        // Update status
        const statusResponse = await fetch('/api/status');
        const status = await statusResponse.json();
        updateStatusCards(status);

        // Update statistics
        const statsResponse = await fetch('/api/statistics');
        const stats = await statsResponse.json();
        updateStatistics(stats);

        // Update uptime
        updateUptime();

    } catch (error) {
        console.error('Error updating dashboard:', error);
        showError('Failed to update dashboard');
    }
}

// Update status cards
function updateStatusCards(status) {
    document.getElementById('activeProviders').textContent = status.available_providers || 0;
    document.getElementById('totalProviders').textContent = status.total_providers || 0;
    document.getElementById('flaggedProviders').textContent = status.flagged_providers || 0;

    // Update provider chart
    updateProviderChart(status);
}

// Update provider status chart
function updateProviderChart(status) {
    const ctx = document.getElementById('providerStatusChart');
    if (!ctx) return;
    
    // Destroy existing chart if it exists
    if (window.providerChart) {
        window.providerChart.destroy();
    }

    window.providerChart = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['Active', 'Flagged'],
            datasets: [{
                data: [status.available_providers || 0, status.flagged_providers || 0],
                backgroundColor: ['#28a745', '#ffc107'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

// Update statistics display
function updateStatistics(stats) {
    const summary = stats.summary || {};
    const providers = stats.providers || {};

    // Update summary cards
    document.getElementById('totalKeys').textContent = summary.total_keys || 0;
    document.getElementById('totalRequests').textContent = summary.total_requests || 0;

    // Update key usage summary
    updateKeyUsageSummary(providers);

    // Update provider details
    updateProviderDetails(providers);

    // Update recent activity
    updateRecentActivity(providers);
}

// Update provider details
function updateProviderDetails(providers) {
    const container = document.getElementById('providerDetails');
    if (!container) return;

    let html = '';
    for (const [provider, data] of Object.entries(providers)) {
        html += `<div class="col-md-6 mb-3">
            <div class="card">
                <div class="card-header">
                    <h6 class="mb-0">${provider}</h6>
                </div>
                <div class="card-body">`;

        for (const [key, stats] of Object.entries(data)) {
            const status = stats.rate_limited ? '🔴 RATE LIMITED' : '🟢 ACTIVE';
            html += `<div class="mb-2">
                <strong>${key}:</strong> ${stats.total_requests} requests,
                ${stats.success_rate} success ${status}
            </div>`;
        }

        html += '</div></div></div>';
    }

    container.innerHTML = html;
}

// Update key usage summary
function updateKeyUsageSummary(providers) {
    const summaryContainer = document.getElementById('keyUsageSummary');
    if (!summaryContainer) return;

    let html = '<div class="row">';
    
    for (const [provider, data] of Object.entries(providers)) {
        for (const [keyName, stats] of Object.entries(data)) {
            const successRate = stats.requests > 0 ? ((stats.successes / stats.requests) * 100).toFixed(1) : 0;
            const status = stats.rate_limited ? '🔴' : (stats.successes > 0 ? '🟢' : '🟡');
            const lastUsed = stats.last_used ? new Date(stats.last_used).toLocaleString() : 'Never';
            
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card h-100">
                        <div class="card-body">
                            <h6 class="card-title">${status} ${provider}/${keyName}</h6>
                            <div class="row text-center">
                                <div class="col-4">
                                    <div class="text-primary h5">${stats.requests}</div>
                                    <small class="text-muted">Requests</small>
                                </div>
                                <div class="col-4">
                                    <div class="text-success h5">${successRate}%</div>
                                    <small class="text-muted">Success</small>
                                </div>
                                <div class="col-4">
                                    <div class="text-info h5">${stats.successes}</div>
                                    <small class="text-muted">Successes</small>
                                </div>
                            </div>
                            <hr>
                            <small class="text-muted">Last used: ${lastUsed}</small>
                        </div>
                    </div>
                </div>
            `;
        }
    }
    
    html += '</div>';
    summaryContainer.innerHTML = html || '<p class="text-muted">No key usage data available</p>';
}

// Update recent activity
function updateRecentActivity(providers) {
    const activityContainer = document.getElementById('recentActivity');
    if (!activityContainer) return;

    const activities = [];
    
    // Collect all activities
    for (const [provider, data] of Object.entries(providers)) {
        for (const [keyName, stats] of Object.entries(data)) {
            if (stats.last_used) {
                activities.push({
                    provider,
                    key: keyName,
                    lastUsed: new Date(stats.last_used),
                    requests: stats.requests,
                    successes: stats.successes,
                    failures: stats.failures
                });
            }
        }
    }

    // Sort by last used (most recent first)
    activities.sort((a, b) => b.lastUsed - a.lastUsed);

    // Generate HTML
    let html = '';
    if (activities.length === 0) {
        html = '<p class="text-muted">No recent activity</p>';
    } else {
        activities.slice(0, 10).forEach(activity => {
            const timeAgo = getTimeAgo(activity.lastUsed);
            const status = activity.successes > activity.failures ? '🟢' : '🔴';
            
            html += `
                <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                    <div>
                        <strong>${status} ${activity.provider}/${activity.key}</strong><br>
                        <small class="text-muted">${activity.requests} requests (${activity.successes} success, ${activity.failures} failed)</small>
                    </div>
                    <small class="text-muted">${timeAgo}</small>
                </div>
            `;
        });
    }
    
    activityContainer.innerHTML = html;
}

// Helper function to get time ago string
function getTimeAgo(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
}

// Update uptime counter
function updateUptime() {
    const uptime = Math.floor((Date.now() - startTime) / 1000 / 60);
    const uptimeElement = document.getElementById('uptime');
    if (uptimeElement) {
        uptimeElement.textContent = uptime + 'm';
    }
}

// Test a provider
async function testProvider(providerName) {
    if (!confirm(`Test ${providerName}?`)) return;

    try {
        const response = await fetch('/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: 'auto',
                messages: [{ role: 'user', content: `Hello from ${providerName} test!` }]
            })
        });

        const result = await response.json();
        if (response.ok) {
            showSuccess(`${providerName} test successful!`);
        } else {
            showError(`${providerName} test failed: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        showError(`Test failed: ${error.message}`);
    }
}

// Test a model
async function testModel(modelId) {
    if (!confirm(`Test ${modelId}?`)) return;

    try {
        const response = await fetch('/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: modelId,
                messages: [{ role: 'user', content: `Hello! Testing ${modelId}` }]
            })
        });

        const result = await response.json();
        if (response.ok) {
            showSuccess(`${modelId} test successful!`);
        } else {
            showError(`${modelId} test failed: ${result.detail || 'Unknown error'}`);
        }
    } catch (error) {
        showError(`Test failed: ${error.message}`);
    }
}

// Utility functions
function showSuccess(message) {
    showAlert(message, 'success');
}

function showError(message) {
    showAlert(message, 'danger');
}

function showAlert(message, type) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alert.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alert);

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
