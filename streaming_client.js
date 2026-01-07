/**
 * Real-Time Voice Assistant Client
 * Optimized for <1 second latency
 * 
 * Features:
 * - 20-40ms audio chunking
 * - WebSocket streaming
 * - Real-time audio playback
 * - Barge-in support
 */

class StreamingVoiceClient {
    constructor() {
        this.ws = null;
        this.audioContext = null;
        this.mediaStream = null;
        this.audioWorkletNode = null;
        this.isRecording = false;
        this.isSpeaking = false;
        this.totalChunksSent = 0;

        this.audioQueue = [];
        this.isPlaying = false;
        this.nextPlaybackTime = 0;
        this.leftoverBytes = null; // Buffer for odd-byte chunks

        // DEBUG MODE: Set to true to send ALL audio regardless of RMS
        this.DEBUG_MODE = true;  // ENABLED - sending all audio to fix transcription

        if (this.DEBUG_MODE) {
            console.log("🔧 DEBUG_MODE: ENABLED - Sending ALL audio");
        }

        // Metrics
        this.metrics = {
            audioSentAt: 0,
            sttReceivedAt: 0,
            llmReceivedAt: 0,
            ttsReceivedAt: 0
        };

        // UI elements
        this.statusEl = document.getElementById('status');
        this.talkBtn = document.getElementById('talkBtn');
        this.transcriptEl = document.getElementById('transcript');
        this.visualizerCanvas = document.getElementById('visualizer');
        this.visualizerCtx = this.visualizerCanvas.getContext('2d');

        // Current transcript
        this.currentUserTranscript = '';
        this.currentAssistantResponse = '';

        this.init();
    }

