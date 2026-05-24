class AudioClient {
    constructor() {
        this.socket = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectTimer = null;

        // Controls
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.connectionStatus = document.getElementById('connectionStatus');
        this.recommendBtn = document.getElementById('recommendBtn');
        this.refreshSummaryBtn = document.getElementById('refreshSummaryBtn');
        this.recommendStatus = document.getElementById('recommendStatus');
        this.vexaJoinForm = document.getElementById('vexaJoinForm');
        this.meetingUrlInput = document.getElementById('meetingUrlInput');
        this.joinMeetingBtn = document.getElementById('joinMeetingBtn');

        // Tab elements
        this.tabs = document.querySelectorAll('.tab');
        this.tabPanes = document.querySelectorAll('.tab-pane');

        // Content panels
        this.transcriptDiv = document.getElementById('transcript');
        this.summaryText = document.getElementById('summaryText');
        this.summaryStage = document.getElementById('summaryStage');
        this.summaryArchetype = document.getElementById('summaryArchetype');
        this.painIndicators = document.getElementById('painIndicators');
        this.summaryTimestamp = document.getElementById('summaryTimestamp');
        this.keyPointsList = document.getElementById('keyPointsList');
        this.recommendationContent = document.getElementById('recommendationContent');

        // State
        this.hasSummary = false;
        this.recommendationCount = 0;

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
        this.recommendBtn.addEventListener('click', () => this.requestRecommendation());
        this.refreshSummaryBtn.addEventListener('click', () => this.refreshSummary());
        this.vexaJoinForm.addEventListener('submit', (event) => this.joinMeeting(event));

        // Tab switching
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
    }

    switchTab(tabName) {
        this.tabs.forEach(t => t.classList.remove('active'));
        this.tabPanes.forEach(p => p.classList.remove('active'));

        const activeTab = document.querySelector(`.tab[data-tab="${tabName}"]`);
        const activePane = document.getElementById(`tab-${tabName}`);

        if (activeTab) activeTab.classList.add('active');
        if (activePane) activePane.classList.add('active');
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.connectWebSocket();

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            try {
                await this.audioContext.audioWorklet.addModule('/static/js/audio-processor.js?v=3');
            } catch (e) {
                console.error("Failed to load audio processor:", e);
                throw e;
            }

            const source = this.audioContext.createMediaStreamSource(stream);
            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor');

            this.workletNode.port.onmessage = (event) => {
                if (!this.isRecording || !this.socket || this.socket.readyState !== WebSocket.OPEN) return;
                this.socket.send(event.data.buffer);
            };

            source.connect(this.workletNode);

            const gainNode = this.audioContext.createGain();
            gainNode.gain.value = 0;
            this.workletNode.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

            this.isRecording = true;
            this.updateUI(true);

        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please ensure you have granted permission.");
        }
    }

    stopRecording() {
        if (this.isRecording) {
            this.isRecording = false;

            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            this.reconnectAttempts = 0;

            if (this.workletNode) {
                this.workletNode.disconnect();
                this.workletNode = null;
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }

            this.updateUI(false);

            if (this.socket) {
                this.socket.close();
            }
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/audio`;

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log("WebSocket connected");
            this.reconnectAttempts = 0;
            this.connectionStatus.textContent = "Connected";
            this.connectionStatus.classList.add('connected');
            this.transcriptDiv.innerHTML = '<p class="status-text connected-text">Connected. Listening...</p>';
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.socket.onclose = () => {
            console.log("WebSocket disconnected");
            this.connectionStatus.textContent = "Disconnected";
            this.connectionStatus.classList.remove('connected');

            if (this.isRecording && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000);
                this.connectionStatus.textContent = `Reconnecting (${this.reconnectAttempts})...`;
                this.reconnectTimer = setTimeout(() => this.connectWebSocket(), delay);
            }
        };

        this.socket.onerror = (err) => {
            console.error("WebSocket error:", err);
        };
    }

    sendCommand(command) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ command }));
        }
    }

    requestRecommendation() {
        this.recommendBtn.disabled = true;
        this.recommendStatus.textContent = "Generating...";
        this.recommendStatus.classList.add('loading');
        this.sendCommand('recommend');

        // Switch to suggestions tab
        this.switchTab('suggestions');
    }

    refreshSummary() {
        this.refreshSummaryBtn.disabled = true;
        this.refreshSummaryBtn.textContent = "Refreshing...";
        this.sendCommand('refresh_summary');
    }

    async joinMeeting(event) {
        event.preventDefault();

        const meetingUrl = this.meetingUrlInput.value.trim();
        if (!meetingUrl) {
            this.connectionStatus.textContent = "Meeting URL required";
            return;
        }

        this.joinMeetingBtn.disabled = true;
        this.connectionStatus.textContent = "Joining meeting...";

        try {
            const response = await fetch('/api/vexa/join', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ meeting_url: meetingUrl, bot_name: 'Sales RPG AI' }),
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Unable to join meeting');
            }

            this.connectionStatus.textContent = `Vexa joined ${data.meeting_id || 'meeting'}`;
            this.connectionStatus.classList.add('connected');
            this.refreshSummaryBtn.disabled = false;
            this.connectMonitorWebSocket();
        } catch (error) {
            console.error("Vexa join error:", error);
            this.connectionStatus.textContent = error.message;
            this.connectionStatus.classList.remove('connected');
        } finally {
            this.joinMeetingBtn.disabled = false;
        }
    }

    connectMonitorWebSocket() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN && !this.isRecording) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/audio?role=monitor`;
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            this.reconnectAttempts = 0;
            this.connectionStatus.textContent = "Connected";
            this.connectionStatus.classList.add('connected');
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.socket.onclose = () => {
            if (!this.isRecording) {
                this.connectionStatus.textContent = "Disconnected";
                this.connectionStatus.classList.remove('connected');

                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000);
                    this.connectionStatus.textContent = `Reconnecting (${this.reconnectAttempts})...`;
                    this.reconnectTimer = setTimeout(() => this.connectMonitorWebSocket(), delay);
                }
            }
        };

        this.socket.onerror = (err) => {
            console.error("Monitor WebSocket error:", err);
        };
    }

    // ── Message Handlers ──────────────────────────────────────────

    handleMessage(data) {
        switch (data.type) {
            case 'transcript':
                this.handleTranscript(data);
                break;
            case 'summary':
                this.handleSummary(data);
                break;
            case 'recommendation':
                this.handleRecommendation(data);
                break;
            case 'analysis':
                // Legacy analysis — show as suggestion
                this.handleAnalysis(data);
                break;
            case 'error':
                console.error("Server Error:", data.error || data.message);
                break;
        }
    }

    handleTranscript(data) {
        const segmentId = `segment-${Math.round(data.start * 10)}`;
        let p = document.getElementById(segmentId);

        if (!p) {
            // Remove placeholder
            const placeholder = this.transcriptDiv.querySelector('.placeholder-text, .status-text');
            if (placeholder) placeholder.remove();

            p = document.createElement('div');
            p.id = segmentId;
            p.classList.add('transcript-line');
            this.transcriptDiv.appendChild(p);
        }

        p.textContent = data.text;

        if (data.is_final || /[.!?]$/.test(data.text)) {
            p.classList.add('final');
        }

        this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
    }

    handleSummary(data) {
        if (data.error) {
            console.error("Summary error:", data.error);
            this.refreshSummaryBtn.disabled = false;
            this.refreshSummaryBtn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refresh Summary';
            return;
        }

        this.hasSummary = true;
        this.recommendBtn.disabled = false;

        // Update summary text
        this.summaryText.innerHTML = `<p>${this.escapeHtml(data.summary)}</p>`;

        // Update stage and archetype badges
        if (data.stage_hint && data.stage_hint !== 'unknown') {
            this.summaryStage.textContent = `Stage: ${data.stage_hint}`;
            this.summaryStage.className = `summary-badge stage-${data.stage_hint}`;
        }
        if (data.archetype_hint && data.archetype_hint !== 'unknown') {
            this.summaryArchetype.textContent = `Archetype: ${data.archetype_hint.replace('_', ' ')}`;
            this.summaryArchetype.className = `summary-badge archetype-${data.archetype_hint}`;
        }

        // Update key points (shared between summary and key points tab)
        if (data.key_points && data.key_points.length > 0) {
            this.keyPointsList.innerHTML = data.key_points
                .map(p => `<li>${this.escapeHtml(p)}</li>`)
                .join('');
        }

        // Update pain indicators
        if (data.pain_indicators && data.pain_indicators.length > 0) {
            this.painIndicators.innerHTML = '<h3>Pain Indicators</h3>' +
                data.pain_indicators
                    .map(p => `<span class="pain-tag">"${this.escapeHtml(p)}"</span>`)
                    .join('');
        }

        // Update timestamp
        const now = new Date();
        this.summaryTimestamp.textContent = `Last updated: ${now.toLocaleTimeString()}`;
        if (data.latency) {
            this.summaryTimestamp.textContent += ` (${Math.round(data.latency)}ms)`;
        }

        // Re-enable refresh button
        this.refreshSummaryBtn.disabled = false;
        this.refreshSummaryBtn.innerHTML = '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Refresh Summary';

        // Flash the Summary tab if not currently active
        const summaryTab = document.querySelector('.tab[data-tab="summary"]');
        if (summaryTab && !summaryTab.classList.contains('active')) {
            summaryTab.classList.add('tab-updated');
            setTimeout(() => summaryTab.classList.remove('tab-updated'), 3000);
        }

        // Also flash the Key Points tab
        const kpTab = document.querySelector('.tab[data-tab="keypoints"]');
        if (kpTab && !kpTab.classList.contains('active')) {
            kpTab.classList.add('tab-updated');
            setTimeout(() => kpTab.classList.remove('tab-updated'), 3000);
        }
    }

    handleRecommendation(data) {
        this.recommendBtn.disabled = false;
        this.recommendStatus.textContent = "";
        this.recommendStatus.classList.remove('loading');

        if (data.error) {
            this.recommendationContent.innerHTML = `
                <div class="recommendation-error">
                    <p>${this.escapeHtml(data.error)}</p>
                </div>`;
            return;
        }

        this.recommendationCount++;

        const stageLabel = data.stage ? data.stage.charAt(0).toUpperCase() + data.stage.slice(1) : 'Unknown';
        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        let questionsHtml = '';
        if (data.questions && data.questions.length > 0) {
            questionsHtml = data.questions.map((q, i) => `
                <div class="question-card">
                    <span class="question-number">${i + 1}</span>
                    <span class="question-text">${this.escapeHtml(q)}</span>
                </div>
            `).join('');
        }

        const entry = document.createElement('div');
        entry.classList.add('recommendation-entry');
        entry.innerHTML = `
            <div class="recommendation-header">
                <span class="recommendation-stage stage-${data.stage || 'unknown'}">${stageLabel}</span>
                <span class="recommendation-meta">#${this.recommendationCount} &middot; ${timeStr}</span>
            </div>
            <div class="recommendation-questions">${questionsHtml}</div>
            ${data.reasoning ? `<div class="recommendation-reasoning">${this.escapeHtml(data.reasoning)}</div>` : ''}
        `;

        // Prepend (most recent first)
        this.recommendationContent.prepend(entry);

        // Remove placeholder if present
        const placeholder = this.recommendationContent.querySelector('.placeholder-text');
        if (placeholder) placeholder.remove();

        // Flash the suggestions tab
        const sugTab = document.querySelector('.tab[data-tab="suggestions"]');
        if (sugTab && !sugTab.classList.contains('active')) {
            sugTab.classList.add('tab-updated');
            setTimeout(() => sugTab.classList.remove('tab-updated'), 3000);
        }
    }

    handleAnalysis(data) {
        // Legacy: constant analysis results (script_location, key_points, suggestion)
        // Display as a recommendation-like entry
        if (data.key_points && data.key_points.length > 0) {
            this.keyPointsList.innerHTML = data.key_points
                .map(p => `<li>${this.escapeHtml(p)}</li>`)
                .join('');
        }
    }

    // ── Utilities ─────────────────────────────────────────────────

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    updateUI(isRecording) {
        if (isRecording) {
            this.startBtn.classList.add('hidden');
            this.stopBtn.classList.remove('hidden');
            this.refreshSummaryBtn.disabled = false;
        } else {
            this.startBtn.classList.remove('hidden');
            this.stopBtn.classList.add('hidden');
            this.recommendBtn.disabled = true;
            this.refreshSummaryBtn.disabled = true;
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new AudioClient();
});
