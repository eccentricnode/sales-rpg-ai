class AudioClient {
    constructor() {
        this.socket = null;
        this.mediaRecorder = null;
        this.isRecording = false;
        
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.transcriptDiv = document.getElementById('transcript');
        this.objectionsDiv = document.getElementById('objections');

        this.setupEventListeners();
    }

    setupEventListeners() {
        this.startBtn.addEventListener('click', () => this.startRecording());
        this.stopBtn.addEventListener('click', () => this.stopRecording());
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.connectWebSocket();
            
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Load the AudioWorklet processor
            try {
                await this.audioContext.audioWorklet.addModule('/static/js/audio-processor.js');
            } catch (e) {
                console.error("Failed to load audio processor:", e);
                throw e;
            }
            
            const source = this.audioContext.createMediaStreamSource(stream);
            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor');
            
            // Handle messages from the processor (audio data)
            this.workletNode.port.onmessage = (event) => {
                if (!this.isRecording || !this.socket || this.socket.readyState !== WebSocket.OPEN) return;
                
                const float32Data = event.data;
                this.socket.send(float32Data.buffer);
            };
            
            source.connect(this.workletNode);
            
            // Connect to destination via a muted gain node to keep the graph alive
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
            if (this.workletNode) {
                this.workletNode.disconnect();
                this.workletNode = null;
            }
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
            }
            
            this.isRecording = false;
            this.updateUI(false);
            this.transcriptDiv.innerHTML += '<p style="color: var(--status-price); font-style: italic; margin-top: 0.5rem;">Stopped listening.</p>';
            
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
            this.transcriptDiv.innerHTML = '<p style="color: var(--status-success); font-style: italic;">Connected! Listening...</p>';
        };
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received:", data);
            
            if (data.type === 'transcript') {
                this.handleTranscript(data);
            } else if (data.type === 'objection') {
                this.handleObjection(data);
            } else if (data.type === 'error') {
                this.handleError(data);
            }
        };
        
        this.socket.onclose = () => {
            console.log("WebSocket disconnected");
        };
    }

    handleTranscript(data) {
        // Use start time as a unique ID for the segment
        // We round to 1 decimal place to avoid floating point issues
        const segmentId = `segment-${Math.round(data.start * 10)}`;
        let p = document.getElementById(segmentId);

        if (!p) {
            p = document.createElement('div');
            p.id = segmentId;
            p.classList.add('transcript-line');
            this.transcriptDiv.appendChild(p);
        }

        p.textContent = data.text;

        // If it looks like a complete sentence, darken it
        // We don't rely solely on is_final because it can be flaky
        if (data.is_final || /[.!?]$/.test(data.text)) {
            p.style.color = 'var(--text-primary)';
        }
        
        this.transcriptDiv.scrollTop = this.transcriptDiv.scrollHeight;
    }

    handleObjection(data) {
        const div = document.createElement('div');
        div.className = 'suggestion-card objection-panel';
        div.innerHTML = `
            <div style="margin-bottom: 0.5rem;">
                <span class="objection-badge objection-price">Objection Detected</span>
            </div>
            <p style="font-style: italic; color: var(--text-secondary); margin-bottom: 0.5rem;">"${data.text}"</p>
            <div style="border-top: 1px solid var(--bg-highlight); padding-top: 0.5rem; margin-top: 0.5rem;">
                <p style="font-weight: 600; font-size: 0.875rem; color: var(--accent-primary); margin-bottom: 0.25rem;">Suggested Response:</p>
                <p style="color: var(--text-primary);">${data.response}</p>
            </div>
        `;
        this.objectionsDiv.prepend(div);
    }

    handleError(data) {
        const div = document.createElement('div');
        div.className = 'suggestion-card objection-panel';
        div.style.borderColor = 'var(--status-price)';
        div.innerHTML = `
            <div style="margin-bottom: 0.5rem;">
                <span class="objection-badge" style="background: rgba(191, 97, 106, 0.2); color: var(--status-price); border: 1px solid var(--status-price);">System Error</span>
            </div>
            <p style="color: var(--text-secondary); margin-bottom: 0.5rem;">An error occurred during analysis:</p>
            <div style="background: rgba(0,0,0,0.2); padding: 0.5rem; border-radius: 4px; font-family: monospace; font-size: 0.8rem; color: var(--status-price);">
                ${data.error || "Unknown error"}
            </div>
        `;
        this.objectionsDiv.prepend(div);
    }

    updateUI(isRecording) {
        if (isRecording) {
            this.startBtn.classList.add('hidden');
            this.stopBtn.classList.remove('hidden');
        } else {
            this.startBtn.classList.remove('hidden');
            this.stopBtn.classList.add('hidden');
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new AudioClient();
});
