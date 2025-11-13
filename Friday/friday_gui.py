# friday_gui.py
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import sys
import os
import time # Adicionado para time.sleep()

# Este import tentará carregar o seu arquivo Friday_Master.py
# Certifique-se de que Friday_Master.py esteja no mesmo diretório
try:
    import Friday_Master as assistant_core
except ImportError:
    messagebox.showerror("Erro de Importação",
                         "Não foi possível encontrar o arquivo 'Friday_Master.py'. "
                         "Certifique-se de que ele está no mesmo diretório e não tem erros de sintaxe.")
    sys.exit(1)

class FridayGUI:
    def __init__(self, master):
        self.master = master
        master.title("Friday Assistant")
        master.geometry("800x600")
        master.protocol("WM_DELETE_WINDOW", self.on_closing) # Para lidar com o fechamento da janela

        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, state='disabled', font=("Arial", 12), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.text_area.tag_config("FRIDAY", foreground="#61AFEF") # Azul claro
        self.text_area.tag_config("VOCÊ", foreground="#98C379")   # Verde claro
        self.text_area.tag_config("SISTEMA", foreground="#C678DD") # Roxo
        self.text_area.tag_config("ERRO", foreground="#E06C75")    # Vermelho
        self.text_area.tag_config("COMANDOS", foreground="#E5C07B") # Amarelo
        self.text_area.pack(expand=True, fill="both", padx=10, pady=10)

        self.status_label = tk.Label(master, text="Status: Aguardando...", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#282C34", fg="#ABB2BF")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.create_buttons()

        self.assistant_thread = None
        self.running_assistant = False # Flag para controlar o loop da assistente

        # Redirecionar os prints do console para a GUI também
        sys.stdout = TextRedirector(self.text_area, "STDOUT")
        sys.stderr = TextRedirector(self.text_area, "ERRO")


        self.update_gui_text("Friday Assistant iniciado. Pressione 'Iniciar Friday' para começar.", "SISTEMA")
        self.master.update_idletasks() # Atualiza a GUI imediatamente

        # Inicializa o Spotify no início, para que o token seja gerado antes
        # e para evitar que a janela congele durante a autenticação
        self.update_gui_text("Autenticando Spotify em segundo plano...", "SISTEMA")
        threading.Thread(target=assistant_core.authenticate_spotify).start()


    def create_buttons(self):
        button_frame = tk.Frame(self.master, bg="#282C34")
        button_frame.pack(pady=5)

        self.start_button = tk.Button(button_frame, text="Iniciar Friday", command=self.start_friday, font=("Arial", 12), bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white")
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(button_frame, text="Parar Friday", command=self.stop_friday, font=("Arial", 12), bg="#f44336", fg="white", state=tk.DISABLED, activebackground="#da190b", activeforeground="white")
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.commands_button = tk.Button(button_frame, text="Mostrar Comandos", command=self.show_commands_list, font=("Arial", 12), bg="#5C6370", fg="white", activebackground="#495057", activeforeground="white")
        self.commands_button.pack(side=tk.LEFT, padx=5)


    def update_gui_text(self, message, sender="SISTEMA"):
        # Garante que a atualização da GUI ocorra na thread principal
        self.master.after(0, self._actual_update_text, message, sender)

    def _actual_update_text(self, message, sender):
        self.text_area.config(state='normal')
        # Limita o tamanho para evitar sobrecarga de memória em longas conversas
        if self.text_area.index(tk.END).count('\n') > 1000: # Mantém ~1000 linhas
            start_index = self.text_area.index("1.0 + 100 lines")
            self.text_area.delete("1.0", start_index)
        self.text_area.insert(tk.END, f"\n[{sender}] {message}", sender) # Usa o sender como tag para cor
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END) # Rola para o final

    def update_status(self, status_text):
        self.master.after(0, self._actual_update_status, status_text)

    def _actual_update_status(self, status_text):
        self.status_label.config(text=f"Status: {status_text}")

    # Funções de speak e listen que a GUI irá usar e que serão "injetadas" no Friday_Master
    def speak_in_gui(self, text, lang='pt'):
        self.update_gui_text(text, sender="FRIDAY")
        self.update_status("Falando...")
        assistant_core.speak_original(text, lang) # Chama a função original de fala
        self.update_status("Pronto para o próximo comando")

    def listen_in_gui(self, timeout=5, phrase_time_limit=6):
        self.update_gui_text("Ouvindo... (Diga 'Friday' ou um comando)", sender="VOCÊ")
        self.update_status("Ouvindo...")
        recognized_text = assistant_core.listen_original(timeout, phrase_time_limit) # Chama a função original de escuta
        if recognized_text:
            self.update_gui_text(f"Você disse: {recognized_text}", sender="VOCÊ")
        else:
            self.update_gui_text("Não entendi ou nenhuma fala detectada.", sender="VOCÊ")
        self.update_status("Processando...") # Estado de reconhecimento, antes de executar o comando
        return recognized_text

    def start_friday(self):
        if not self.running_assistant:
            self.running_assistant = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_gui_text("Iniciando o loop principal da assistente...", "SISTEMA")
            self.assistant_thread = threading.Thread(target=self.run_friday_loop)
            self.assistant_thread.daemon = True # Permite que a thread termine com a janela
            self.assistant_thread.start()
            self.update_status("Friday rodando...")

    def stop_friday(self):
        if self.running_assistant:
            self.running_assistant = False
            # Damos um pequeno tempo para a thread principal verificar a flag
            # Antes de re-habilitar os botões.
            self.update_gui_text("Solicitando parada da assistente...", "SISTEMA")
            self.update_status("Parando...")
            # Não atualiza os botões imediatamente para dar tempo à thread
            self.master.after(1000, self._check_thread_and_update_buttons)


    def _check_thread_and_update_buttons(self):
        if self.assistant_thread and self.assistant_thread.is_alive():
            # Se ainda estiver rodando, tenta de novo ou mostra um erro.
            # Por simplicidade, vamos apenas esperar um pouco mais ou forçar.
            messagebox.showwarning("Parada em Andamento", "A assistente ainda está processando. Por favor, aguarde um momento.")
            self.master.after(500, self._check_thread_and_update_buttons) # Tenta novamente
        else:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status("Inativo")


    def run_friday_loop(self):
        # Sobrescreve as funções speak e listen do módulo assistant_core
        # para que elas usem as funções da GUI.
        assistant_core.gui_speak_callback = self.speak_in_gui
        assistant_core.gui_listen_callback = self.listen_in_gui

        # Chama o loop principal da assistente, passando a função que verifica a flag
        assistant_core.main_loop_with_gui(self.running_assistant_checker)
        self.update_gui_text("Friday encerrado.", "SISTEMA")
        self.update_status("Inativo")
        self.running_assistant = False
        # Garante que os botões sejam atualizados na thread principal do Tkinter
        self.master.after(0, lambda: self.start_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.stop_button.config(state=tk.DISABLED))


    def running_assistant_checker(self):
        """Função que o main_loop_with_gui chamará para verificar se deve continuar rodando."""
        return self.running_assistant

    def show_commands_list(self):
        # Chama a função do Friday_Master que retorna a string de comandos
        commands_text = assistant_core.print_commands_list()
        self.update_gui_text(commands_text, "COMANDOS")


    def on_closing(self):
        if self.running_assistant:
            if messagebox.askokcancel("Sair do Friday", "O Friday está ativo. Deseja realmente sair?"):
                self.stop_friday() # Tenta parar a assistente de forma limpa
                # Dá um pequeno tempo para a thread processar o desligamento
                if self.assistant_thread and self.assistant_thread.is_alive():
                    # Isso pode bloquear a GUI se a assistente demorar a parar.
                    # Idealmente, o loop deve sair rápido ao ver a flag `running_assistant` False.
                    self.assistant_thread.join(timeout=2)
                self.master.destroy()
        else:
            self.master.destroy()

# Para redirecionar os prints do console para a GUI
class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_to_write):
        # Apenas insere se a string não for vazia e não for apenas uma nova linha
        if str_to_write and str_to_write.strip():
            self.widget.config(state='normal')
            self.widget.insert(tk.END, str_to_write, (self.tag,))
            self.widget.config(state='disabled')
            self.widget.see(tk.END)

    def flush(self):
        pass # Necessário para objetos que se comportam como arquivos

if __name__ == "__main__":
    root = tk.Tk()
    app = FridayGUI(root)
    root.mainloop()