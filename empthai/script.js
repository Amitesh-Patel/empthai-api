// DOM Elements
const connectBtn = document.getElementById('connectBtn');
const disconnectBtn = document.getElementById('disconnectBtn');
const sendTextBtn = document.getElementById('sendTextBtn');
const startRecordingBtn = document.getElementById('startRecordingBtn');
const stopRecordingBtn = document.getElementById('stopRecordingBtn');
const clearSessionBtn = document.getElementById('clearSessionBtn');
const textInput = document.getElementById('textInput');
const chatContainer = document.getElementById('chatContainer');
const connectionStatus = document.getElementById('connectionStatus');
const statusTooltip = document.getElementById('statusTooltip');
const voiceIndicator = document.getElementById('voiceIndicator');

// Variables
let socket = null;
let mediaRecorder = null;
let audioChunks = [];
let clientId = null;
let isRecording = false;
let audioContext = null;
let audioQueue = [];
let isPlaying = false;
let streamingMessageElement = null;
let currentStreamText = "";
let audioAnalyser = null;
let audioDataArray = null;

// Generate a random client ID
function generateClientId() {
    return 'client_' + Math.random().toString(36).substring(2, 15);
}

// Initialize audio context
function initAudioContext() {
    // Create AudioContext when needed (to avoid autoplay policy issues)
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContext;
}

