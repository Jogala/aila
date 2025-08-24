// AILA - AI Legal Assistant JavaScript

// Use configuration from config.js
const API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8000';
// Request timeout for analysis calls (defaults to 120s if not configured)
const REQUEST_TIMEOUT_MS = window.APP_CONFIG?.REQUEST_TIMEOUT_MS ?? 120000;
let serverConnected = false;
let serverApiKeysStatus = null;

// Check server status
async function checkServerStatus() {
    const statusIndicator = document.getElementById('statusIndicator');
    const serverStatus = document.getElementById('serverStatus');
    const serverGuide = document.getElementById('serverGuide');
    const sections = document.querySelector('.sections');

    statusIndicator.className = 'status-indicator checking';
    serverStatus.textContent = 'Checking server...';

    try {
        // Try to reach the health endpoint or root endpoint
        const response = await fetch(`${API_BASE_URL}/api/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000) // 5 second timeout
        });

        if (response.ok) {
            statusIndicator.className = 'status-indicator connected';
            serverStatus.textContent = 'Server connected ✓';
            serverGuide.style.display = 'none';
            sections.style.display = 'grid';
            serverConnected = true;
            
            // Check API keys status
            await checkApiKeysStatus();

            // Populate model list for current provider once connected
            try {
                const provider = document.getElementById('llmProvider')?.value;
                if (provider) {
                    await updateModelsForProvider(provider);
                }
            } catch (e) {
                console.warn('Failed to load models after server connect:', e);
            }
        } else {
            throw new Error(`Server responded with ${response.status}`);
        }
    } catch (error) {
        statusIndicator.className = 'status-indicator';
        serverStatus.textContent = 'Server not available ✗';
        serverGuide.style.display = 'block';
        sections.style.display = 'none';
        serverConnected = false;

        // Update guide with specific error if helpful
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            serverGuide.querySelector('p').textContent =
                'Cannot connect to the FastAPI server. Please make sure it is running and accessible.';
        } else if (error.message.includes('timeout')) {
            serverGuide.querySelector('p').textContent =
                'Server connection timed out. The server might be starting up or overloaded.';
        }
    }
}

// Check API keys status
async function checkApiKeysStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/api-keys-status`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            const hasServerKeys = await response.json();
            console.log('Server has API keys:', hasServerKeys);
            
            // Show/hide API keys panels based on server capability
            toggleApiKeysPanels(!hasServerKeys); // Invert: if server has keys, don't require user keys
            
            // Store for compatibility
            serverApiKeysStatus = { 
                has_openai_key: hasServerKeys, 
                has_anthropic_key: hasServerKeys, 
                requires_user_keys: !hasServerKeys 
            };
        }
    } catch (error) {
        console.warn('Failed to check API keys status:', error);
        // Assume user keys are required if we can't check
        toggleApiKeysPanels(true);
    }
}

// Show or hide the API keys panels
function toggleApiKeysPanels(requiresUserKeys) {
    const userKeysPanel = document.getElementById('userApiKeysPanel');
    const serverKeysPanel = document.getElementById('serverApiKeysPanel');
    
    // Always show the user keys panel
    if (userKeysPanel) userKeysPanel.style.display = 'block';
    
    if (requiresUserKeys) {
        // Hide server keys panel when user keys are required
        if (serverKeysPanel) serverKeysPanel.style.display = 'none';
        
        // Update user panel messaging for required keys
        updateUserKeysMessage(true);
    } else {
        // Show server keys panel when server keys are available
        if (serverKeysPanel) serverKeysPanel.style.display = 'block';
        
        // Update server key details
        updateServerKeyDetails();
        
        // Update user panel messaging for optional keys
        updateUserKeysMessage(false);
    }
    
    // Update button states after panel visibility changes
    updateAnalyzeButtonStates();
}

