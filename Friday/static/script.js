// static/script.js
const socket = io(); // Conecta ao servidor Socket.IO
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const micButton = document.getElementById('micButton');
const startFridayButton = document.getElementById('startFriday');
const stopFridayButton = document.getElementById('stopFriday');
const showCommandsButton = document.getElementById('showCommands');
const statusTextSpan = document.getElementById('status-text'); // ID CORRIGIDO AQUI
const ledIndicator = document.getElementById('led-indicator'); // Adicionado para controlar o LED

let fridayActive = false;
let recognition; // Para a API de reconhecimento de voz do navegador
let isSpeaking = false; // Flag para controlar se Friday está falando

// --- Funções de Manipulação da Interface ---
function appendMessage(sender, message, isHtml = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    // Adiciona uma classe com o nome do remetente em minúsculas para estilização
    messageElement.classList.add(sender.toLowerCase().replace(' ', '-')); 

    const content = isHtml ? message : `${sender}: ${message}`;
    if (isHtml) {
        messageElement.innerHTML = content;
    } else {
        messageElement.textContent = content;
    }
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight; // Rola para o final
}

function updateStatus(status) {
    statusTextSpan.textContent = `Status: ${status}`; // Usa o span corrigido
    
    // Lógica para o LED
    if (status.toLowerCase().includes('rodando') ||
        status.toLowerCase().includes('ouvindo') ||
        status.toLowerCase().includes('processando') ||
        status.toLowerCase().includes('falando')) {
        ledIndicator.style.backgroundColor = 'green';
    } else {
        ledIndicator.style.backgroundColor = 'red';
    }
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
    toggleInput(active); // Habilita/desabilita input e microfone com base no estado do Friday
    
    if (!active) {
        updateStatus("Inativo.");
        // Também parar o TTS do navegador se Friday for desativado
        if (isSpeaking && speechSynthesis.speaking) {
            speechSynthesis.cancel();
            isSpeaking = false;
        }
    } else {
        // Se Friday acabou de ser ativado, o status será atualizado pelo backend
        // para "Olá, como posso ajudar?" e, em seguida, "Ouvindo..." ou "Pronto".
        // Não precisamos definir um status genérico aqui.
    }
}

// --- Funções de Reconhecimento de Voz do Navegador ---
function startSpeechRecognition() {
    if (!fridayActive) { // Só inicia se Friday estiver ativo
        console.log("Friday não está ativo. Não iniciando reconhecimento de voz.");
        return;
    }

    if (!('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
        alert('Seu navegador não suporta a API de Reconhecimento de Voz. Por favor, use Chrome ou Edge.');
        micButton.disabled = true;
        return;
    }

    // Se já estiver ouvindo, para
    if (recognition && recognition.abort) {
        recognition.abort(); 
    }
    
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'pt-BR';
    recognition.interimResults = false; // Queremos apenas resultados finais
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        console.log('Reconhecimento de voz iniciado...');
        micButton.classList.add('recording');
        micButton.textContent = '🔴 Gravando...'; // Mudar texto do botão
        updateStatus("Microfone ativo. Fale agora...");
        messageInput.disabled = true; // Desabilita input de texto enquanto ouve
        sendButton.disabled = true;
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        console.log('Reconhecido:', transcript);
        micButton.classList.remove('recording');
        micButton.textContent = '🎙️'; // Restaura texto do botão
        updateStatus("Voz reconhecida. Enviando...");
        // Envia o resultado para o servidor Python
        socket.emit('web_microphone_result', { text: transcript });
        // Os inputs serão reabilitados pelo update_status do backend, após processar o comando
    };

    recognition.onerror = (event) => {
        console.error('Erro no reconhecimento de voz:', event.error);
        micButton.classList.remove('recording');
        micButton.textContent = '🎙️'; // Restaura texto do botão
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
        micButton.textContent = '🎙️'; // Restaura texto do botão
        // O status e inputs serão atualizados pelo servidor após processar o comando
    };

    recognition.start();
}

// --- Funções de Fala da Friday no Navegador (Text-to-Speech) ---
function speakBrowser(text) {
    if (!('speechSynthesis' in window)) {
        console.warn('Seu navegador não suporta a API de Síntese de Fala.');
        return;
    }

    // Interrompe qualquer fala anterior para evitar sobreposição
    if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'pt-BR';
    utterance.rate = 1;
    utterance.pitch = 1;

    // Tenta encontrar uma voz em português do Brasil
    const voices = speechSynthesis.getVoices();
    const portugueseVoice = voices.find(voice => voice.lang === 'pt-BR' && voice.name.includes('Brazil'));
    if (portugueseVoice) {
        utterance.voice = portugueseVoice;
    } else {
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
        // O status voltará para "Pronto" ou "Ouvindo" pelo backend
    };

    utterance.onerror = (event) => {
        isSpeaking = false;
        console.error('Erro na síntese de fala:', event);
        if (fridayActive) { // Se Friday ainda estiver ativo, mostra erro
            updateStatus("Erro ao falar.");
        }
    };

    speechSynthesis.speak(utterance);
}

// Garante que as vozes estejam carregadas (assíncrono)
speechSynthesis.onvoiceschanged = () => {
    console.log("Vozes do navegador carregadas.");
};


// --- Event Listeners ---
sendButton.addEventListener('click', () => {
    const command = messageInput.value.trim();
    if (command && fridayActive) {
        // Envia o comando do usuário para o servidor
        socket.emit('send_command', { command: command });
        // Adiciona a mensagem do usuário ao chat imediatamente no frontend
        appendMessage('VOCÊ', command); 
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
    if (!fridayActive) { // Evita múltiplos cliques
        socket.emit('start_friday');
        appendMessage('SISTEMA', 'Iniciando Friday...'); // Feedback imediato
    }
});

stopFridayButton.addEventListener('click', () => {
    if (fridayActive) { // Evita múltiplos cliques
        socket.emit('stop_friday');
        appendMessage('SISTEMA', 'Parando Friday...'); // Feedback imediato
        if (recognition && recognition.abort) {
            recognition.abort(); // Para o reconhecimento de voz do navegador
        }
    }
});

showCommandsButton.addEventListener('click', () => {
    socket.emit('get_commands_list');
});

// --- Socket.IO Event Handlers ---
socket.on('connect', () => {
    console.log('Conectado ao servidor Socket.IO');
    updateStatus("Conectado. Pressione Iniciar para começar.");
    // Habilita o botão de iniciar apenas se não estiver ativo
    startFridayButton.disabled = fridayActive; 
});

socket.on('new_message', (data) => {
    // Adiciona a mensagem do servidor ao chat
    appendMessage(data.sender, data.message, data.is_html);
    
    // Se a mensagem for do Friday, usa o TTS do navegador
    if (data.sender === 'FRIDAY' && data.message) {
        speakBrowser(data.message);
    }
});

socket.on('update_status', (data) => {
    updateStatus(data.status); // Atualiza o texto e o LED
    if (data.status.toLowerCase().includes('rodando') || data.status.toLowerCase().includes('iniciando friday')) {
        setFridayActive(true);
    } else if (data.status.toLowerCase().includes('inativo') || data.status.toLowerCase().includes('parando')) {
        setFridayActive(false);
    }
});

// Inicialização
setFridayActive(false); // Garante que comece desativado e os inputs bloqueados
updateStatus("Carregando..."); // Status inicial enquanto espera a conexão
