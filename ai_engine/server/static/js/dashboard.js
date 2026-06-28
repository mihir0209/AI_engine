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

    // Update summary cards (if they exist on this page)
    const totalKeysElement = document.getElementById('totalKeys');
    const totalRequestsElement = document.getElementById('totalRequests');
    
    if (totalKeysElement) totalKeysElement.textContent = summary.total_keys || 0;
    if (totalRequestsElement) totalRequestsElement.textContent = summary.total_requests || 0;

    // Note: Key usage summary and recent activity removed from dashboard
    // These features are available on the dedicated Statistics page
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