// Connect to WebSocket
connectBtn.addEventListener('click', () => {
    clientId = generateClientId();
    
    // Update UI to connecting state
    connectionStatus.textContent = 'Connecting...';
    connectionStatus.classList.add('processing');
    statusTooltip.textContent = 'Establishing connection...';
    
    // Create WebSocket connection
    socket = new WebSocket(`ws://localhost:8000/ws/${clientId}`);
    
    // Connection opened
    socket.addEventListener('open', (event) => {
        connectionStatus.textContent = 'Connected';
        connectionStatus.classList.remove('processing');
        connectionStatus.classList.add('connected');
        statusTooltip.textContent = 'Successfully connected to server';
        
        // Enable appropriate buttons
        connectBtn.disabled = true;
        disconnectBtn.disabled = false;
        sendTextBtn.disabled = false;
        startRecordingBtn.disabled = false;
        clearSessionBtn.disabled = false;
        
        // Apply button transitions
        const buttons = [disconnectBtn, sendTextBtn, startRecordingBtn, clearSessionBtn];
        buttons.forEach(btn => {
            btn.style.transition = 'opacity 0.3s ease';
            btn.style.opacity = '1';
        });
        
        // Clear welcome message if it exists
        if (document.querySelector('.welcome-message')) {
            const welcome = document.querySelector('.welcome-message');
            welcome.style.opacity = '0';
            welcome.style.transform = 'translateY(-20px)';
            
            // Remove after animation completes
            setTimeout(() => {
                chatContainer.innerHTML = '';
                addStatusMessage('Connected to server');
            }, 300);
        } else {
            addStatusMessage('Connected to server');
        }
    });
    
    // Listen for messages
    socket.addEventListener('message', async (event) => {
        try {
            const message = JSON.parse(event.data);
            console.log('Message from server:', message);
            
            switch (message.type) {
                case 'status':
                    addStatusMessage(`Status: ${message.status}`);
                    break;
                    
                case 'transcription':
                    addUserMessage(`(Transcribed) ${message.text}`);
                    break;
                    
                case 'text_response':
                    // Create container with avatar for bot response
                    const messageWithAvatar = document.createElement('div');
                    messageWithAvatar.className = 'message-with-avatar';
                    
                    // Create avatar
                    const avatar = document.createElement('div');
                    avatar.className = 'bot-avatar';
                    avatar.textContent = 'AI';
                    messageWithAvatar.appendChild(avatar);
                    
                    // Create streaming message container
                    streamingMessageElement = document.createElement('div');
                    streamingMessageElement.className = 'streaming-message';
                    
                    // Add a streaming indicator
                    const indicator = document.createElement('span');
                    indicator.className = 'stream-indicator';
                    streamingMessageElement.appendChild(indicator);
                    
                    // Initialize with empty content that will be filled by chunks
                    currentStreamText = "";
                    streamingMessageElement.appendChild(document.createTextNode(""));
                    
                    // Add to the message container
                    messageWithAvatar.appendChild(streamingMessageElement);
                    chatContainer.appendChild(messageWithAvatar);
                    
                    // Scroll to bottom with smooth animation
                    smoothScrollToBottom();
                    break;
                    
                case 'audio_response_chunk':
                    // Update the streaming message with the new chunk
                    currentStreamText += message.text;
                    
                    // If this is the first or ongoing chunk, update the streaming message
                    if (streamingMessageElement) {
                        // Remove previous content and update
                        while (streamingMessageElement.childNodes.length > 1) {
                            streamingMessageElement.removeChild(streamingMessageElement.lastChild);
                        }
                        streamingMessageElement.appendChild(document.createTextNode(currentStreamText));
                        
                        // If this is the last chunk, convert to regular bot message
                        if (message.end) {
                            // Remove the streaming indicator
                            streamingMessageElement.removeChild(streamingMessageElement.firstChild);
                            streamingMessageElement.className = 'bot-message';
                            
                            // Add typing completion animation
                            streamingMessageElement.style.transition = 'box-shadow 0.3s ease';
                            streamingMessageElement.style.boxShadow = '0 4px 12px rgba(66, 133, 244, 0.2)';
                            setTimeout(() => {
                                if (streamingMessageElement) {
                                    streamingMessageElement.style.boxShadow = '0 3px 8px rgba(0, 0, 0, 0.05)';
                                }
                            }, 300);
                            
                            streamingMessageElement = null;
                            currentStreamText = "";
                        }
                        
                        smoothScrollToBottom();
                    }
                    
                    // Play the audio chunk
                    const audioData = atob(message.audio);
                    const arrayBuffer = new ArrayBuffer(audioData.length);
                    const view = new Uint8Array(arrayBuffer);
                    for (let i = 0; i < audioData.length; i++) {
                        view[i] = audioData.charCodeAt(i);
                    }
                    
                    // Add to queue and play
                    audioQueue.push(arrayBuffer);
                    playNextAudio();
                    break;
                    
                case 'audio_response':
                    // Handle legacy non-chunked audio (for backward compatibility)
                    const legacyAudioData = atob(message.audio);
                    const legacyArrayBuffer = new ArrayBuffer(legacyAudioData.length);
                    const legacyView = new Uint8Array(legacyArrayBuffer);
                    for (let i = 0; i < legacyAudioData.length; i++) {
                        legacyView[i] = legacyAudioData.charCodeAt(i);
                    }
                    
                    // Add to queue and play
                    audioQueue.push(legacyArrayBuffer);
                    playNextAudio();
                    addBotMessage(message.text);
                    break;
                    
                case 'error':
                    addStatusMessage(`Error: ${message.message}`);
                    connectionStatus.classList.add('processing');
                    setTimeout(() => {
                        connectionStatus.classList.remove('processing');
                    }, 1500);
                    break;
            }
        } catch (error) {
            console.error('Error processing message:', error);
            addStatusMessage('Error processing server message');
        }
    });
    
    // Connection closed
    socket.addEventListener('close', (event) => {
        connectionStatus.textContent = 'Disconnected';
        connectionStatus.classList.remove('connected');
        connectionStatus.classList.remove('processing');
        statusTooltip.textContent = 'Connect to start a conversation';
        
        // Disable appropriate buttons with fade out effect
        disconnectBtn.disabled = true;
        sendTextBtn.disabled = true;
        startRecordingBtn.disabled = true;
        stopRecordingBtn.disabled = true;
        clearSessionBtn.disabled = true;
        
        // Apply button transitions
        const buttons = [disconnectBtn, sendTextBtn, startRecordingBtn, stopRecordingBtn, clearSessionBtn];
        buttons.forEach(btn => {
            btn.style.opacity = '0.6';
        });
        
        connectBtn.disabled = false;
        connectBtn.style.opacity = '1';
        
        addStatusMessage('Disconnected from server');
    });
    
    // Connection error
    socket.addEventListener('error', (event) => {
        connectionStatus.textContent = 'Error';
        connectionStatus.classList.remove('connected');
        connectionStatus.classList.add('processing');
        statusTooltip.textContent = 'Connection error occurred';
        
        addStatusMessage('Connection error');
        console.error('WebSocket error:', event);
        
        // Re-enable connect button after error
        connectBtn.disabled = false;
    });
});

