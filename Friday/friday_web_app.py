# friday_web_app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import queue
import sys
import os

# Importa o Friday_Master como o core da assistente
try:
    import Friday_Master as assistant_core
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'Friday_Master.py'. "
          "Certifique-se de que ele está no mesmo diretório.")
    sys.exit(1)

app = Flask(__name__)
# Para desenvolvimento, permita qualquer origem. Em produção, restrinja.
app.config['SECRET_KEY'] = 'your_secret_key' # Mude isso para uma chave secreta real
socketio = SocketIO(app, cors_allowed_origins="*")

# Variáveis para gerenciar o loop da assistente e a comunicação
assistant_thread = None
running_assistant = False
speech_recognition_thread = None # Thread para reconhecimento de voz do microfone local

# Fila para comandos de texto vindos do navegador
web_input_queue = queue.Queue()
# Fila para armazenar o resultado da escuta da web (seja microfone ou texto)
web_listen_result_queue = queue.Queue()


# --- Funções de Callback para o Friday_Master.py ---
def web_speak_callback_impl(text, sender_type="FRIDAY"):
    """Emite mensagens para o frontend via SocketIO."""
    socketio.emit('new_message', {'sender': sender_type, 'message': text, 'is_html': False}, namespace='/')
    # Opcional: para Friday falar também localmente no servidor
    # assistant_core.speak_original(text) 

def web_listen_callback_impl(timeout=5, phrase_time_limit=6):
    """Aguarda por um comando do navegador (texto digitado ou microfone do navegador)."""
    # Emite um status para o navegador indicando que está aguardando input
    socketio.emit('update_status', {'status': 'Ouvindo...'}, namespace='/')

    try:
        # Bloqueia até que um comando seja colocado na fila pelo frontend
        command = web_listen_result_queue.get(timeout=timeout + phrase_time_limit)
        return command
    except queue.Empty:
        # Se o tempo limite for atingido sem nenhum input, retorna vazio
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Tempo limite de escuta atingido. Nenhuma entrada.', 'is_html': False}, namespace='/')
        return ""

def web_update_status_callback_impl(status_text):
    """Atualiza o status na interface web."""
    socketio.emit('update_status', {'status': status_text}, namespace='/')

# --- Funções para gerenciar o loop principal da assistente ---
def running_assistant_checker():
    """Função que o main_loop_with_web_interface chamará para verificar se deve continuar rodando."""
    return running_assistant

def run_friday_loop():
    global running_assistant

    # Sobrescreve os callbacks no Friday_Master
    assistant_core.web_speak_callback = web_speak_callback_impl
    assistant_core.web_listen_callback = web_listen_callback_impl
    assistant_core.web_update_status_callback = web_update_status_callback_impl

    assistant_core.main_loop_with_web_interface(running_assistant_checker)
    web_speak_callback_impl("Friday encerrado.", "SISTEMA")
    web_update_status_callback_impl("Inativo")
    running_assistant = False # Garante que a flag seja redefinida

# --- Rotas Flask ---
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    print('Cliente conectado ao SocketIO')
    emit('new_message', {'sender': 'SISTEMA', 'message': 'Bem-vindo ao Friday Web Assistant!', 'is_html': False}, namespace='/')
    if running_assistant:
        emit('update_status', {'status': 'Friday rodando...'}, namespace='/')
    else:
        emit('update_status', {'status': 'Inativo. Pressione Iniciar para começar.'}, namespace='/')

@socketio.on('disconnect')
def test_disconnect():
    print('Cliente desconectado do SocketIO')

@socketio.on('start_friday')
def start_friday_from_web():
    global running_assistant, assistant_thread
    if not running_assistant:
        running_assistant = True
        web_speak_callback_impl("Iniciando Friday. Olá, como posso ajudar?", "SISTEMA")
        web_update_status_callback_impl("Iniciando Friday...")
        assistant_thread = threading.Thread(target=run_friday_loop)
        assistant_thread.daemon = True # Permite que a thread termine com o aplicativo Flask
        assistant_thread.start()
        web_update_status_callback_impl("Friday rodando...")
    else:
        web_speak_callback_impl("Friday já está ativo.", "SISTEMA")

@socketio.on('stop_friday')
def stop_friday_from_web():
    global running_assistant
    if running_assistant:
        running_assistant = False
        web_speak_callback_impl("Parando Friday...", "SISTEMA")
        web_update_status_callback_impl("Parando...")
        # A thread da assistente vai sair do loop quando verificar a flag `running_assistant`
    else:
        web_speak_callback_impl("Friday não está ativo para parar.", "SISTEMA")

@socketio.on('send_command')
def handle_command_from_web(data):
    """Recebe um comando de texto digitado pelo usuário na interface web."""
    command = data['command'].lower()
    if command:
        emit('new_message', {'sender': 'VOCÊ', 'message': command, 'is_html': False}, namespace='/')
        web_listen_result_queue.put(command) # Coloca o comando na fila para o Friday_Master
        web_update_status_callback_impl("Comando recebido. Processando...")
    else:
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhum comando enviado.', 'is_html': False}, namespace='/')

@socketio.on('web_microphone_result')
def handle_web_microphone_result(data):
    """Recebe o texto reconhecido do microfone do navegador."""
    recognized_text = data['text'].lower()
    if recognized_text:
        emit('new_message', {'sender': 'VOCÊ', 'message': f"🎙️ {recognized_text}", 'is_html': False}, namespace='/')
        web_listen_result_queue.put(recognized_text) # Coloca o texto na fila para o Friday_Master
        web_update_status_callback_impl("Voz recebida do navegador. Processando...")
    else:
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhuma fala detectada pelo microfone do navegador.', 'is_html': False}, namespace='/')

@socketio.on('get_commands_list')
def get_commands_list_from_web():
    commands_html = assistant_core.print_commands_list().replace('\n', '<br>')
    emit('new_message', {'sender': 'SISTEMA', 'message': commands_html, 'is_html': True}, namespace='/')


if __name__ == '__main__':
    print("Iniciando o servidor Flask-SocketIO. Abra seu navegador em http://127.0.0.1:5000")
    # Autentica Spotify no início do web app em uma thread separada para não bloquear
    threading.Thread(target=assistant_core.authenticate_spotify).start()
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug para host 0.0.0.0