// Update user keys panel messaging
function updateUserKeysMessage(required) {
    const userKeysPanel = document.getElementById('userApiKeysPanel');
    if (!userKeysPanel) return;
    
    const userPanelTitle = userKeysPanel.querySelector('.section-title');
    const userPanelInfo = userKeysPanel.querySelector('.api-keys-info');
    
    if (required) {
        // Server keys not available - user keys required
        if (userPanelTitle) {
            userPanelTitle.textContent = '🔑 API Keys Required';
        }
        if (userPanelInfo) {
            userPanelInfo.innerHTML = `
                <p><strong>⚠️ Server API Keys Not Configured</strong></p>
                <p>This server doesn't have API keys configured. Please provide your own API keys to use the analysis features.</p>
                <p><small><strong>Privacy:</strong> Your API keys are sent securely with each request and are never stored on the server.</small></p>
            `;
        }
    } else {
        // Server keys available - user keys optional
        if (userPanelTitle) {
            userPanelTitle.textContent = '🔑 API Keys (Optional Override)';
        }
        if (userPanelInfo) {
            userPanelInfo.innerHTML = `
                <p><strong>🎛️ Override Server API Keys (Optional)</strong></p>
                <p>Leave empty to use server API keys, or provide your own to override the server configuration.</p>
                <p><small><strong>Privacy:</strong> Your API keys (if provided) are sent securely with each request and are never stored on the server.</small></p>
            `;
        }
    }
}

// Update server key details display
function updateServerKeyDetails() {
    const serverKeyDetails = document.getElementById('serverKeyDetails');
    const serverKeysPanel = document.getElementById('serverApiKeysPanel');
    if (!serverKeyDetails || !serverApiKeysStatus) return;
    
    const availableKeys = [];
    if (serverApiKeysStatus.has_openai_key) availableKeys.push('OpenAI');
    if (serverApiKeysStatus.has_anthropic_key) availableKeys.push('Anthropic');
    
    if (availableKeys.length > 0) {
        // Update the server panel title and description when user field is also shown
        const serverPanelTitle = serverKeysPanel.querySelector('.section-title');
        const serverPanelInfo = serverKeysPanel.querySelector('.api-keys-info p');
        
        if (serverPanelTitle) {
            serverPanelTitle.textContent = '🔐 Server API Keys Available (Optional Override Below)';
        }
        
        if (serverPanelInfo) {
            serverPanelInfo.innerHTML = '<strong>✨ You can use server keys or provide your own</strong>';
        }
        
        serverKeyDetails.innerHTML = `
            <p><small>
                <strong>Available server providers:</strong> ${availableKeys.join(', ')}<br>
                <strong>Priority:</strong> Your API key (if provided) takes precedence over server keys<br>
                <strong>Status:</strong> Ready for analysis
            </small></p>
        `;
    }
}

// Copy to clipboard function
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Could add a toast notification here
        console.log('Copied to clipboard:', text);
    });
}

// Update the config display and check server
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('apiEndpoint').textContent = API_BASE_URL;

    // Also update form defaults from config if available
    if (window.APP_CONFIG) {
        const defaultModel = window.APP_CONFIG.DEFAULT_MODEL;
        const defaultTemp = window.APP_CONFIG.DEFAULT_TEMPERATURE;

        if (defaultModel) {
            document.getElementById('llmModel').value = defaultModel;
        }

        if (defaultTemp !== undefined) {
            document.getElementById('llmTemperature').value = defaultTemp;
        }
    }

    // Check server status on page load
    checkServerStatus();

    // When provider changes, update available models
    const providerSelect = document.getElementById('llmProvider');
    if (providerSelect) {
        providerSelect.addEventListener('change', async (e) => {
            const provider = e.target.value;
            try {
                await updateModelsForProvider(provider);
            } catch (err) {
                console.warn('Failed to update models for provider change:', err);
            }
        });
    }

    // Add event listener to user API key input to update button states
    const userApiKeyInput = document.getElementById('userApiKey');
    if (userApiKeyInput) {
        userApiKeyInput.addEventListener('input', updateAnalyzeButtonStates);
        userApiKeyInput.addEventListener('paste', () => {
            // Use setTimeout to ensure the pasted value is processed
            setTimeout(updateAnalyzeButtonStates, 10);
        });
    }
});