// Disconnect from WebSocket
disconnectBtn.addEventListener('click', () => {
    if (socket) {
        // Add visual feedback
        connectionStatus.textContent = 'Disconnecting...';
        connectionStatus.classList.add('processing');
        connectionStatus.classList.remove('connected');
        
        addStatusMessage('Disconnecting...');
        
        // Close socket
        socket.close();
        socket = null;
    }
});

// Send text message
sendTextBtn.addEventListener('click', () => {
    sendMessage();
});

// Handle Enter key in text input
textInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
        sendMessage();
    }
});

// Send message helper function
function sendMessage() {
    const text = textInput.value.trim();
    if (text && socket && socket.readyState === WebSocket.OPEN) {
        // Add visual feedback
        sendTextBtn.classList.add('sending');
        
        // Send text message
        const message = {
            type: 'text_input',
            text: text,
            use_rag: true
        };
        
        socket.send(JSON.stringify(message));
        addUserMessage(text);
        textInput.value = '';
        
        // Remove visual feedback after a short delay
        setTimeout(() => {
            sendTextBtn.classList.remove('sending');
        }, 300);
    }
}

// Start recording audio
startRecordingBtn.addEventListener('click', async () => {
    if (isRecording) return;
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        // Set up audio visualization
        setupAudioVisualization(stream);
        
        mediaRecorder.addEventListener('dataavailable', (event) => {
            audioChunks.push(event.data);
        });
        
        mediaRecorder.addEventListener('stop', async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            
            // Send audio data to server
            if (socket && socket.readyState === WebSocket.OPEN) {
                const reader = new FileReader();
                reader.onload = () => {
                    socket.send(reader.result);
                    addStatusMessage('Audio sent to server');
                };
                reader.readAsArrayBuffer(audioBlob);
            }
            
            isRecording = false;
            startRecordingBtn.disabled = false;
            stopRecordingBtn.disabled = true;
            
            // Hide voice visualization
            voiceIndicator.style.display = 'none';
            
            // Clean up audio analysis
            if (audioAnalyser) {
                try {
                    audioAnalyser.disconnect();
                } catch (error) {
                    console.log('Analyser already disconnected');
                }
            }
        });
        
        mediaRecorder.start();
        isRecording = true;
        startRecordingBtn.disabled = true;
        stopRecordingBtn.disabled = false;
        
        // Show voice visualization
        voiceIndicator.style.display = 'flex';
        
        addStatusMessage('Recording started');
        
    } catch (error) {
        console.error('Error accessing microphone:', error);
        addStatusMessage('Error accessing microphone');
    }
});

// Setup audio visualization for more dynamic voice activity display
function setupAudioVisualization(stream) {
    const ctx = initAudioContext();
    const source = ctx.createMediaStreamSource(stream);
    audioAnalyser = ctx.createAnalyser();
    audioAnalyser.fftSize = 32;
    
    const bufferLength = audioAnalyser.frequencyBinCount;
    audioDataArray = new Uint8Array(bufferLength);
    
    source.connect(audioAnalyser);
    
    // Update voice bars
    function updateVoiceVisualization() {
        if (!isRecording) return;
        
        audioAnalyser.getByteFrequencyData(audioDataArray);
        
        // Get average level
        let total = 0;
        for (let i = 0; i < audioDataArray.length; i++) {
            total += audioDataArray[i];
        }
        const average = total / audioDataArray.length;
        
        // Update voice bars
        const voiceBars = document.querySelectorAll('.voice-bar');
        voiceBars.forEach((bar, index) => {
            // Use a combination of the data point and random variation
            const value = Math.min(100, (audioDataArray[index % audioDataArray.length] / 2) + (average / 4) + (Math.random() * 15));
            bar.style.height = `${value * 0.2}px`;
        });
        
        requestAnimationFrame(updateVoiceVisualization);
    }
    
    updateVoiceVisualization();
}

// Stop recording audio
stopRecordingBtn.addEventListener('click', () => {
    if (mediaRecorder && isRecording) {
        // Add visual feedback
        stopRecordingBtn.classList.add('stopping');
        
        mediaRecorder.stop();
        addStatusMessage('Recording stopped');
        
        // Remove visual feedback after a short delay
        setTimeout(() => {
            stopRecordingBtn.classList.remove('stopping');
        }, 300);
    }
});

