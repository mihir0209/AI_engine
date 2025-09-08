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
        this.setupTemporaryChatCleanup();
    }

    // Setup temporary chat cleanup on page unload
    setupTemporaryChatCleanup() {
        // Track temporary chats opened in this session
        this.sessionTemporaryChats = new Set();
        
        // Cleanup temporary chats when page is closed/refreshed
        window.addEventListener('beforeunload', () => {
            this.cleanupTemporaryChats();
        });
        
        // Also cleanup on visibility change (when tab is hidden)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.cleanupTemporaryChats();
            }
        });
    }

    async cleanupTemporaryChats() {
        // Delete temporary chats that were created/accessed in this session
        for (const chatId of this.sessionTemporaryChats) {
            try {
                await fetch(`/api/chat/chats/${chatId}`, {
                    method: 'DELETE',
                    keepalive: true // Allows request to complete even if page is unloading
                });
            } catch (error) {
                console.warn('Error cleaning up temporary chat:', chatId, error);
            }
        }
        this.sessionTemporaryChats.clear();
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
            console.log('Loading chats...');
            const response = await fetch('/api/chat/chats?include_temporary=true&limit=50');
            console.log('Chat response status:', response.status);
            const chats = await response.json();
            console.log('Loaded chats:', chats.length, chats);
            this.renderChatList(chats);
        } catch (error) {
            console.error('Error loading chats:', error);
            this.showError('Failed to load chats');
        }
    }

    renderChatList(chats) {
        console.log('Rendering chat list with:', chats);
        const chatList = document.getElementById('chatList');
        
        if (!chatList) {
            console.error('Chat list element not found!');
            return;
        }
        
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

        // Sort chats by updated_at descending (most recent first)
        const sortedChats = chats.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

        const html = sortedChats.map(chat => {
            const badges = [];
            
            // Add type badge
            badges.push(`<span class="badge ${chat.is_temporary ? 'bg-temporary' : 'bg-permanent'}">${chat.is_temporary ? 'TEMP' : 'PERM'}</span>`);
            
            // Add force provider badge if enabled
            if (chat.force_provider) {
                badges.push(`<span class="badge bg-force">FORCE</span>`);
            }

            const providerModel = chat.provider && chat.model ? 
                `${chat.provider}/${chat.model}` : 
                (chat.provider || 'auto');

            return `
                <div class="chat-item ${chat.id === this.currentChatId ? 'active' : ''}" 
                     onclick="chatInterface.selectChat(${chat.id})"
                     data-chat-id="${chat.id}"
                     data-is-temporary="${chat.is_temporary}">
                    <div class="chat-item-header">
                        <div class="chat-item-title" title="${this.escapeHtml(chat.title)}">
                            ${this.escapeHtml(chat.title)}
                        </div>
                        <div class="chat-item-badges">
                            ${badges.join('')}
                        </div>
                    </div>
                    <div class="chat-item-preview" title="${chat.last_message ? this.escapeHtml(chat.last_message) : 'No messages yet'}">
                        ${chat.last_message ? this.escapeHtml(this.truncateText(chat.last_message, 60)) : 'No messages yet'}
                    </div>
                    <div class="chat-item-meta">
                        <span class="chat-item-time">${this.formatRelativeTime(chat.updated_at)}</span>
                        <span class="chat-item-provider" title="${providerModel}">
                            ${this.truncateText(providerModel, 15)}
                        </span>
                    </div>
                </div>
            `;
        }).join('');

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
            
            // Track temporary chats for cleanup
            if (data.chat.is_temporary) {
                this.sessionTemporaryChats.add(chatId);
            }
            
            this.renderChatHeader(data.chat);
            this.renderMessages(data.messages);
            this.showChatInterface();
            
            // Load models for the chat's provider if set
            if (data.chat.provider) {
                await this.loadModelsForProvider(data.chat.provider, 'modelSelect');
                // Set the provider and model in the interface
                const providerSelect = document.getElementById('providerSelect');
                const modelSelect = document.getElementById('modelSelect');
                if (providerSelect) providerSelect.value = data.chat.provider;
                if (modelSelect && data.chat.model) modelSelect.value = data.chat.model;
            }
            
            this.connectWebSocket();

            // Update chat list selection
            document.querySelectorAll('.chat-item').forEach(item => {
                item.classList.remove('active');
            });
            const chatElement = document.querySelector(`[data-chat-id="${chatId}"]`);
            if (chatElement) {
                chatElement.classList.add('active');
            }

            // Auto-close mobile sidebar
            if (window.innerWidth <= 768) {
                const sidebar = document.querySelector('.chat-sidebar');
                sidebar.classList.remove('show');
            }

        } catch (error) {
            console.error('Error selecting chat:', error);
            this.showError('Failed to load chat');
        }
    }

    async loadCurrentChatMessages() {
        if (!this.currentChatId) return;
        try {
            const response = await fetch(`/api/chat/chats/${this.currentChatId}`);
            const data = await response.json();
            this.renderMessages(data.messages);
        } catch (error) {
            console.error('Error loading current chat messages:', error);
        }
    }

    renderChatHeader(chat) {
        document.getElementById('chatTitle').textContent = chat.title;
        document.getElementById('chatType').textContent = chat.is_temporary ? 'Temporary' : 'Permanent';
        document.getElementById('chatType').className = `badge ${chat.is_temporary ? 'bg-temporary' : 'bg-permanent'}`;
        
        // Show/hide force provider badge
        const forceProviderBadge = document.getElementById('forceProviderBadge');
        if (chat.force_provider) {
            forceProviderBadge.style.display = 'inline-block';
        } else {
            forceProviderBadge.style.display = 'none';
        }
        
        // Set provider and model
        if (chat.provider) {
            document.getElementById('providerSelect').value = chat.provider;
        }
        if (chat.model) {
            document.getElementById('modelSelect').value = chat.model;
        }

        // Populate system prompt
        const systemPromptTextarea = document.getElementById('currentSystemPrompt');
        systemPromptTextarea.value = chat.system_prompt || '';

        // Initialize chat controls as hidden (user can toggle with button)
        document.getElementById('chatControls').style.display = 'none';
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
        
        // Highlight code blocks
        this.highlightCodeBlocks();
        this.scrollToBottom();
    }

    highlightCodeBlocks() {
        // Apply syntax highlighting to code blocks
        if (typeof Prism !== 'undefined') {
            try {
                Prism.highlightAll();
            } catch (e) {
                console.warn('Prism highlighting error:', e);
            }
        }
    }

    renderMessage(message) {
        const timeStr = this.formatRelativeTime(message.created_at);
        const isUser = message.role === 'user';
        const isSystem = message.role === 'system';
        
        let messageInfo = '';
        if (isUser) {
            messageInfo = `<div class="message-timestamp">${timeStr}</div>`;
        } else if (message.role === 'assistant' && message.metadata) {
            const provider = message.metadata.provider || 'unknown';
            const model = message.metadata.model || 'unknown';
            const responseTime = message.metadata.response_time ? 
                `${message.metadata.response_time.toFixed(2)}s` : '';
            
            // Status indicators
            const indicators = [];
            if (message.metadata.error) indicators.push('❌');
            if (message.metadata.force_provider) indicators.push('🔒');
            
            messageInfo = `
                <div class="message-info">
                    <span class="message-timestamp">${timeStr}</span>
                    <span class="message-provider-info">
                        ${provider}/${model}${responseTime ? ` • ${responseTime}` : ''}${indicators.length ? ` ${indicators.join(' ')}` : ''}
                    </span>
                </div>
            `;
        }

        return `
            <div class="message ${message.role}" data-message-id="${message.id}">
                <div class="message-bubble">
                    <div class="message-content">
                        ${this.formatMessageContent(message.content)}
                    </div>
                </div>
                ${messageInfo}
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
        // Enhanced markdown support using marked.js if available, otherwise basic formatting
        if (typeof marked !== 'undefined') {
            try {
                const renderer = new marked.Renderer();
                
                // Custom code block rendering for syntax highlighting
                renderer.code = function(code, language) {
                    const validLanguage = language && Prism.languages[language] ? language : 'javascript';
                    const highlightedCode = Prism.highlight(code, Prism.languages[validLanguage], validLanguage);
                    return `<pre class="line-numbers"><code class="language-${validLanguage}">${highlightedCode}</code></pre>`;
                };
                
                return marked.parse(content, { 
                    renderer: renderer,
                    breaks: true,
                    gfm: true,
                    sanitize: false
                });
            } catch (e) {
                console.warn('Marked.js error, falling back to basic formatting:', e);
            }
        }
        
        // Basic markdown formatting fallback
        return this.escapeHtml(content)
            // Headers
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // Bold and italic
            .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code blocks with basic syntax highlighting
            .replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
                const language = lang || 'javascript';
                return `<pre class="line-numbers"><code class="language-${language}">${code}</code></pre>`;
            })
            .replace(/```([\s\S]*?)```/g, '<pre class="line-numbers"><code>$1</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            // Lists
            .replace(/^[\s]*[-*+]\s+(.*)$/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            .replace(/^[\s]*\d+\.\s+(.*)$/gm, '<li>$1</li>')
            // Blockquotes
            .replace(/^> (.*)$/gm, '<blockquote>$1</blockquote>')
            // Line breaks
            .replace(/\n/g, '<br>');
    }

    showChatInterface() {
        document.getElementById('welcomeMessage').style.display = 'none';
        document.getElementById('chatHeader').style.display = 'block';
        document.getElementById('chatControls').style.display = 'block';
        document.getElementById('messagesList').style.display = 'block';
        document.getElementById('messageInput').style.display = 'block';
    }

    hideChatInterface() {
        document.getElementById('welcomeMessage').style.display = 'block';
        document.getElementById('chatHeader').style.display = 'none';
        document.getElementById('chatControls').style.display = 'none';
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

            this.websocket.onmessage = async (event) => {
                await this.handleWebSocketMessage(JSON.parse(event.data));
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

    async handleWebSocketMessage(data) {
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
                // Update the streaming message with final metadata
                if (data.provider && data.model) {
                    this.updateStreamingMessageMetadata(data);
                }
                // Refresh both chat list and current messages
                await this.loadChats(); 
                if (this.currentChatId) {
                    await this.loadCurrentChatMessages();
                }
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

        // Check autodecide mode
        const autodecideBtn = document.getElementById('autodecideBtn');
        const isAutodecideOn = autodecideBtn.classList.contains('btn-success');
        
        let provider = null;
        let model = null;
        
        if (!isAutodecideOn) {
            // Manual mode - use selected provider/model
            provider = document.getElementById('providerSelect').value || null;
            model = document.getElementById('modelSelect').value || null;
        }
        // If autodecide is on, provider and model stay null (AI Engine will decide)

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
                metadata: { autodecide: isAutodecideOn }
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
                        metadata: { provider, model, autodecide: isAutodecideOn }
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
            // Add message actions for immediate interaction
            const messageActions = `
                <div class="message-actions">
                    <button class="btn btn-sm btn-outline-secondary" onclick="chatInterface.copyStreamingMessage()" title="Copy">
                        <i class="fas fa-copy"></i>
                    </button>
                </div>
            `;
            streamingMsg.innerHTML += messageActions;
            
            streamingMsg.removeAttribute('id');
            // Highlight any code blocks in the final response
            this.highlightCodeBlocks();
        }
        this.messageBuffer = '';
        
        // Note: Don't reload messages here, wait for ai_complete event with proper metadata
    }

    updateStreamingMessageMetadata(data) {
        const streamingMsg = document.querySelector('.message.assistant:last-child');
        if (streamingMsg && data.provider && data.model) {
            const provider = data.provider;
            const model = data.model;
            const responseTime = data.response_time ? `${data.response_time.toFixed(2)}s` : '';
            const timestamp = new Date().toISOString();
            
            // Remove any existing message info
            const existingInfo = streamingMsg.querySelector('.message-info');
            if (existingInfo) existingInfo.remove();
            
            // Add new message info with provider and model
            const messageInfo = document.createElement('div');
            messageInfo.className = 'message-info';
            messageInfo.innerHTML = `
                <span class="message-timestamp">${this.formatRelativeTime(timestamp)}</span>
                <span class="message-provider-info">
                    ${provider}/${model}${responseTime ? ` • ${responseTime}` : ''}
                </span>
            `;
            
            streamingMsg.appendChild(messageInfo);
        }
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
        const forceProvider = document.getElementById('forceProviderCheck').checked;

        if (!title) {
            alert('Please enter a chat title');
            return;
        }

        // Validate force provider setting
        if (forceProvider && !provider) {
            alert('Force Provider requires selecting a specific provider');
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
                    is_temporary: isTemporary,
                    force_provider: forceProvider
                })
            });

            const result = await response.json();
            
            if (result.success) {
                // Close modal
                bootstrap.Modal.getInstance(document.getElementById('createChatModal')).hide();
                
                // Clear form
                form.reset();
                
                // Track temporary chats for cleanup
                if (isTemporary) {
                    this.sessionTemporaryChats.add(result.chat_id);
                }
                
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

        // Add new status to bottom-right corner
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
                    statusDiv.style.opacity = '0';
                    setTimeout(() => statusDiv.remove(), 300);
                }
            }, 3000);
        }
    }

    // Enhanced time formatting - Fixed simpler version
    formatRelativeTime(dateString) {
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) {
                return 'Invalid date';
            }
            
            const now = new Date();
            const today = new Date();
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            
            // Simple time format
            const timeOptions = { 
                hour: 'numeric', 
                minute: '2-digit',
                hour12: true 
            };
            
            const timeString = date.toLocaleTimeString('en-US', timeOptions);
            
            // If today, just show time
            if (date.toDateString() === today.toDateString()) {
                return timeString;
            }
            
            // If yesterday
            if (date.toDateString() === yesterday.toDateString()) {
                return `Yesterday ${timeString}`;
            }
            
            // Otherwise show date and time
            const dateOptions = { 
                month: 'short', 
                day: 'numeric' 
            };
            
            const dateString = date.toLocaleDateString('en-US', dateOptions);
            return `${dateString}, ${timeString}`;
            
        } catch (error) {
            console.error('Error formatting time:', error);
            return 'Invalid time';
        }
    }

    // Text truncation utility
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength - 3) + '...';
    }

    copyMessage(messageId) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"] .message-bubble`);
        const text = messageElement.textContent;
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccess('Message copied to clipboard');
        });
    }

    copyStreamingMessage() {
        const streamingElement = document.querySelector('.message.assistant:last-child .message-bubble');
        if (streamingElement) {
            const text = streamingElement.textContent;
            navigator.clipboard.writeText(text).then(() => {
                this.showSuccess('Message copied to clipboard');
            });
        }
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
        // Legacy method - keeping for compatibility
        return this.formatRelativeTime(dateString);
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

    // Quick temporary chat creation - bypasses modal
    async createQuickTempChat() {
        try {
            const response = await fetch('/api/chat/chats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: 'Untitled Temporary Chat',
                    system_prompt: null,
                    provider: null,
                    model: null,
                    is_temporary: true,
                    force_provider: false
                })
            });

            const result = await response.json();
            
            if (result.success) {
                // Refresh chat list and select the new chat
                await this.loadChats();
                this.selectChat(result.chat_id);
                this.showSuccess('Quick temporary chat created!');
            } else {
                this.showError('Failed to create chat: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error creating quick temp chat:', error);
            this.showError('Failed to create chat');
        }
    }

    // Update system prompt for current chat
    async updateSystemPrompt() {
        if (!this.currentChatId) {
            this.showError('No chat selected');
            return;
        }

        const systemPrompt = document.getElementById('currentSystemPrompt').value.trim();
        
        try {
            const response = await fetch(`/api/chat/chats/${this.currentChatId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    system_prompt: systemPrompt || null
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('System prompt updated!');
            } else {
                this.showError('Failed to update system prompt: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error updating system prompt:', error);
            this.showError('Failed to update system prompt');
        }
    }

    // Clear system prompt
    clearSystemPrompt() {
        document.getElementById('currentSystemPrompt').value = '';
        this.updateSystemPrompt();
    }

    // Toggle autodecide mode
    toggleAutodecide() {
        const autodecideBtn = document.getElementById('autodecideBtn');
        const autodecideBtnText = document.getElementById('autodecideBtnText');
        const modelControls = document.getElementById('modelControls');
        
        // Check current state
        const isAutodecideOn = autodecideBtn.classList.contains('btn-success');
        
        if (isAutodecideOn) {
            // Turn OFF autodecide
            autodecideBtn.classList.remove('btn-success');
            autodecideBtn.classList.add('btn-outline-secondary');
            autodecideBtnText.textContent = 'Autodecide: OFF';
            modelControls.style.display = 'flex';
            this.showSuccess('Autodecide mode disabled - manual provider/model selection');
        } else {
            // Turn ON autodecide
            autodecideBtn.classList.remove('btn-outline-secondary');
            autodecideBtn.classList.add('btn-success');
            autodecideBtnText.textContent = 'Autodecide: ON';
            modelControls.style.display = 'none';
            this.showSuccess('Autodecide mode enabled - AI will choose optimal provider/model');
        }
    }

    // Toggle system prompt visibility
    toggleSystemPrompt() {
        const chatControls = document.getElementById('chatControls');
        const isVisible = chatControls.style.display === 'block';
        
        if (isVisible) {
            chatControls.style.display = 'none';
        } else {
            chatControls.style.display = 'block';
        }
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

function toggleSidebar() {
    const sidebar = document.querySelector('.chat-sidebar');
    sidebar.classList.toggle('show');
}

// New functions for enhanced chat features
function createQuickTempChat() {
    chatInterface.createQuickTempChat();
}

function updateSystemPrompt() {
    chatInterface.updateSystemPrompt();
}

function clearSystemPrompt() {
    chatInterface.clearSystemPrompt();
}

function toggleAutodecide() {
    chatInterface.toggleAutodecide();
}

function toggleSystemPrompt() {
    chatInterface.toggleSystemPrompt();
}

// Initialize chat interface when page loads
let chatInterface;
document.addEventListener('DOMContentLoaded', function() {
    chatInterface = new ChatInterface();
});
