// Chat Interface JavaScript
class ChatInterface {
    constructor() {
        this.currentChatId = null;
        this.websocket = null;
        this.providers = {};
        this.isConnected = false;
        this.messageBuffer = '';
        
        this.init();
    }

    async init() {
        await this.loadProviders();
        await this.loadChats();
        await this.loadStats();
        this.setupEventListeners();
        this.setupAutoResize();
    }

    // Provider Management
    async loadProviders() {
        try {
            const response = await fetch('/api/providers');
            this.providers = await response.json();
            this.populateProviderSelects();
        } catch (error) {
            console.error('Error loading providers:', error);
        }
    }

    populateProviderSelects() {
        const selects = ['providerSelect', 'chatProviderSelect'];
        
        selects.forEach(selectId => {
            const select = document.getElementById(selectId);
            select.innerHTML = '<option value="">Auto (Best Available)</option>';
            
            Object.entries(this.providers).forEach(([name, config]) => {
                if (config.enabled) {
                    const option = document.createElement('option');
                    option.value = name;
                    option.textContent = name.toUpperCase();
                    select.appendChild(option);
                }
            });
        });

        // Add event listeners for dynamic model loading
        document.getElementById('providerSelect').addEventListener('change', (e) => {
            this.loadModelsForProvider(e.target.value, 'modelSelect');
            this.updateChatSettings();
        });

        document.getElementById('chatProviderSelect').addEventListener('change', (e) => {
            this.loadModelsForProvider(e.target.value, 'chatModelSelect');
        });
    }

    async loadModelsForProvider(providerName, modelSelectId) {
        const modelSelect = document.getElementById(modelSelectId);
        
        if (!providerName) {
            // Reset to auto when no provider selected
            modelSelect.innerHTML = '<option value="">Auto (Provider Default)</option>';
            return;
        }

        // Show loading state
        modelSelect.innerHTML = '<option value="">Loading models...</option>';
        modelSelect.disabled = true;

        try {
            // Call the main server's provider-specific models endpoint directly
            const response = await fetch(`/api/providers/${providerName}/models`);
            const data = await response.json();

            modelSelect.innerHTML = '<option value="">Auto (Provider Default)</option>';

            if (data.discovery_available && data.models && data.models.length > 0) {
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.id} (${model.owned_by})`;
                    modelSelect.appendChild(option);
                });
                console.log(`✅ Loaded ${data.models.length} models for provider ${providerName}:`, data.models.map(m => m.id));
            } else {
                // Add some common models for manual selection as fallback
                const commonModels = this.getCommonModelsForProvider(providerName);
                if (commonModels.length > 0) {
                    commonModels.forEach(modelId => {
                        const option = document.createElement('option');
                        option.value = modelId;
                        option.textContent = modelId + ' (common)';
                        modelSelect.appendChild(option);
                    });
                    console.log(`⚠️ No discovery available for ${providerName}, added common models:`, commonModels);
                } else {
                    console.log(`⚠️ No models available for provider ${providerName}`);
                }
                
                // Add info about manual entry
                const infoOption = document.createElement('option');
                infoOption.disabled = true;
                infoOption.textContent = '--- Manual entry available ---';
                modelSelect.appendChild(infoOption);
            }

        } catch (error) {
            console.error(`❌ Error loading models for provider ${providerName}:`, error);
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        } finally {
            modelSelect.disabled = false;
        }
    }

    getCommonModelsForProvider(providerName) {
        const commonModels = {
            'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
            'anthropic': ['claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'],
            'google': ['gemini-pro', 'gemini-pro-vision'],
            'cohere': ['command', 'command-light'],
            'meta': ['llama-2-70b-chat', 'llama-2-13b-chat'],
            'mistral': ['mistral-medium', 'mistral-small'],
            'groq': ['llama3-70b-8192', 'mixtral-8x7b-32768'],
            'together': ['meta-llama/Llama-2-70b-chat-hf', 'mistralai/Mixtral-8x7B-Instruct-v0.1'],
            'replicate': ['meta/llama-2-70b-chat', 'mistralai/mixtral-8x7b-instruct-v0.1'],
            'huggingface': ['microsoft/DialoGPT-large', 'facebook/blenderbot-400M-distill'],
            'chi': ['gpt-4.1-mini']
        };
        
        return commonModels[providerName.toLowerCase()] || [];
    }

    // Chat Management
    async loadChats() {
        try {
            const response = await fetch('/api/chat/chats?include_temporary=true&limit=50');
            const chats = await response.json();
            this.renderChatList(chats);
        } catch (error) {
            console.error('Error loading chats:', error);
            this.showError('Failed to load chats');
        }
    }

    renderChatList(chats) {
        const chatList = document.getElementById('chatList');
        
        if (chats.length === 0) {
            chatList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comments"></i>
                    <p>No chats yet</p>
                    <small>Create your first chat to get started</small>
                </div>
            `;
            return;
        }

        const html = chats.map(chat => `
            <div class="chat-item ${chat.id === this.currentChatId ? 'active' : ''}" 
                 onclick="chatInterface.selectChat(${chat.id})">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="chat-item-title">${this.escapeHtml(chat.title)}</div>
                        <div class="chat-item-preview text-muted">
                            ${chat.last_message ? this.escapeHtml(chat.last_message.substring(0, 50)) + '...' : 'No messages yet'}
                        </div>
                    </div>
                    <div class="d-flex flex-column align-items-end">
                        <span class="badge ${chat.is_temporary ? 'bg-temporary' : 'bg-permanent'} mb-1">
                            ${chat.is_temporary ? 'Temp' : 'Perm'}
                        </span>
                        <small class="chat-item-time text-muted">
                            ${this.formatTime(chat.updated_at)}
                        </small>
                    </div>
                </div>
            </div>
        `).join('');

        chatList.innerHTML = html;
    }