// Clear session
clearSessionBtn.addEventListener('click', () => {
    if (socket && socket.readyState === WebSocket.OPEN) {
        // Add visual feedback
        clearSessionBtn.classList.add('clearing');
        
        const message = {
            type: 'clear_session'
        };
        
        socket.send(JSON.stringify(message));
        
        // Fade out existing messages
        const messages = chatContainer.querySelectorAll('.user-message, .bot-message, .status-message, .message-with-avatar');
        messages.forEach(msg => {
            msg.style.transition = 'opacity 0.3s ease';
            msg.style.opacity = '0';
        });
        
        // Clear after animation completes
        setTimeout(() => {
            chatContainer.innerHTML = '';
            addStatusMessage('Session cleared');
            
            // Remove visual feedback
            clearSessionBtn.classList.remove('clearing');
        }, 300);
    }
});

// Play the next audio in queue
async function playNextAudio() {
    if (isPlaying || audioQueue.length === 0) return;
    
    isPlaying = true;
    const ctx = initAudioContext();
    
    try {
        const arrayBuffer = audioQueue.shift();
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
        
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        
        source.onended = () => {
            isPlaying = false;
            playNextAudio(); // Play next in queue if any
        };
        
        source.start(0);
    } catch (error) {
        console.error('Error playing audio:', error);
        isPlaying = false;
        playNextAudio(); // Try next one
    }
}

// Add message to chat with improved animations
function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'user-message';
    messageDiv.textContent = text;
    
    // Add appear animation
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(10px)';
    
    chatContainer.appendChild(messageDiv);
    
    // Trigger animation
    setTimeout(() => {
        messageDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
    }, 10);
    
    smoothScrollToBottom();
}

function addBotMessage(text) {
    // Create container with avatar
    const messageWithAvatar = document.createElement('div');
    messageWithAvatar.className = 'message-with-avatar';
    
    // Create avatar
    const avatar = document.createElement('div');
    avatar.className = 'bot-avatar';
    avatar.textContent = 'AI';
    messageWithAvatar.appendChild(avatar);
    
    // Create message
    const messageDiv = document.createElement('div');
    messageDiv.className = 'bot-message';
    messageDiv.textContent = text;
    
    // Add appear animation
    messageDiv.style.opacity = '0';
    messageDiv.style.transform = 'translateY(10px)';
    
    messageWithAvatar.appendChild(messageDiv);
    chatContainer.appendChild(messageWithAvatar);
    
    // Trigger animation
    setTimeout(() => {
        messageDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        messageDiv.style.opacity = '1';
        messageDiv.style.transform = 'translateY(0)';
    }, 10);
    
    smoothScrollToBottom();
}

function addStatusMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'status-message';
    messageDiv.textContent = text;
    
    // Add appear animation
    messageDiv.style.opacity = '0';
    
    chatContainer.appendChild(messageDiv);
    
    // Trigger animation
    setTimeout(() => {
        messageDiv.style.transition = 'opacity 0.3s ease';
        messageDiv.style.opacity = '1';
    }, 10);
    
    smoothScrollToBottom();
}

// Smooth scrolling to bottom of chat
function smoothScrollToBottom() {
    const scrollHeight = chatContainer.scrollHeight;
    const currentScroll = chatContainer.scrollTop;
    const targetScroll = scrollHeight - chatContainer.clientHeight;
    const distance = targetScroll - currentScroll;
    
    // If already at bottom or very close, just jump to bottom
    if (distance < 50) {
        chatContainer.scrollTop = scrollHeight;
        return;
    }
    
    // Otherwise animate the scroll
    const duration = 300; // ms
    const startTime = performance.now();
    
    function scrollStep(timestamp) {
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeProgress = easeOutCubic(progress);
        
        chatContainer.scrollTop = currentScroll + (distance * easeProgress);
        
        if (progress < 1) {
            requestAnimationFrame(scrollStep);
        }
    }
    
    requestAnimationFrame(scrollStep);
}

// Easing function for smoother animation
function easeOutCubic(x) {
    return 1 - Math.pow(1 - x, 3);
}

// Initialize tooltips for buttons
function initTooltips() {
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        button.setAttribute('title', button.textContent.trim());
    });
}

// Add input focus effects
function setupInputEffects() {
    textInput.addEventListener('focus', () => {
        textInput.parentElement.classList.add('input-focused');
    });
    
    textInput.addEventListener('blur', () => {
        textInput.parentElement.classList.remove('input-focused');
    });
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    initTooltips();
    setupInputEffects();
    
    // Add CSS class for input container
    document.querySelector('.input-container').classList.add('input-container-ready');
});