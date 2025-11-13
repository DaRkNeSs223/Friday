# friday_gui.py
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import sys
import os
import time
import webbrowser # Importado para abrir o navegador

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
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Frame para o status e o indicador de LED
        status_frame = tk.Frame(master, bg="#282C34")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = tk.Label(status_frame, text="Status: Aguardando...", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg="#282C34", fg="#ABB2BF")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Canvas para o indicador de LED (círculo)
        self.led_canvas = tk.Canvas(status_frame, width=20, height=20, bg="#282C34", highlightthickness=0)
        self.led_canvas.pack(side=tk.RIGHT, padx=5, pady=2)
        self.led_indicator = self.led_canvas.create_oval(5, 5, 15, 15, outline="gray", fill="red") # Começa vermelho (offline)

        self.text_area = scrolledtext.ScrolledText(master, wrap=tk.WORD, state='disabled', font=("Arial", 12), bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.text_area.tag_config("FRIDAY", foreground="#61AFEF")
        self.text_area.tag_config("VOCÊ", foreground="#98C379")
        self.text_area.tag_config("SISTEMA", foreground="#C678DD")
        self.text_area.tag_config("ERRO", foreground="#E06C75")
        self.text_area.tag_config("COMANDOS", foreground="#E5C07B")
        self.text_area.pack(expand=True, fill="both", padx=10, pady=10)

        self.create_buttons()

        self.assistant_thread = None
        self.running_assistant = False

        sys.stdout = TextRedirector(self.text_area, "STDOUT")
        sys.stderr = TextRedirector(self.text_area, "ERRO")

        self.update_gui_text("Friday Assistant iniciado. Pressione 'Iniciar Friday' para começar.", "SISTEMA")
        self.master.update_idletasks()

        self.update_gui_text("Autenticando Spotify em segundo plano...", "SISTEMA")
        threading.Thread(target=assistant_core.authenticate_spotify).start()

        # Abrir a interface web automaticamente
        self.open_web_app_automatically()


    def create_buttons(self):
        button_frame = tk.Frame(self.master, bg="#282C34")
        button_frame.pack(pady=5)

        self.start_button = tk.Button(button_frame, text="Iniciar Friday", command=self.start_friday, font=("Arial", 12), bg="#4CAF50", fg="white", activebackground="#45a049", activeforeground="white")
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(button_frame, text="Parar Friday", command=self.stop_friday, font=("Arial", 12), bg="#f44336", fg="white", state=tk.DISABLED, activebackground="#da190b", activeforeground="white")
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.commands_button = tk.Button(button_frame, text="Mostrar Comandos", command=self.show_commands_list, font=("Arial", 12), bg="#5C6370", fg="white", activebackground="#495057", activeforeground="white")
        self.commands_button.pack(side=tk.LEFT, padx=5)

        # Botão para abrir a interface web
        self.open_web_button = tk.Button(button_frame, text="Abrir Web App", command=self.open_web_app, font=("Arial", 12), bg="#5D8AA8", fg="white", activebackground="#4A759C", activeforeground="white")
        self.open_web_button.pack(side=tk.LEFT, padx=5)


    def update_gui_text(self, message, sender="SISTEMA"):
        self.master.after(0, self._actual_update_text, message, sender)

    def _actual_update_text(self, message, sender):
        self.text_area.config(state='normal')
        if self.text_area.index(tk.END).count('\n') > 1000:
            start_index = self.text_area.index("1.0 + 100 lines")
            self.text_area.delete("1.0", start_index)
        self.text_area.insert(tk.END, f"\n[{sender}] {message}", sender)
        self.text_area.config(state='disabled')
        self.text_area.see(tk.END)

    def update_status(self, status_text):
        self.master.after(0, self._actual_update_status, status_text)

    def _actual_update_status(self, status_text):
        self.status_label.config(text=f"Status: {status_text}")
        if "rodando" in status_text.lower() or "ouvindo" in status_text.lower() or "processando" in status_text.lower() or "falando" in status_text.lower():
            self.led_canvas.itemconfig(self.led_indicator, fill="green")
        else:
            self.led_canvas.itemconfig(self.led_indicator, fill="red")


    def speak_in_gui(self, text, lang='pt'):
        self.update_gui_text(text, sender="FRIDAY")
        self.update_status("Falando...")
        assistant_core.speak_original(text, lang)

    def listen_in_gui(self, timeout=5, phrase_time_limit=6):
        self.update_gui_text("Ouvindo... (Diga 'Friday' ou um comando)", sender="VOCÊ")
        self.update_status("Ouvindo...")
        recognized_text = assistant_core.listen_original(timeout, phrase_time_limit)
        if recognized_text:
            self.update_gui_text(f"Você disse: {recognized_text}", sender="VOCÊ")
        else:
            self.update_gui_text("Não entendi ou nenhuma fala detectada.", sender="VOCÊ")
        self.update_status("Processando...")
        return recognized_text

    def start_friday(self):
        if not self.running_assistant:
            self.running_assistant = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_gui_text("Iniciando o loop principal da assistente...", "SISTEMA")
            self.assistant_thread = threading.Thread(target=self.run_friday_loop)
            self.assistant_thread.daemon = True
            self.assistant_thread.start()
            self.update_status("Friday rodando...")

    def stop_friday(self):
        if self.running_assistant:
            self.running_assistant = False
            self.update_gui_text("Solicitando parada da assistente...", "SISTEMA")
            self.update_status("Parando...")
            self.master.after(100, self._finalize_stop_ui)

    def _finalize_stop_ui(self):
        if not self.running_assistant and (not self.assistant_thread or not self.assistant_thread.is_alive()):
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.update_status("Inativo")
        else:
            self.master.after(100, self._finalize_stop_ui)

    def run_friday_loop(self):
        assistant_core.gui_speak_callback = self.speak_in_gui
        assistant_core.gui_listen_callback = self.listen_in_gui
        assistant_core.gui_update_status_callback = self.update_status

        assistant_core.main_loop_with_gui(self.running_assistant_checker)
        
        self.master.after(0, self.update_gui_text, "Friday encerrado.", "SISTEMA")
        self.master.after(0, self.update_status, "Inativo") # Garante que o LED fique vermelho
        self.running_assistant = False
        self.master.after(0, lambda: self.start_button.config(state=tk.NORMAL))
        self.master.after(0, lambda: self.stop_button.config(state=tk.DISABLED))


    def running_assistant_checker(self):
        return self.running_assistant

    def show_commands_list(self):
        commands_text = assistant_core.print_commands_list()
        self.update_gui_text(commands_text, "COMANDOS")

    def open_web_app(self):
        webbrowser.open("http://127.0.0.1:5000")
        self.update_gui_text("Abrindo a interface web em http://127.0.0.1:5000", "SISTEMA")

    def open_web_app_automatically(self):
        # Abre a interface web em uma thread separada para não bloquear a GUI
        threading.Thread(target=self._delayed_open_web_app).start()

    def _delayed_open_web_app(self):
        time.sleep(2) # Pequeno atraso para dar tempo ao servidor Flask iniciar
        self.open_web_app()


    def on_closing(self):
        if self.running_assistant:
            if messagebox.askokcancel("Sair do Friday", "O Friday está ativo. Deseja realmente sair?"):
                self.stop_friday()
                self.master.after(500, self._try_destroy_after_stop)
        else:
            self.master.destroy()

    def _try_destroy_after_stop(self):
        if self.assistant_thread and self.assistant_thread.is_alive():
            self.master.after(500, self._try_destroy_after_stop)
        else:
            self.master.destroy()

class TextRedirector(object):
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag

    def write(self, str_to_write):
        if str_to_write and str_to_write.strip():
            self.widget.config(state='normal')
            self.widget.insert(tk.END, str_to_write, (self.tag,))
            self.widget.config(state='disabled')
            self.widget.see(tk.END)

    def flush(self):
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = FridayGUI(root)
    root.mainloop()