    async selectChat(chatId) {
        if (this.currentChatId === chatId) return;

        try {
            // Disconnect previous WebSocket
            this.disconnectWebSocket();

            // Load chat data
            const response = await fetch(`/api/chat/chats/${chatId}`);
            const data = await response.json();

            this.currentChatId = chatId;
            this.renderChatHeader(data.chat);
            this.renderMessages(data.messages);
            this.showChatInterface();
            this.connectWebSocket();

            // Update chat list selection
            document.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector(`[onclick="chatInterface.selectChat(${chatId})"]`).classList.add('active');

        } catch (error) {
            console.error('Error selecting chat:', error);
            this.showError('Failed to load chat');
        }
    }

    renderChatHeader(chat) {
        document.getElementById('chatTitle').textContent = chat.title;
        document.getElementById('chatType').textContent = chat.is_temporary ? 'Temporary' : 'Permanent';
        document.getElementById('chatType').className = `badge ${chat.is_temporary ? 'bg-temporary' : 'bg-permanent'}`;
        
        // Set provider and model
        if (chat.provider) {
            document.getElementById('providerSelect').value = chat.provider;
        }
        if (chat.model) {
            document.getElementById('modelSelect').value = chat.model;
        }
    }

    renderMessages(messages) {
        const container = document.getElementById('messagesList');
        
        if (messages.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-comment-dots"></i>
                    <p>No messages yet</p>
                    <small>Start the conversation below</small>
                </div>
            `;
            return;
        }

        const html = messages.map(msg => this.renderMessage(msg)).join('');
        container.innerHTML = html;
        this.scrollToBottom();
    }

    renderMessage(message) {
        const timeStr = this.formatTime(message.created_at);
        const isUser = message.role === 'user';
        const isSystem = message.role === 'system';
        
        let providerInfo = '';
        if (message.role === 'assistant' && message.metadata) {
            const provider = message.metadata.provider || 'Unknown';
            const model = message.metadata.model || 'Unknown';
            const responseTime = message.metadata.response_time ? 
                `${message.metadata.response_time.toFixed(2)}s` : '';
            providerInfo = `
                <div class="message-info">
                    ${provider.toUpperCase()} • ${model} ${responseTime ? `• ${responseTime}` : ''}
                </div>
            `;
        }

        return `
            <div class="message ${message.role}" data-message-id="${message.id}">
                <div class="message-bubble">
                    ${this.formatMessageContent(message.content)}
                    ${isUser ? `<div class="message-info">${timeStr}</div>` : ''}
                    ${providerInfo}
                </div>
                ${!isSystem ? `
                    <div class="message-actions">
                        <button class="btn btn-sm btn-outline-secondary" onclick="chatInterface.copyMessage(${message.id})" title="Copy">
                            <i class="fas fa-copy"></i>
                        </button>
                        ${isUser ? `
                            <button class="btn btn-sm btn-outline-primary" onclick="chatInterface.editMessage(${message.id})" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }

    formatMessageContent(content) {
        // Basic formatting for code blocks and line breaks
        return this.escapeHtml(content)
            .replace(/\n/g, '<br>')
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    showChatInterface() {
        document.getElementById('welcomeMessage').style.display = 'none';
        document.getElementById('chatHeader').style.display = 'block';
        document.getElementById('messagesList').style.display = 'block';
        document.getElementById('messageInput').style.display = 'block';
    }

    hideChatInterface() {
        document.getElementById('welcomeMessage').style.display = 'block';
        document.getElementById('chatHeader').style.display = 'none';
        document.getElementById('messagesList').style.display = 'none';
        document.getElementById('messageInput').style.display = 'none';
    }

    // WebSocket Management
    connectWebSocket() {
        if (!this.currentChatId || this.websocket) return;

        try {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${window.location.host}/api/chat/chats/${this.currentChatId}/stream`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus('connected');
                console.log('WebSocket connected');
            };

            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };

            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('disconnected');
                console.log('WebSocket disconnected');
            };

            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('disconnected');
            };

        } catch (error) {
            console.error('Error connecting WebSocket:', error);
        }
    }

    disconnectWebSocket() {
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
            this.isConnected = false;
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'message_saved':
                console.log('Message saved:', data.message_id);
                break;
                
            case 'ai_thinking':
                this.showTypingIndicator();
                break;
                
            case 'ai_chunk':
                this.appendToResponse(data.content);
                if (data.is_final) {
                    this.finalizeResponse(data);
                }
                break;
                
            case 'ai_complete':
                this.hideTypingIndicator();
                this.loadChats(); // Refresh chat list
                break;
                
            case 'ai_error':
                this.hideTypingIndicator();
                this.showError('AI Error: ' + data.content);
                break;
                
            case 'pong':
                // Keep-alive response
                break;
                
            default:
                console.log('Unknown WebSocket message:', data);
        }
    }

    // Message Sending
    async sendMessage() {
        const textarea = document.getElementById('messageTextarea');
        const content = textarea.value.trim();
        
        if (!content || !this.currentChatId) return;

        const provider = document.getElementById('providerSelect').value || null;
        const model = document.getElementById('modelSelect').value || null;

        // Clear input
        textarea.value = '';
        this.resizeTextarea(textarea);

        // Add user message to UI immediately
        this.addUserMessageToUI(content);

        if (this.isConnected && this.websocket) {
            // Send via WebSocket for real-time streaming
            this.websocket.send(JSON.stringify({
                type: 'user_message',
                content: content,
                provider: provider,
                model: model,
                metadata: {}
            }));
        } else {
            // Fallback to REST API
            try {
                await fetch(`/api/chat/chats/${this.currentChatId}/messages`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        role: 'user',
                        content: content,
                        metadata: { provider, model }
                    })
                });
                
                // Poll for response
                setTimeout(() => this.pollForNewMessages(), 1000);
                
            } catch (error) {
                console.error('Error sending message:', error);
                this.showError('Failed to send message');
            }
        }
    }

    addUserMessageToUI(content) {
        const messagesList = document.getElementById('messagesList');
        const userMessage = {
            id: Date.now(), // Temporary ID
            role: 'user',
            content: content,
            created_at: new Date().toISOString()
        };
        
        messagesList.innerHTML += this.renderMessage(userMessage);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        document.getElementById('typingIndicator').style.display = 'block';
        
        // Add loading message bubble
        const messagesList = document.getElementById('messagesList');
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message assistant';
        loadingDiv.id = 'loadingMessage';
        loadingDiv.innerHTML = `
            <div class="loading-message">
                <div class="spinner-border text-primary" role="status"></div>
                <span>AI is thinking...</span>
            </div>
        `;
        messagesList.appendChild(loadingDiv);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        document.getElementById('typingIndicator').style.display = 'none';
        const loadingMsg = document.getElementById('loadingMessage');
        if (loadingMsg) {
            loadingMsg.remove();
        }
    }

    appendToResponse(chunk) {
        this.messageBuffer += chunk;
        
        // Update or create response bubble
        let responseMsg = document.getElementById('streamingResponse');
        if (!responseMsg) {
            const loadingMsg = document.getElementById('loadingMessage');
            if (loadingMsg) {
                loadingMsg.remove();
            }
            
            responseMsg = document.createElement('div');
            responseMsg.className = 'message assistant';
            responseMsg.id = 'streamingResponse';
            responseMsg.innerHTML = `
                <div class="message-bubble">
                    <div class="response-content"></div>
                </div>
            `;
            
            document.getElementById('messagesList').appendChild(responseMsg);
        }
        
        const contentDiv = responseMsg.querySelector('.response-content');
        contentDiv.innerHTML = this.formatMessageContent(this.messageBuffer);
        this.scrollToBottom();
    }

    finalizeResponse(data) {
        this.hideTypingIndicator();
        const streamingMsg = document.getElementById('streamingResponse');
        if (streamingMsg) {
            streamingMsg.removeAttribute('id');
        }
        this.messageBuffer = '';
    }

    async pollForNewMessages() {
        // Simple polling fallback when WebSocket is not available
        try {
            const response = await fetch(`/api/chat/chats/${this.currentChatId}`);
            const data = await response.json();
            this.renderMessages(data.messages);
        } catch (error) {
            console.error('Error polling messages:', error);
        }
    }

    // Chat Creation
    async createNewChat(isTemporary = false) {
        document.getElementById('isTemporaryCheck').checked = isTemporary;
        const modal = new bootstrap.Modal(document.getElementById('createChatModal'));
        modal.show();
    }

    async submitCreateChat() {
        const form = document.getElementById('createChatForm');
        const formData = new FormData(form);
        
        const title = document.getElementById('chatTitleInput').value.trim();
        const systemPrompt = document.getElementById('systemPromptInput').value.trim();
        const provider = document.getElementById('chatProviderSelect').value || null;
        const model = document.getElementById('chatModelSelect').value || null;
        const isTemporary = document.getElementById('isTemporaryCheck').checked;

        if (!title) {
            alert('Please enter a chat title');
            return;
        }

        try {
            const response = await fetch('/api/chat/chats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: title,
                    system_prompt: systemPrompt || null,
                    provider: provider,
                    model: model,
                    is_temporary: isTemporary
                })
            });

            const result = await response.json();
            
            if (result.success) {
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('createChatModal')).hide();
                
                // Clear form
                form.reset();
                
                // Refresh chat list and select new chat
                await this.loadChats();
                await this.selectChat(result.chat_id);
                
            } else {
                throw new Error('Failed to create chat');
            }

        } catch (error) {
            console.error('Error creating chat:', error);
            this.showError('Failed to create chat');
        }
    }

    // Chat Editing
    async editChatTitle() {
        if (!this.currentChatId) return;
        
        const currentTitle = document.getElementById('chatTitle').textContent;
        document.getElementById('editTitleInput').value = currentTitle;
        
        const modal = new bootstrap.Modal(document.getElementById('editTitleModal'));
        modal.show();
    }

    async submitEditTitle() {
        const newTitle = document.getElementById('editTitleInput').value.trim();
        
        if (!newTitle || !this.currentChatId) {
            alert('Please enter a valid title');
            return;
        }

        try {
            const response = await fetch(`/api/chat/chats/${this.currentChatId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: newTitle
                })
            });

            const result = await response.json();
            
            if (result.success) {
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('editTitleModal')).hide();
                
                // Update UI
                document.getElementById('chatTitle').textContent = newTitle;
                await this.loadChats();
                
            } else {
                throw new Error('Failed to update title');
            }

        } catch (error) {
            console.error('Error updating title:', error);
            this.showError('Failed to update title');
        }
    }

    async deleteCurrentChat() {
        if (!this.currentChatId) return;
        
        const chatTitle = document.getElementById('chatTitle').textContent;
        if (!confirm(`Are you sure you want to delete "${chatTitle}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/chat/chats/${this.currentChatId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentChatId = null;
                this.disconnectWebSocket();
                this.hideChatInterface();
                await this.loadChats();
            } else {
                throw new Error('Failed to delete chat');
            }

        } catch (error) {
            console.error('Error deleting chat:', error);
            this.showError('Failed to delete chat');
        }
    }

    // Statistics
    async loadStats() {
        try {
            const response = await fetch('/api/chat/stats');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats;
                document.getElementById('chatStats').innerHTML = `
                    ${stats.total_chats} chats • ${stats.total_messages} messages
                `;
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    // Utility Methods
    setupEventListeners() {
        // Enter key to send message
        document.getElementById('messageTextarea').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Model change updates chat settings (provider change is handled in populateProviderSelects)
        document.getElementById('modelSelect').addEventListener('change', (e) => {
            this.updateChatSettings();
        });
    }

    setupAutoResize() {
        const textarea = document.getElementById('messageTextarea');
        textarea.addEventListener('input', () => this.resizeTextarea(textarea));
    }

    resizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    async updateChatSettings() {
        if (!this.currentChatId) return;

        const provider = document.getElementById('providerSelect').value || null;
        const model = document.getElementById('modelSelect').value || null;

        try {
            await fetch(`/api/chat/chats/${this.currentChatId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    provider: provider,
                    model: model
                })
            });
        } catch (error) {
            console.error('Error updating chat settings:', error);
        }
    }

    updateConnectionStatus(status) {
        // Remove existing status
        const existing = document.querySelector('.connection-status');
        if (existing) existing.remove();

        // Add new status
        const statusDiv = document.createElement('div');
        statusDiv.className = `connection-status ${status}`;
        
        const icon = status === 'connected' ? 'wifi' : 
                    status === 'connecting' ? 'spinner fa-spin' : 'wifi-slash';
        const text = status === 'connected' ? 'Connected' :
                    status === 'connecting' ? 'Connecting...' : 'Disconnected';
        
        statusDiv.innerHTML = `<i class="fas fa-${icon}"></i> ${text}`;
        document.body.appendChild(statusDiv);

        // Auto-hide after 3 seconds if connected
        if (status === 'connected') {
            setTimeout(() => {
                if (statusDiv.parentNode) {
                    statusDiv.remove();
                }
            }, 3000);
        }
    }

    copyMessage(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"] .message-bubble`);
        const text = messageElement.textContent;
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccess('Message copied to clipboard');
        });
    }

    clearInput() {
        const textarea = document.getElementById('messageTextarea');
        textarea.value = '';
        this.resizeTextarea(textarea);
    }

    scrollToBottom() {
        const container = document.getElementById('messagesContainer');
        container.scrollTop = container.scrollHeight;
    }

    formatTime(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        
        return date.toLocaleDateString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        this.showAlert('danger', message);
    }

    showSuccess(message) {
        this.showAlert('success', message);
    }

    showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 70px; right: 20px; z-index: 1050; max-width: 300px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Global functions for HTML onclick handlers
function createNewChat(isTemporary) {
    chatInterface.createNewChat(isTemporary);
}

function submitCreateChat() {
    chatInterface.submitCreateChat();
}

function editChatTitle() {
    chatInterface.editChatTitle();
}

function submitEditTitle() {
    chatInterface.submitEditTitle();
}

function deleteCurrentChat() {
    chatInterface.deleteCurrentChat();
}

function sendMessage() {
    chatInterface.sendMessage();
}

function clearInput() {
    chatInterface.clearInput();
}

// Initialize chat interface when page loads
let chatInterface;
document.addEventListener('DOMContentLoaded', function() {
    chatInterface = new ChatInterface();
});
