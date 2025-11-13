# friday_web_app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import queue
import sys
import os
import webbrowser # Importado para abrir automaticamente

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
    socketio.emit('new_message', {'sender': sender_type, 'message': text, 'is_html': False}, namespace='/')

def web_listen_callback_impl(timeout=5, phrase_time_limit=6):
    socketio.emit('update_status', {'status': 'Ouvindo...'}, namespace='/')

    try:
        command = web_listen_result_queue.get(timeout=timeout + phrase_time_limit)
        return command
    except queue.Empty:
        socketio.emit('new_message', {'sender': 'SISTEMA', 'message': 'Tempo limite de escuta atingido. Nenhuma entrada.', 'is_html': False}, namespace='/')
        return ""

def web_update_status_callback_impl(status_text):
    socketio.emit('update_status', {'status': status_text}, namespace='/')

# --- Funções para gerenciar o loop principal da assistente ---
def running_assistant_checker():
    return running_assistant

def run_friday_loop():
    global running_assistant

    assistant_core.web_speak_callback = web_speak_callback_impl
    assistant_core.web_listen_callback = web_listen_callback_impl
    assistant_core.web_update_status_callback = web_update_status_callback_impl

    assistant_core.main_loop_with_web_interface(running_assistant_checker)
    
    web_speak_callback_impl("Friday encerrado.", "SISTEMA")
    web_update_status_callback_impl("Inativo")
    running_assistant = False


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
        assistant_thread.daemon = True
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
    else:
        web_speak_callback_impl("Friday não está ativo para parar.", "SISTEMA")

@socketio.on('send_command')
def handle_command_from_web(data):
    command = data['command'].lower()
    if command:
        emit('new_message', {'sender': 'VOCÊ', 'message': command, 'is_html': False}, namespace='/')
        web_listen_result_queue.put(command)
        web_update_status_callback_impl("Comando recebido. Processando...")
    else:
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhum comando enviado.', 'is_html': False}, namespace='/')

@socketio.on('web_microphone_result')
def handle_web_microphone_result(data):
    recognized_text = data['text'].lower()
    if recognized_text:
        emit('new_message', {'sender': 'VOCÊ', 'message': f"🎙️ {recognized_text}", 'is_html': False}, namespace='/')
        web_listen_result_queue.put(recognized_text)
        web_update_status_callback_impl("Voz recebida do navegador. Processando...")
    else:
        emit('new_message', {'sender': 'SISTEMA', 'message': 'Nenhuma fala detectada pelo microfone do navegador.', 'is_html': False}, namespace='/')

@socketio.on('get_commands_list')
def get_commands_list_from_web():
    commands_text = assistant_core.print_commands_list()
    commands_html = commands_text.replace('\n', '<br>') 
    emit('new_message', {'sender': 'COMANDOS', 'message': commands_html, 'is_html': True}, namespace='/')


if __name__ == '__main__':
    print("Iniciando o servidor Flask-SocketIO. Abra seu navegador em http://127.0.0.1:5000")
    
    # Abre a interface web automaticamente em uma thread separada
    def open_browser_after_delay():
        time.sleep(3) # Dá um tempo para o servidor Flask iniciar
        webbrowser.open("http://127.0.0.1:5000")
        print("Interface web aberta automaticamente.")

    threading.Thread(target=open_browser_after_delay).start()
    
    # Autentica Spotify no início do web app em uma thread separada para não bloquear
    threading.Thread(target=assistant_core.authenticate_spotify).start()
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
