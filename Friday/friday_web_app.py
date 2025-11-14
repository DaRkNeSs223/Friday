# --- START OF FILE friday_web_app.py ---

# friday_web_app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import queue
import sys
import os
import webbrowser 

try:
    import Friday_Master as assistant_core
except ImportError:
    print("ERRO: Não foi possível encontrar o arquivo 'Friday_Master.py'. "
          "Certifique-se de que ele está no mesmo diretório.")
    sys.exit(1)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

assistant_thread = None
running_assistant = False
speech_recognition_thread = None

web_input_queue = queue.Queue()
web_listen_result_queue = queue.Queue()

# --- Funções de Callback para o Friday_Master.py ---
def web_speak_callback_impl(text, sender_type="FRIDAY"):
    # Esta função EMITE mensagens para o chat da web
    socketio.emit('new_message', {'sender': sender_type, 'message': text, 'is_html': False}, namespace='/')

def web_listen_callback_impl(timeout=5, phrase_time_limit=6):
    # Indica que a assistente está ouvindo na interface
    socketio.emit('update_status', {'status': 'Ouvindo...'}, namespace='/')
    socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Aguardando sua fala...', 'is_html': False}, namespace='/')

    try:
        command = web_listen_result_queue.get(timeout=timeout + phrase_time_limit)
        # Ao receber um comando, mostramos o que o usuário disse no chat
        if command:
            # Emitir o comando do usuário ANTES da resposta do Friday para melhor UX
            socketio.emit('new_message', {'sender': 'VOCÊ', 'message': f"Você disse: {command}", 'is_html': False}, namespace='/')
            return command
        else:
            socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhuma fala detectada ou tempo limite atingido.', 'is_html': False}, namespace='/')
            return "" # Retorna string vazia para o Friday_Master lidar com isso
    except queue.Empty:
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Tempo limite de escuta atingido. Nenhuma entrada.', 'is_html': False}, namespace='/')
        return "" # Retorna string vazia para o Friday_Master lidar com isso

def web_update_status_callback_impl(status_text):
    # Esta função EMITE o status para a interface da web
    socketio.emit('update_status', {'status': status_text}, namespace='/')

# --- Funções para gerenciar o loop principal da assistente ---
def running_assistant_checker():
    return running_assistant

def run_friday_loop():
    global running_assistant

    # Configura os callbacks para a interface web
    assistant_core.web_speak_callback = web_speak_callback_impl
    assistant_core.web_listen_callback = web_listen_callback_impl
    assistant_core.web_update_status_callback = web_update_status_callback_impl

    # Calibração do microfone
    try:
        # A mensagem de calibração agora usa speak(), então aparecerá no chat/status
        assistant_core.speak("Calibrando o microfone para o ruído ambiente, por favor aguarde...", "SISTEMA")
        assistant_core.update_status("Calibrando microfone...")
        with assistant_core.sr.Microphone() as source:
            assistant_core.r.adjust_for_ambient_noise(source, duration=1.5)
        assistant_core.speak("Microfone calibrado.", "SISTEMA")
        assistant_core.update_status("Microfone calibrado")
    except Exception as e:
        # Erros aqui são importantes para o console do servidor Flask
        print(f"ERRO DE INICIALIZAÇÃO DO MICROFONE (web_app): {e}") 
        assistant_core.speak(f"Não foi possível inicializar o microfone: {e}. Funcionalidades de voz podem não funcionar.", "ERRO")
        assistant_core.update_status("Erro no microfone")


    # Autenticação do Spotify
    assistant_core.speak("Autenticando Spotify em segundo plano...", "SISTEMA")
    assistant_core.update_status("Autenticando Spotify...")
    threading.Thread(target=assistant_core.authenticate_spotify).start()
    # A mensagem "Conectado ao Spotify" virá via speak() dentro de authenticate_spotify, indo para o chat.

    assistant_core.main_loop_with_web_interface(running_assistant_checker)
    
    assistant_core.speak("Friday encerrado.", "SISTEMA")
    assistant_core.update_status("Inativo")
    running_assistant = False


# --- Rotas Flask ---
@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def test_connect():
    print('Cliente conectado ao SocketIO (console)') # Esta mensagem ainda irá para o terminal
    emit('new_message', {'sender': 'SISTEMA', 'message': 'Bem-vindo ao Friday Web Assistant!', 'is_html': False}, namespace='/')
    
    if running_assistant:
        emit('update_status', {'status': 'Friday rodando...'}, namespace='/')
    else:
        emit('update_status', {'status': 'Inativo. Pressione Iniciar para começar.'}, namespace='/')

@socketio.on('disconnect')
def test_disconnect():
    print('Cliente desconectado do SocketIO (console)') # Esta mensagem ainda irá para o terminal

@socketio.on('start_friday')
def start_friday_from_web():
    global running_assistant, assistant_thread
    if not running_assistant:
        running_assistant = True
        # As mensagens de início agora são delegadas ao Friday_Master via speak/update_status
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Iniciando Friday...', 'is_html': False}, namespace='/')
        socketio.emit('update_status', {'status': 'Iniciando Friday...'}, namespace='/')
        assistant_thread = threading.Thread(target=run_friday_loop)
        assistant_thread.daemon = True
        assistant_thread.start()
    else:
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Friday já está ativo.', 'is_html': False}, namespace='/')

@socketio.on('stop_friday')
def stop_friday_from_web():
    global running_assistant
    if running_assistant:
        running_assistant = False
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Parando Friday...', 'is_html': False}, namespace='/')
        socketio.emit('update_status', {'status': 'Parando...'}, namespace='/')
    else:
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Friday não está ativo para parar.', 'is_html': False}, namespace='/')

@socketio.on('send_command')
def handle_command_from_web(data):
    command = data['command'].lower()
    if command:
        # Coloca o comando na fila para o Friday_Master. O callback web_listen_callback_impl 
        # será responsável por exibir o que o usuário disse no chat.
        web_listen_result_queue.put(command)
        web_update_status_callback_impl("Comando recebido. Processando...")
    else:
        # Esta é uma mensagem de erro/info do sistema para o chat
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhum comando enviado.', 'is_html': False}, namespace='/')

@socketio.on('web_microphone_result')
def handle_web_microphone_result(data):
    recognized_text = data['text'].lower()
    if recognized_text:
        # Coloca o resultado do microfone na fila. O callback web_listen_callback_impl 
        # será responsável por exibir o que o usuário disse no chat.
        web_listen_result_queue.put(recognized_text)
        web_update_status_callback_impl("Voz recebida do navegador. Processando...")
    else:
        # Esta é uma mensagem de erro/info do sistema para o chat
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhuma fala detectada pelo microfone do navegador.', 'is_html': False}, namespace='/')

@socketio.on('get_commands_list')
def get_commands_list_from_web():
    commands_text = assistant_core.print_commands_list()
    commands_html = commands_text.replace('\n', '<br>') 
    # Esta é uma mensagem de info para o chat
    emit('new_message', {'sender': 'COMANDOS', 'message': commands_html, 'is_html': True}, namespace='/')


if __name__ == '__main__':
    print("Iniciando o servidor Flask-SocketIO. Abrindo seu navegador em http://127.0.0.1:5000 (console)") # Este print é ok no terminal
    
    def open_browser_after_delay():
        time.sleep(3) 
        webbrowser.open("http://127.0.0.1:5000")
        print("Interface web aberta automaticamente. (console)") # Este print é ok no terminal

    threading.Thread(target=open_browser_after_delay).start()
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
