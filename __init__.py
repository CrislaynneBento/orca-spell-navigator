from gi.repository import GObject, Pluma, Gtk, Gdk
import subprocess

class OrcaSpellPlugin(GObject.Object, Pluma.WindowActivatable):
    __gtype_name__ = "OrcaSpellPlugin"
    window = GObject.Property(type=Pluma.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self.erros = []
        self.indice = 0
        self.handler_id = 0 # Guarda a referência do evento de teclado

    def do_activate(self):
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("do_activate chamado!\n")
        
        try:
            # Avisa o usuário (agora protegido contra falhas de áudio)
            self.orca_fala("Plugin OrcaSpell ativado.")
            
            # Conecta os atalhos diretamente na janela do Pluma (Funciona em X11 e Wayland)
            self.handler_id = self.window.connect("key-press-event", self.on_key_press)
            
            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalhos nativos do GTK ativados com sucesso!\n")
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"ERRO ao ativar o plugin: {e}\n")

    def do_deactivate(self):
        # Desconecta o evento ao desativar o plugin para liberar memória
        if self.handler_id and self.window:
            self.window.disconnect(self.handler_id)
            self.handler_id = 0
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("Plugin desativado.\n")

    def do_update_state(self):
        pass

    def on_key_press(self, window, event):
        """Gerenciador de atalhos nativo do GTK corrigido para Shift"""
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        
        nome_tecla = Gdk.keyval_name(event.keyval)
        with open("/tmp/orcaspell.log", "a") as f:
            f.write(f"Tecla pressionada no Pluma: {nome_tecla} (Modificador: {state})\n")
        
        # Opção 1: Ctrl + F8 (Caso o sistema libere a tecla)
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.KEY_F8:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalho Ctrl+F8 acionado com sucesso!\n")
            self.iniciar_revisao(None)
            return True
            
        # Opção 2: Ctrl + Shift + H (Corrigido para KEY_H maiúsculo)
        alvo_mod = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if state == alvo_mod and event.keyval == Gdk.KEY_H:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalho alternativo Ctrl+Shift+H acionado com sucesso!\n")
            self.iniciar_revisao(None)
            return True
            
        # Alt + N -> Próximo Erro (Aqui continua minúsculo pois não usa Shift)
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_n:
            self.proximo_erro(None)
            return True
            
        # Alt + P -> Erro Anterior
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_p:
            self.erro_anterior(None)
            return True
            
        return False

    def orca_fala(self, texto):
        try:
            subprocess.Popen(["spd-say", "-l", "pt", texto])
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro ao executar spd-say: {e}\n")

    def obter_texto(self):
        doc = self.window.get_active_document()
        if not doc:
            return ""
        inicio = doc.get_start_iter()
        fim = doc.get_end_iter()
        return doc.get_text(inicio, fim, True)

    def iniciar_revisao(self, action):
        try:
            texto = self.obter_texto()
            if not texto.strip():
                self.orca_fala("O documento está vazio.")
                return

            resultado = subprocess.run(
                ["hunspell", "-d", "pt_BR", "-l"],
                input=texto, capture_output=True, text=True, check=True
            )

            palavras_erradas = list(set(
                p.strip() for p in resultado.stdout.strip().split("\n") if p.strip()
            ))

            if not palavras_erradas:
                self.orca_fala("Nenhum erro ortográfico encontrado.")
                return

            self.erros = []
            for palavra in palavras_erradas:
                inicio = 0
                while True:
                    pos = texto.find(palavra, inicio)
                    if pos == -1:
                        break
                    self.erros.append({"palavra": palavra, "posicao": pos})
                    inicio = pos + len(palavra)

            self.erros.sort(key=lambda x: x["posicao"])
            self.indice = 0
            self.orca_fala(f"{len(self.erros)} erros encontrados. Pressione Alt N para o primeiro.")
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro em iniciar_revisao: {e}\n")
            self.orca_fala("Erro interno ao iniciar a revisão do Hunspell.")

    def anunciar_erro_atual(self):
        if not self.erros:
            self.orca_fala("Nenhum erro para navegar.")
            return
        erro = self.erros[self.indice]
        palavra = erro["palavra"]

        try:
            resultado = subprocess.run(
                ["hunspell", "-d", "pt_BR"],
                input=palavra, capture_output=True, text=True, check=True
            )
            sugestao = "sem sugestão"
            for linha in resultado.stdout.split("\n"):
                if linha.startswith("&"):
                    partes = linha.split(":")
                    if len(partes) > 1:
                        sugestao = partes[1].strip().split(",")[0].strip()
                        break

            self.orca_fala(
                f"Erro {self.indice + 1} de {len(self.erros)}. "
                f"Palavra: {palavra}. Sugestão: {sugestao}."
            )
        except Exception as e:
            self.orca_fala(f"Erro ao verificar sugestões para a palavra {palavra}.")

    def proximo_erro(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Control F8.")
            return
        if self.indice < len(self.erros) - 1:
            self.indice += 1
        else:
            self.orca_fala("Você chegou ao último erro.")
            return
        self.anunciar_erro_atual()

    def erro_anterior(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Control F8.")
            return
        if self.indice > 0:
            self.indice -= 1
        else:
            self.orca_fala("Você está no primeiro erro.")
            return
        self.anunciar_erro_atual()

    def aceitar_sugestao(self, action):
        self.orca_fala("Função aceitar sugestão em desenvolvimento.")

    def ignorar_erro(self, action):
        if not self.erros:
            return
        self.orca_fala("Erro ignorado.")
        self.proximo_erro(action)