    async init() {
        // Initialize audio context
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000  // Match server expectation
        });

        // Add Gain and Compressor to prevent distortion ("fati hui voice")
        this.gainNode = this.audioContext.createGain();
        this.gainNode.gain.value = 0.95; // Slightly below 1.0 to avoid clipping

        this.compressor = this.audioContext.createDynamicsCompressor();
        this.compressor.threshold.setValueAtTime(-20, this.audioContext.currentTime);
        this.compressor.knee.setValueAtTime(40, this.audioContext.currentTime);
        this.compressor.ratio.setValueAtTime(12, this.audioContext.currentTime);
        this.compressor.attack.setValueAtTime(0, this.audioContext.currentTime);
        this.compressor.release.setValueAtTime(0.25, this.audioContext.currentTime);

        this.compressor.connect(this.gainNode);
        this.gainNode.connect(this.audioContext.destination);

        // Connect to WebSocket
        this.connectWebSocket();

        // Setup UI
        this.setupUI();

        // Setup visualizer
        this.setupVisualizer();
    }

    connectWebSocket() {
        return new Promise((resolve, reject) => {
            this.updateStatus('Connecting...', '');

            const wsHost = window.location.hostname || '127.0.0.1';
            this.ws = new WebSocket(`ws://${wsHost}:8765`);

            this.ws.onopen = () => {
                console.log('✅ Connected to server');
                this.updateStatus('Connected - Ready to talk', 'connected');
                this.talkBtn.disabled = false;
                resolve();
            };

            this.ws.onmessage = (event) => {
                this.handleServerMessage(JSON.parse(event.data));
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.updateStatus('Connection error - check server', '');
                reject(error);
            };

            this.ws.onclose = (event) => {
                console.log(`🔌 Disconnected from server. Code: ${event.code}, Reason: ${event.reason}`);
                this.updateStatus('Disconnected - Refresh to reconnect', '');
                this.talkBtn.disabled = true;

                // Show debug info
                const debugEl = document.getElementById('debugInfo');
                const wsDebug = document.getElementById('wsDebug');
                if (debugEl && wsDebug) {
                    debugEl.style.display = 'block';
                    wsDebug.textContent = `Closed (Code: ${event.code}, Reason: ${event.reason || 'none'})`;
                }
            };

            // Timeout after 5 seconds
            setTimeout(() => reject(new Error('Connection timeout')), 5000);
        });
    }

    setupUI() {
        // Toggle to talk button
        this.talkBtn.addEventListener('click', () => {
            if (this.isRecording) {
                this.stopRecording();
            } else {
                this.startRecording();
            }
        });

        // Pre-initialize on first hover or touch to remove startup lag
        const preInit = async () => {
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('🔊 AudioContext pre-warmed');
            }
            // Remove listeners after first run
            this.talkBtn.removeEventListener('mouseenter', preInit);
            this.talkBtn.removeEventListener('touchstart', preInit);
        };
        this.talkBtn.addEventListener('mouseenter', preInit);
        this.talkBtn.addEventListener('touchstart', preInit);

        // Keyboard shortcut (spacebar)
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !e.repeat && !this.talkBtn.disabled) {
                e.preventDefault();
                if (this.isRecording) {
                    this.stopRecording();
                } else {
                    this.startRecording();
                }
            }
        });
    }

    setupVisualizer() {
        this.visualizerCanvas.width = this.visualizerCanvas.offsetWidth;
        this.visualizerCanvas.height = this.visualizerCanvas.offsetHeight;

        // We defer animation until we have an analyser
        this.analyser = null;
        this.dataArray = null;
        this.animateVisualizer();
    }

    animateVisualizer() {
        const draw = () => {
            const ctx = this.visualizerCtx;
            const width = this.visualizerCanvas.width;
            const height = this.visualizerCanvas.height;

            ctx.clearRect(0, 0, width, height);

            if (this.isRecording && this.analyser) {
                // Real frequency data
                this.analyser.getByteFrequencyData(this.dataArray);

                const bufferLength = this.analyser.frequencyBinCount;
                const barWidth = (width / bufferLength) * 2.5;
                let barHeight;
                let x = 0;

                for (let i = 0; i < bufferLength; i++) {
                    barHeight = this.dataArray[i] / 2;

                    ctx.fillStyle = 'rgba(33, 150, 243, 0.8)';
                    ctx.fillRect(x, height - barHeight, barWidth, barHeight);

                    x += barWidth + 1;
                }
            } else if (this.isSpeaking) {
                // Fake animation for AI speaking (since we don't analyze AI audio yet)
                const time = Date.now() / 1000;
                const bars = 20;
                const barWidth = width / bars;

                for (let i = 0; i < bars; i++) {
                    const barHeight = Math.sin(time * 5 + i * 0.5) * 20 + 25;
                    const x = i * barWidth;
                    const y = (height - barHeight) / 2;

                    ctx.fillStyle = 'rgba(156, 39, 176, 0.8)';
                    ctx.fillRect(x, y, barWidth - 2, barHeight);
                }
            }

            requestAnimationFrame(draw);
        };

        draw();
    }

    async startRecording() {
        if (this.isRecording) return;

        console.log('🎤 Starting recording');

        // Ensure WebSocket is connected before recording
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.log('⏳ WebSocket not ready, connecting...');
            try {
                await this.connectWebSocket();
                console.log('✅ WebSocket ready for recording');
            } catch (error) {
                console.error('❌ Failed to connect WebSocket:', error);
                this.updateStatus('Connection failed - refresh page', '');
                return;
            }
        }

        // If AI is speaking, interrupt it
        if (this.isSpeaking) {
            this.ws.send(JSON.stringify({ type: 'interrupt' }));
            this.stopAudioPlayback();
        }

        // Ensure AudioContext is resumed
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
            console.log('🔊 AudioContext resumed');
        }

        this.isRecording = true;
        this.talkBtn.classList.add('active');
        this.talkBtn.textContent = '🛑 Stop Talking';
        this.updateStatus('Listening...', 'listening');

        // Reset metrics
        this.metrics.audioSentAt = Date.now();
        this.metrics.sttReceivedAt = 0;
        this.metrics.llmReceivedAt = 0;
        this.metrics.ttsReceivedAt = 0;

        this.currentUserTranscript = '';
        this.totalChunksSent = 0;

        try {
            // Get microphone access
            console.log("🎤 Requesting microphone access...");
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            console.log("✅ Microphone access granted!");
            console.log("📊 Audio tracks:", this.mediaStream.getAudioTracks());

            const actualSampleRate = this.audioContext.sampleRate;
            console.log(`ℹ️ Actual AudioContext Sample Rate: ${actualSampleRate}Hz`);

            // Create audio source
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);

            // Create Analyser for Visualizer
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            const bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(bufferLength);
            source.connect(this.analyser);

            // Target sample rate is 16000
            const targetSampleRate = 16000;
            const downsampleRatio = actualSampleRate / targetSampleRate;
            console.log(`🔄 Downsampling ratio: ${downsampleRatio.toFixed(2)}`);

            // Use a buffer size that results in ~40-60ms chunks
            // e.g. 2048 at 48kHz is ~42ms.
            let bufferSize = 2048;
            if (actualSampleRate < 30000) bufferSize = 1024;

            const processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            source.connect(processor);
            processor.connect(this.audioContext.destination);

            processor.onaudioprocess = (e) => {
                if (!this.isRecording) return;

                const inputData = e.inputBuffer.getChannelData(0);

                // 1. Resample to 16kHz
                const resampledLength = Math.floor(inputData.length / downsampleRatio);
                const resampledData = new Float32Array(resampledLength);

                for (let i = 0; i < resampledLength; i++) {
                    const index = Math.floor(i * downsampleRatio);
                    resampledData[i] = inputData[index];
                }

                // 2. Convert to Int16 PCM and calculate RMS
                const pcmData = new Int16Array(resampledLength);
                let sumSq = 0;
                for (let i = 0; i < resampledLength; i++) {
                    const s = Math.max(-1, Math.min(1, resampledData[i]));
                    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    sumSq += s * s;
                }

                const rms = Math.sqrt(sumSq / resampledLength);

                // DEBUG: Log RMS occasionally
                if (this.totalChunksSent % 10 === 0) {
                    console.log(`🔊 Chunk ${this.totalChunksSent}: RMS=${rms.toFixed(6)}`);
                }

                // Check WebSocket state BEFORE sending
                if (!this.ws) {
                    if (this.totalChunksSent % 20 === 0) {
                        console.error('❌ WebSocket is NULL!');
                    }
                    return;
                }

                if (this.ws.readyState !== WebSocket.OPEN) {
                    if (this.totalChunksSent % 20 === 0) {
                        console.error(`❌ WebSocket not open! State: ${this.ws.readyState}`);
                    }
                    return;
                }

                // Send based on mode
                try {
                    if (this.DEBUG_MODE) {
                        // DEBUG MODE: Send ALL audio
                        this.sendAudioChunk([pcmData]);
                    } else {
                        // NORMAL MODE: Filter by RMS
                        const RMS_THRESHOLD = 0.0005;
                        if (rms > RMS_THRESHOLD) {
                            this.sendAudioChunk([pcmData]);
                        }
                    }
                } catch (error) {
                    console.error('❌ Error sending chunk:', error);
                }
            };

            this.audioProcessor = processor;
            this.audioSource = source;

        } catch (error) {
            console.error('❌ Microphone access error:', error);
            this.updateStatus('Microphone access denied', '');
            this.isRecording = false;
            this.talkBtn.classList.remove('active');
        }
    }

    stopRecording() {
        if (!this.isRecording) return;

        console.log('🛑 Stopping recording');

        this.isRecording = false;
        this.talkBtn.classList.remove('active');
        this.talkBtn.textContent = '🎤 Click to Talk';
        this.updateStatus('Processing...', 'processing');

        // Stop microphone
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }

        // Cleanup audio nodes safely
        if (this.audioProcessor) {
            try { this.audioProcessor.disconnect(); } catch (e) { }
            this.audioProcessor.onaudioprocess = null;
        }
        if (this.audioSource) {
            try { this.audioSource.disconnect(); } catch (e) { }
        }
        if (this.analyser) {
            try { this.analyser.disconnect(); } catch (e) { }
        }

        // Signal end of speech
        this.ws.send(JSON.stringify({ type: 'end_of_speech' }));
    }

    sendAudioChunk(chunks) {
        // Combine chunks
        const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
        const combined = new Int16Array(totalLength);
        let offset = 0;
        for (const chunk of chunks) {
            combined.set(chunk, offset);
            offset += chunk.length;
        }

        // Convert to base64 - FIXED: loop-based encoding (spread operator fails with large arrays)
        const bytes = new Uint8Array(combined.buffer);
        let binary = '';
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const base64 = btoa(binary);

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'audio_chunk',
            audio: base64
        }));
        this.totalChunksSent++;
    }

    handleServerMessage(data) {
        switch (data.type) {
            case 'transcript_partial':
                this.handlePartialTranscript(data.text);
                break;

            case 'transcript_final':
                this.handleFinalTranscript(data.text);
                break;

            case 'llm_token':
                this.handleLLMToken(data.token);
                break;

            case 'audio_chunk':
                this.handleAudioChunk(data.audio);
                break;

            case 'response_complete':
                this.handleResponseComplete();
                break;

            case 'state':
                this.updateStatus(data.message, data.status);
                if (data.status === 'speaking') {
                    this.isSpeaking = true;
                } else if (data.status === 'success' || data.status === 'idle') {
                    this.isSpeaking = false;
                }
                break;
        }
    }

    handlePartialTranscript(text) {
        if (this.metrics.sttReceivedAt === 0) {
            this.metrics.sttReceivedAt = Date.now();
            this.updateMetrics();
        }

        if (text.trim().length <= 1) return; // Ignore noise/.
        this.currentUserTranscript = text;
        this.updateTranscript('user', text, true);
    }

    handleFinalTranscript(text) {
        this.currentUserTranscript = text;
        this.updateTranscript('user', text, false);
        this.updateStatus('Krishna is responding...', 'processing');
    }

    handleLLMToken(token) {
        if (this.metrics.llmReceivedAt === 0) {
            this.metrics.llmReceivedAt = Date.now();
            this.updateMetrics();
        }

        this.currentAssistantResponse += token;
        this.updateTranscript('assistant', this.currentAssistantResponse, true);
    }

    async handleAudioChunk(base64Audio) {
        if (this.metrics.ttsReceivedAt === 0) {
            this.metrics.ttsReceivedAt = Date.now();
            this.updateMetrics();
            this.updateStatus('Krishna is speaking...', 'speaking');
            this.isSpeaking = true;
        }

        // Decode base64 to binary
        const binaryString = atob(base64Audio);
        let bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        // Handle odd bytes from previous chunks
        if (this.leftoverBytes) {
            const combined = new Uint8Array(this.leftoverBytes.length + bytes.length);
            combined.set(this.leftoverBytes);
            combined.set(bytes, this.leftoverBytes.length);
            bytes = combined;
            this.leftoverBytes = null;
        }

        // If we still have an odd number of bytes, save the last one
        if (bytes.length % 2 !== 0) {
            this.leftoverBytes = bytes.slice(-1);
            bytes = bytes.slice(0, -1);
        }

        if (bytes.length === 0) return;

        // Convert raw bytes to Int16 PCM (16kHz mono)
        // Correctly handle the buffer if it's not aligned
        const pcmData = new Int16Array(bytes.buffer, 0, bytes.length / 2);
        this.audioQueue.push(pcmData);

        // Start playback if not already playing AND we have enough buffer (min 1 chunk for faster response)
        if (!this.isPlaying && this.audioQueue.length >= 1) {
            this.playAudioQueue();
        }
    }

    async playAudioQueue() {
        this.isPlaying = true;

        // Target sample rate from server (pcm_16000)
        const sampleRate = 16000;

        while (this.audioQueue.length > 0) {
            const pcmData = this.audioQueue.shift();

            // Convert Int16 to Float32
            const floatData = new Float32Array(pcmData.length);
            for (let i = 0; i < pcmData.length; i++) {
                floatData[i] = pcmData[i] / 32768.0;
            }

            try {
                const buffer = this.audioContext.createBuffer(1, floatData.length, sampleRate);
                buffer.copyToChannel(floatData, 0);

                const source = this.audioContext.createBufferSource();
                source.buffer = buffer;
                source.connect(this.compressor); // Route through compressor
                this.currentSource = source; // Store for interruption

                // Schedule for gapless playback
                const now = this.audioContext.currentTime;
                if (this.nextPlaybackTime < now) {
                    this.nextPlaybackTime = now + 0.05; // Lower lookahead for faster response
                }

                source.start(this.nextPlaybackTime);
                this.nextPlaybackTime += buffer.duration;

                // Keep the loop running without blocking
                await new Promise(r => setTimeout(r, 0));
            } catch (error) {
                console.error('❌ PCM playback error:', error);
            }
        }

        this.isPlaying = false;
    }

    stopAudioPlayback() {
        this.audioQueue = [];
        this.isPlaying = false;
        this.isSpeaking = false;
        this.nextPlaybackTime = 0;
        this.leftoverBytes = null;

        // Stop current source if possible
        if (this.currentSource) {
            try { this.currentSource.stop(); } catch (e) { }
            this.currentSource = null;
        }
    }

    handleResponseComplete() {
        this.updateTranscript('assistant', this.currentAssistantResponse, false);
        this.currentAssistantResponse = '';
        this.updateStatus('Connected - Ready to talk', 'connected');
        this.isSpeaking = false;
    }

    updateTranscript(role, text, isPartial) {
        // Remove previous partial of same role
        const lastItem = this.transcriptEl.lastElementChild;
        if (lastItem && lastItem.classList.contains(role) && lastItem.classList.contains('partial')) {
            lastItem.remove();
        }

        // Add new transcript item
        const item = document.createElement('div');
        item.className = `transcript-item ${role}`;
        if (isPartial) {
            item.classList.add('partial');
        }

        const prefix = role === 'user' ? 'You: ' : 'Krishna: ';
        item.textContent = prefix + text;

        this.transcriptEl.appendChild(item);
        this.transcriptEl.scrollTop = this.transcriptEl.scrollHeight;
    }

    updateStatus(message, className) {
        this.statusEl.textContent = message;
        this.statusEl.className = 'status ' + className;
    }

    updateMetrics() {
        const sttLatency = this.metrics.sttReceivedAt - this.metrics.audioSentAt;
        const llmLatency = this.metrics.llmReceivedAt - this.metrics.audioSentAt;
        const ttsLatency = this.metrics.ttsReceivedAt - this.metrics.audioSentAt;

        if (sttLatency > 0) {
            document.getElementById('sttLatency').textContent = sttLatency + 'ms';
            document.getElementById('sttLatency').className = this.getLatencyClass(sttLatency, 400);
        }

        if (llmLatency > 0) {
            document.getElementById('llmLatency').textContent = llmLatency + 'ms';
            document.getElementById('llmLatency').className = this.getLatencyClass(llmLatency, 500);
        }

        if (ttsLatency > 0) {
            document.getElementById('ttsLatency').textContent = ttsLatency + 'ms';
            document.getElementById('totalLatency').textContent = ttsLatency + 'ms';
            document.getElementById('totalLatency').className = this.getLatencyClass(ttsLatency, 1000);
        }
    }

    getLatencyClass(latency, target) {
        if (latency < target * 0.8) return 'latency-good';
        if (latency < target * 1.2) return 'latency-ok';
        return 'latency-bad';
    }
}

// Initialize client when page loads
window.addEventListener('load', () => {
    new StreamingVoiceClient();
});
