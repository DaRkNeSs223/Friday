// static/script.js
const socket = io(); // Conecta ao servidor Socket.IO
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const micButton = document.getElementById('micButton');
const startFridayButton = document.getElementById('startFriday');
const stopFridayButton = document.getElementById('stopFriday');
const showCommandsButton = document.getElementById('showCommands');
const statusText = document.getElementById('statusText');

let fridayActive = false;
let recognition; // Para a API de reconhecimento de voz do navegador

// --- Funções de Manipulação da Interface ---
function appendMessage(sender, message, isHtml = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.classList.add(sender.toLowerCase()); // 'friday', 'user', 'system', 'comandos'

    if (isHtml) {
        messageElement.innerHTML = message;
    } else {
        messageElement.textContent = message;
    }
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight; // Rola para o final
}

function updateStatus(status) {
    statusText.textContent = status;
}

function toggleInput(enable) {
    messageInput.disabled = !enable;
    sendButton.disabled = !enable;
    micButton.disabled = !enable;
}

function setFridayActive(active) {
    fridayActive = active;
    startFridayButton.disabled = active;
    stopFridayButton.disabled = !active;
    toggleInput(active);
    if (!active) {
        updateStatus("Inativo.");
    }
}

// --- Funções de Reconhecimento de Voz do Navegador ---
function startSpeechRecognition() {
    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'pt-BR';
        recognition.interimResults = false; // Queremos apenas resultados finais
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            console.log('Reconhecimento de voz iniciado...');
            micButton.classList.add('recording');
            updateStatus("Microfone ativo. Fale agora...");
            messageInput.disabled = true; // Desabilita input de texto enquanto ouve
            sendButton.disabled = true;
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            console.log('Reconhecido:', transcript);
            micButton.classList.remove('recording');
            updateStatus("Voz reconhecida. Enviando...");
            // Envia o resultado para o servidor Python
            socket.emit('web_microphone_result', { text: transcript });
            messageInput.disabled = false;
            sendButton.disabled = false;
        };

        recognition.onerror = (event) => {
            console.error('Erro no reconhecimento de voz:', event.error);
            micButton.classList.remove('recording');
            updateStatus(`Erro no microfone: ${event.error}.`);
            // Se o Friday estiver ativo, reabilita o input
            if (fridayActive) {
                messageInput.disabled = false;
                sendButton.disabled = false;
            }
        };

        recognition.onend = () => {
            console.log('Reconhecimento de voz encerrado.');
            micButton.classList.remove('recording');
            // O status será atualizado pelo servidor após processar o comando
            if (fridayActive) {
                messageInput.disabled = false;
                sendButton.disabled = false;
            }
        };

        recognition.start();
    } else {
        alert('Seu navegador não suporta a API de Reconhecimento de Voz. Por favor, use Chrome ou Edge.');
        micButton.disabled = true;
    }
}

// --- Funções de Fala da Friday no Navegador (Text-to-Speech) ---
let isSpeaking = false;
function speakBrowser(text) {
    if (!('speechSynthesis' in window)) {
        console.warn('Seu navegador não suporta a API de Síntese de Fala.');
        return;
    }

    // Interrompe qualquer fala anterior
    if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'pt-BR'; // Define o idioma
    utterance.rate = 1; // Velocidade da fala (1 é normal)
    utterance.pitch = 1; // Tom da voz (1 é normal)

    // Tenta encontrar uma voz em português do Brasil
    const voices = speechSynthesis.getVoices();
    const portugueseVoice = voices.find(voice => voice.lang === 'pt-BR' && voice.name.includes('Brazil'));
    if (portugueseVoice) {
        utterance.voice = portugueseVoice;
    } else {
        // Se não encontrar uma específica, tenta a primeira em pt-BR
        const genericPortugueseVoice = voices.find(voice => voice.lang === 'pt-BR');
        if (genericPortugueseVoice) {
            utterance.voice = genericPortugueseVoice;
        }
    }


    utterance.onstart = () => {
        isSpeaking = true;
        updateStatus("Friday falando...");
    };

    utterance.onend = () => {
        isSpeaking = false;
        // O status deve voltar para "Ouvindo" ou "Pronto" pelo backend
        if (fridayActive) {
             updateStatus("Pronto para o próximo comando."); // Ou "Ouvindo"
        }
    };

    utterance.onerror = (event) => {
        isSpeaking = false;
        console.error('Erro na síntese de fala:', event);
        if (fridayActive) {
            updateStatus("Erro ao falar.");
        }
    };

    speechSynthesis.speak(utterance);
}


// Garante que as vozes estejam carregadas (assíncrono)
speechSynthesis.onvoiceschanged = () => {
    // Agora as vozes estão disponíveis
    console.log("Vozes do navegador carregadas.");
};


// --- Event Listeners ---
sendButton.addEventListener('click', () => {
    const command = messageInput.value.trim();
    if (command && fridayActive) {
        socket.emit('send_command', { command: command });
        messageInput.value = ''; // Limpa o input
    }
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

micButton.addEventListener('click', () => {
    if (fridayActive) {
        startSpeechRecognition();
    }
});

startFridayButton.addEventListener('click', () => {
    socket.emit('start_friday');
});

stopFridayButton.addEventListener('click', () => {
    socket.emit('stop_friday');
    if (recognition && recognition.abort) {
        recognition.abort(); // Para o reconhecimento de voz do navegador
    }
});

showCommandsButton.addEventListener('click', () => {
    socket.emit('get_commands_list');
});

// --- Socket.IO Event Handlers ---
socket.on('connect', () => {
    console.log('Conectado ao servidor Socket.IO');
});

socket.on('new_message', (data) => {
    appendMessage(data.sender, data.message, data.is_html);
    // Se a mensagem for do Friday, usa o TTS do navegador
    if (data.sender === 'FRIDAY' && data.message) {
        speakBrowser(data.message);
    }
});

socket.on('update_status', (data) => {
    updateStatus(data.status);
    if (data.status.includes('rodando')) {
        setFridayActive(true);
    } else if (data.status.includes('Inativo')) {
        setFridayActive(false);
    }
});

// Inicialização
setFridayActive(false); // Garante que comece desativado
toggleInput(false); // Desabilita input inicialmente