// Fetch and update model options for a provider
async function updateModelsForProvider(provider) {
    const modelSelect = document.getElementById('llmModel');
    if (!modelSelect) return;

    // Show loading state
    modelSelect.disabled = true;
    modelSelect.innerHTML = '<option disabled selected>Loading models...</option>';

    // Build request (use GET with query param)
    const url = new URL(`${API_BASE_URL}/api/models`);
    url.searchParams.set('provider_name', provider);

    const response = await makeApiCall(url.toString());

    const models = await response.json();

    // Populate options
    modelSelect.innerHTML = '';
    if (Array.isArray(models) && models.length > 0) {
        for (const m of models) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            modelSelect.appendChild(opt);
        }

        // Try to keep/choose a sensible default
        const desired = (window.APP_CONFIG && window.APP_CONFIG.DEFAULT_MODEL) || '';
        if (desired && models.includes(desired)) {
            modelSelect.value = desired;
        } else {
            modelSelect.selectedIndex = 0;
        }
    } else {
        const opt = document.createElement('option');
        opt.disabled = true;
        opt.selected = true;
        opt.textContent = 'No models available';
        modelSelect.appendChild(opt);
    }

    modelSelect.disabled = false;
}

// Enhanced error handling for API calls
async function makeApiCall(url, options = {}) {
    if (!serverConnected) {
        throw new Error('Server not connected. Please start the FastAPI server first.');
    }

    try {
        const response = await fetch(url, {
            ...options,
            // Allow longer-running analyses (configurable via APP_CONFIG)
            signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
        });

        if (!response.ok) {
            if (response.status === 0 || response.status >= 500) {
                // Server might have gone down
                serverConnected = false;
                checkServerStatus();
            }
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
    } catch (error) {
        if (error.name === 'TypeError' && error.message.includes('fetch')) {
            serverConnected = false;
            checkServerStatus();
            throw new Error('Lost connection to server. Please check if the FastAPI server is still running.');
        }
        throw error;
    }
}

// Validate API key provider matches LLM provider
function validateApiKeyProvider() {
    const userKeysPanel = document.getElementById('userApiKeysPanel');
    if (!userKeysPanel || userKeysPanel.style.display === 'none') {
        return true; // No validation needed if user keys panel is hidden
    }

    const llmProvider = document.getElementById('llmProvider').value;
    const userApiKeyProvider = document.getElementById('userApiKeyProvider').value;
    
    if (llmProvider !== userApiKeyProvider) {
        throw new Error(`API key provider (${userApiKeyProvider}) must match LLM provider (${llmProvider})`);
    }
    
    const userApiKey = document.getElementById('userApiKey').value;
    if (!userApiKey || userApiKey.trim() === '') {
        throw new Error('API key is required when server keys are not configured');
    }
    
    return true;
}

// Validate that analysis can proceed (combines both API key and button state validation)
function validateCanProceedWithAnalysis() {
    if (!canProceedWithAnalysis()) {
        throw new Error('API key is required when server keys are not configured');
    }
    
    // Only check provider match if user actually provided an API key
    const userApiKey = document.getElementById('userApiKey').value.trim();
    if (userApiKey.length > 0) {
        const llmProvider = document.getElementById('llmProvider').value;
        const userApiKeyProvider = document.getElementById('userApiKeyProvider').value;
        
        if (llmProvider !== userApiKeyProvider) {
            throw new Error(`API key provider (${userApiKeyProvider}) must match LLM provider (${llmProvider})`);
        }
    }
    
    return true;
}

// Get user API key if provided
function getUserApiKey() {
    const userApiKey = document.getElementById('userApiKey').value.trim();
    return userApiKey.length > 0 ? userApiKey : null;
}

// Check if analysis can proceed (either server keys available or user provided valid API key)
function canProceedWithAnalysis() {
    const userApiKey = document.getElementById('userApiKey').value.trim();
    const serverKeysPanel = document.getElementById('serverApiKeysPanel');
    
    // If user provided a key, we can proceed
    if (userApiKey.length > 0) {
        return true;
    }
    
    // If no user key, check if server keys are available
    const hasServerKeys = serverKeysPanel && serverKeysPanel.style.display !== 'none';
    return hasServerKeys;
}

// Update button states based on API key availability
function updateAnalyzeButtonStates() {
    const fileAnalyzeBtn = document.querySelector('#fileAnalysisForm button[type="submit"]');
    const textAnalyzeBtn = document.querySelector('#textAnalysisForm button[type="submit"]');
    const canProceed = canProceedWithAnalysis();
    
    if (fileAnalyzeBtn) {
        fileAnalyzeBtn.disabled = !canProceed;
        fileAnalyzeBtn.style.opacity = canProceed ? '1' : '0.5';
        fileAnalyzeBtn.style.cursor = canProceed ? 'pointer' : 'not-allowed';
    }
    
    if (textAnalyzeBtn) {
        textAnalyzeBtn.disabled = !canProceed;
        textAnalyzeBtn.style.opacity = canProceed ? '1' : '0.5';
        textAnalyzeBtn.style.cursor = canProceed ? 'pointer' : 'not-allowed';
    }
}

// Handle file upload form
document.getElementById('fileAnalysisForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const loading = document.getElementById('fileLoading');
    const error = document.getElementById('fileError');
    const submitBtn = e.target.querySelector('button[type="submit"]');

    // Show loading state
    loading.classList.add('show');
    error.classList.remove('show');
    submitBtn.disabled = true;

    try {
        // Validate that analysis can proceed
        validateCanProceedWithAnalysis();
        
        // Clear any previous text analysis data
        window.lastAnalyzedTexts = null;

        // Get LLM settings from the shared panel
        const llmProvider = document.getElementById('llmProvider').value;
        const llmModel = document.getElementById('llmModel').value;
        const llmTemperature = document.getElementById('llmTemperature').value;
        const llmPromptTemplate = document.getElementById('llmPromptTemplate').value;
        const userApiKey = getUserApiKey();

        // Create URL with query parameters for non-file data
        const url = new URL(`${API_BASE_URL}/api/analyze`);
        url.searchParams.append('provider_name', llmProvider);
        url.searchParams.append('model', llmModel);
        url.searchParams.append('temperature', llmTemperature);
        url.searchParams.append('prompt_template', llmPromptTemplate);
        // Always send api_key parameter (empty string if using server keys)
        url.searchParams.append('api_key', userApiKey || '');

        // Create form data for files only
        const apiFormData = new FormData();
        apiFormData.append('document1', formData.get('document1'));
        apiFormData.append('document2', formData.get('document2'));

        const response = await makeApiCall(url.toString(), {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        // Store the document texts from the API response for highlighting
        if (result.document1_text && result.document2_text) {
            window.lastAnalyzedTexts = {
                doc1_text: result.document1_text,
                doc2_text: result.document2_text
            };
        }

        displayResults(result);

    } catch (err) {
        error.textContent = `Error: ${err.message}`;
        error.classList.add('show');
    } finally {
        loading.classList.remove('show');
        submitBtn.disabled = false;
    }
});

// Handle text analysis form
document.getElementById('textAnalysisForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(e.target);
    const loading = document.getElementById('textLoading');
    const error = document.getElementById('textError');
    const submitBtn = e.target.querySelector('button[type="submit"]');

    // Show loading state
    loading.classList.add('show');
    error.classList.remove('show');
    submitBtn.disabled = true;

    try {
        // Validate that analysis can proceed
        validateCanProceedWithAnalysis();
        
        // Get LLM settings from the shared panel
        const llmProvider = document.getElementById('llmProvider').value;
        const llmModel = document.getElementById('llmModel').value;
        const llmTemperature = parseFloat(document.getElementById('llmTemperature').value);
        const llmPromptTemplate = document.getElementById('llmPromptTemplate').value;
        const userApiKey = getUserApiKey();

        const requestBody = {
            doc1_text: formData.get('doc1_text'),
            doc2_text: formData.get('doc2_text'),
            name_doc1: formData.get('name_doc1'),
            name_doc2: formData.get('name_doc2'),
            llm_config: {
                provider_name: llmProvider,
                model: llmModel,
                temperature: llmTemperature,
                api_key: userApiKey || '' // Use user key or empty string for server key
            },
            prompt_template: llmPromptTemplate
        };

        // Store the original texts for document comparison
        window.lastAnalyzedTexts = {
            doc1_text: requestBody.doc1_text,
            doc2_text: requestBody.doc2_text
        };

        const response = await makeApiCall(`${API_BASE_URL}/api/analyze-texts`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const result = await response.json();
        displayResults(result);

    } catch (err) {
        error.textContent = `Error: ${err.message}`;
        error.classList.add('show');
    } finally {
        loading.classList.remove('show');
        submitBtn.disabled = false;
    }
});

function displayResults(result) {
    const resultsDiv = document.getElementById('results');
    const contentDiv = document.getElementById('resultsContent');
    const exportBtn = document.getElementById('exportResultsBtn');

    // Store complete results for export
    window.lastResults = result;

    // Show export button
    exportBtn.style.display = 'flex';

    // Set up export functionality
    exportBtn.onclick = () => {
        try {
            // Create a copy of results without document texts
            const exportData = { ...result };
            delete exportData.document1_text;
            delete exportData.document2_text;

            // Create filename with timestamp
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
            const doc1Name = result.document1_name?.replace(/\.[^/.]+$/, '') || 'doc1';
            const doc2Name = result.document2_name?.replace(/\.[^/.]+$/, '') || 'doc2';
            const filename = `analysis_${doc1Name}_vs_${doc2Name}_${timestamp}.json`;

            // Download the file
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            // Show success feedback
            const originalText = exportBtn.innerHTML;
            exportBtn.innerHTML = '✅ Downloaded!';
            exportBtn.style.background = '#38a169';
            setTimeout(() => {
                exportBtn.innerHTML = originalText;
                exportBtn.style.background = 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)';
            }, 2000);

        } catch (error) {
            console.error('Export failed:', error);
            alert('Failed to export results. Please try again.');
        }
    };

    // Create summary section
    const summaryHTML = `
        <div class="summary-grid">
            <div class="summary-card">
                <h3>${result.summary.critical_changes}</h3>
                <p>Critical Changes</p>
            </div>
            <div class="summary-card">
                <h3>${result.summary.minor_changes}</h3>
                <p>Minor Changes</p>
            </div>
            <div class="summary-card">
                <h3>${result.summary.formatting_changes}</h3>
                <p>Formatting Changes</p>
            </div>
        </div>
        
        <div style="margin-bottom: 2rem;">
            <h3 style="margin-bottom: 1rem;">Analysis Summary</h3>
            <p style="background: #f7fafc; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <strong>Most Affected Party:</strong> ${result.summary.most_affected_party}
            </p>
            <p style="background: #f7fafc; padding: 1rem; border-radius: 8px;">
                <strong>Overall Assessment:</strong> ${result.summary.overall_assessment}
            </p>
        </div>
    `;

    // Create changes section
    const changesHTML = result.changes.map(change => `
        <div class="change-item ${change.change_type.toLowerCase()}">
            <div class="change-header">
                <span class="change-type ${change.change_type.toLowerCase()}">${change.change_type}</span>
                <span class="confidence-score">Confidence: ${(change.confidence_score * 100).toFixed(1)}%</span>
            </div>
            
            <div class="change-details">
                <div>
                    <h4 style="margin-bottom: 0.5rem;">Description</h4>
                    <p style="margin-bottom: 1rem;">${change.description}</p>
                </div>
                
                ${change.old_text && change.new_text ? `
                <div class="change-text">
                    <div>
                        <h5 style="margin-bottom: 0.5rem;">Old Text</h5>
                        <div class="text-block old-text">${change.old_text}</div>
                    </div>
                    <div>
                        <h5 style="margin-bottom: 0.5rem;">New Text</h5>
                        <div class="text-block new-text">${change.new_text}</div>
                    </div>
                </div>
                ` : ''}
                
                ${change.section ? `
                <div>
                    <strong>Section:</strong> ${change.section}
                </div>
                ` : ''}
                
                ${change.legal_implications ? `
                <div>
                    <strong>Legal Implications:</strong> ${change.legal_implications}
                </div>
                ` : ''}
                
                ${change.affected_parties && change.affected_parties.length > 0 ? `
                <div>
                    <strong>Affected Parties:</strong> ${change.affected_parties.join(', ')}
                </div>
                ` : ''}
            </div>
        </div>
    `).join('');

    contentDiv.innerHTML = summaryHTML + `
        <h3 style="margin-bottom: 1rem;">Detailed Changes</h3>
        ${changesHTML}
        
        <div id="documentComparison" style="margin-top: 3rem;">
            <h3 style="margin-bottom: 1rem;">📄 Full Document Comparison</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-bottom: 2rem;">
                <div>
                    <h4 style="margin-bottom: 1rem; color: #4a5568;">${result.document1_name}</h4>
                    <div id="doc1FullText" style="background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.5rem; font-family: monospace; font-size: 0.875rem; line-height: 1.6; white-space: pre-wrap; max-height: 500px; overflow-y: auto;"></div>
                </div>
                <div>
                    <h4 style="margin-bottom: 1rem; color: #4a5568;">${result.document2_name}</h4>
                    <div id="doc2FullText" style="background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.5rem; font-family: monospace; font-size: 0.875rem; line-height: 1.6; white-space: pre-wrap; max-height: 500px; overflow-y: auto;"></div>
                </div>
            </div>
        </div>
        
        <div style="margin-top: 2rem; padding: 1rem; background: #f7fafc; border-radius: 8px;">
            <small style="color: #4a5568;">
                <strong>Analysis completed:</strong> ${result.analysis_timestamp}<br>
                <strong>Documents:</strong> ${result.document1_name} vs ${result.document2_name}<br>
                <strong>LLM:</strong> ${result.llm_config.provider_name} - ${result.llm_config.model}
            </small>
        </div>
    `;

    // Populate the full document texts with highlighted changes
    populateDocumentComparison(result);

    resultsDiv.classList.add('show');
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function populateDocumentComparison(result) {
    const doc1Container = document.getElementById('doc1FullText');
    const doc2Container = document.getElementById('doc2FullText');

    if (window.lastAnalyzedTexts) {
        // We have the document texts - show them with highlighted changes
        const { doc1_text, doc2_text } = window.lastAnalyzedTexts;

        doc1Container.innerHTML = highlightChangesInText(doc1_text, result.changes, 'old');
        doc2Container.innerHTML = highlightChangesInText(doc2_text, result.changes, 'new');
    } else {
        // No texts available
        doc1Container.innerHTML = `<div style="color: #666; font-style: italic; text-align: center; padding: 2rem;">
            📄 Document text not available<br>
            <small>(This shouldn't happen - check API response)</small>
        </div>`;
        doc2Container.innerHTML = `<div style="color: #666; font-style: italic; text-align: center; padding: 2rem;">
            📄 Document text not available<br>
            <small>(This shouldn't happen - check API response)</small>
        </div>`;
    }
}

function highlightChangesInText(text, changes, type) {
    let highlightedText = text;

    // Sort changes by position (if we had position info) or by length (longest first)
    const sortedChanges = changes
        .filter(change => change.old_text && change.new_text)
        .sort((a, b) => (b.old_text?.length || 0) - (a.old_text?.length || 0));

    for (const change of sortedChanges) {
        const searchText = type === 'old' ? change.old_text : change.new_text;
        const changeClass = change.change_type.toLowerCase();

        if (searchText && highlightedText.includes(searchText)) {
            const highlightColor = changeClass === 'critical' ? '#fed7d7' :
                changeClass === 'minor' ? '#faf089' : '#e6fffa';
            const borderColor = changeClass === 'critical' ? '#fc8181' :
                changeClass === 'minor' ? '#f6e05e' : '#81e6d9';

            highlightedText = highlightedText.replace(
                searchText,
                `<span style="background: ${highlightColor}; border: 1px solid ${borderColor}; padding: 2px 4px; border-radius: 3px; font-weight: 600;">${searchText}</span>`
            );
        }
    }

    return highlightedText;
}
