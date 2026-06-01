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
            self.orca_fala("OrcaSpell ativado.")

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
        """Gerenciador de atalhos nativo do GTK"""
        state = event.state & Gtk.accelerator_get_default_mod_mask()

        nome_tecla = Gdk.keyval_name(event.keyval)
        with open("/tmp/orcaspell.log", "a") as f:
            f.write(f"Tecla pressionada no Pluma: {nome_tecla} (Modificador: {state})\n")

        # Opção 1: Ctrl + F8 (Caso o sistema libere a tecla)
        if state == Gdk.ModifierType.CONTROL_MASK and event.keyval == Gdk.KEY_F8:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalhos Ctrl+F8 acionado com sucesso!\n")
            self.iniciar_revisao(None)
            return True

        # Opção 2: Ctrl + Shift + H (Funciona tanto com H maiúsculo quanto h minúsculo)
        alvo_mod = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if state == alvo_mod and (event.keyval == Gdk.KEY_H or event.keyval == Gdk.KEY_h):
            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalho alternativo Ctrl+Shift+H acionado com sucesso!\n")
            self.iniciar_revisao(None)
            return True

        # Alt + N -> Próximo Erro
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_n:
            self.proximo_erro(None)
            return True

        # Alt + P -> Erro Anterior
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_p:
            self.erro_anterior(None)
            return True

        # Alt + C -> Aplicar Correção/Sugestão
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_c:
            self.aceitar_sugestao(None)
            return True

        # Alt + S -> Avançar entre as sugestões da palavra atual
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_s:
            self.proxima_sugestao(None)
            return True

        # Alt + Z -> Voltar para a sugestão anterior
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_z:
            self.sugestao_anterior(None)
            return True

        # Alt + L -> Ler o parágrafo do erro atual
        elif state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_l:
            self.ler_paragrafo_atual(None)
            return True

        return False

    def orca_fala(self, texto):
        try:
            comando_piper = (
                "piper --model ~/.local/share/piper-voices/pt_BR-faber-medium.onnx --output_raw | "
                "pw-play --rate 22050 --channels 1 --format s16 -"
            )
            # Executa o comando passando o texto dinamicamente
            subprocess.Popen(f'echo "{texto}" | {comando_piper}', shell=True)
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro ao executar Piper no plugin: {e}\n")

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

            palavras_erradas = set()

            # Roda o Hunspell (Erros ortográficos brutos)
            resultado_hunspell = subprocess.run(
                ["hunspell", "-d", "pt_BR", "-l"],
                input=texto, capture_output=True, text=True, check=True
            )
            for p in resultado_hunspell.stdout.strip().split("\n"):
                if p.strip():
                    palavras_erradas.add(p.strip())

            if not palavras_erradas:
                self.orca_fala("Nenhum erro ortográfico encontrado.")
                return

            self.erros = []
            for palavra in list(palavras_erradas):
                inicio = 0
                while True:
                    pos = texto.find(palavra, inicio)
                    if pos == -1:
                        break
                    self.erros.append({"palavra": palavra, "posicao": pos})
                    inicio = pos + len(palavra)

            self.erros.sort(key=lambda x: x["posicao"])
            self.indice = -1
            self.orca_fala(f"{len(self.erros)} erros encontrados. Pressione Alt N para o primeiro.")
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro em iniciar_revisao: {e}\n")
            self.orca_fala("Erro interno ao iniciar a revisão.")

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

            lista_sugestoes = []
            for linha in resultado.stdout.split("\n"):
                if linha.startswith("&"):
                    partes = linha.split(":")
                    if len(partes) > 1:
                        lista_sugestoes = [s.strip() for s in partes[1].strip().split(",")]
                        break

            # Armazena todas as sugestões encontradas na memória do erro atual
            erro["lista_sugestoes"] = lista_sugestoes if lista_sugestoes else ["sem sugestão"]
            erro["indice_sugestao"] = 0

            # Define a primeira sugestão como a ativa inicial
            erro["sugestao"] = erro["lista_sugestoes"][0]

            sugestao_inicial = erro["sugestao"]
            total_sugestoes = len(erro["lista_sugestoes"]) if lista_sugestoes else 0

            # O Faber dita o erro e ensina o comando de contexto (Alt + L)
            self.orca_fala(
                f"Erro {self.indice + 1} de {len(self.erros)}. "
                f"Palavra: {palavra}. Sugestão 1 de {total_sugestoes}: {sugestao_inicial}. "
                f"Para ouvir o parágrafo completo, pressione Alt L."
            )
        except Exception as e:
            self.orca_fala(f"Erro ao verificar sugestões para a palavra {palavra}.")

    def proxima_sugestao(self, action):
        if not self.erros or self.indice < 0:
            self.orca_fala("Nenhum erro selecionado.")
            return

        erro = self.erros[self.indice]
        lista = erro.get("lista_sugestoes", ["sem sugestão"])

        if len(lista) <= 1 or lista == ["sem sugestão"]:
            self.orca_fala("Não há outras sugestões para esta palavra.")
            return

        # Rotaciona o índice entre as opções disponíveis
        erro["indice_sugestao"] = (erro["indice_sugestao"] + 1) % len(lista)
        erro["sugestao"] = lista[erro["indice_sugestao"]]

        num = erro["indice_sugestao"] + 1
        self.orca_fala(f"Sugestão {num} de {len(lista)}: {erro['sugestao']}.")

    def sugestao_anterior(self, action):
        if not self.erros or self.indice < 0:
            self.orca_fala("Nenhum erro selecionado.")
            return

        erro = self.erros[self.indice]
        lista = erro.get("lista_sugestoes", ["sem sugestão"])

        if len(lista) <= 1 or lista == ["sem sugestão"]:
            self.orca_fala("Não há outras sugestões para esta palavra.")
            return

        # Retrocede o índice. Se estiver na primeira (0), vai para a última (len-1)
        erro["indice_sugestao"] = (erro["indice_sugestao"] - 1) % len(lista)
        erro["sugestao"] = lista[erro["indice_sugestao"]]

        num = erro["indice_sugestao"] + 1
        self.orca_fala(f"Sugestão {num} de {len(lista)}: {erro['sugestao']}.")

    def ler_paragrafo_atual(self, action):
        if not self.erros or self.indice < 0:
            self.orca_fala("Inicie a revisão primeiro.")
            return

        doc = self.window.get_active_document()
        if not doc:
            return

        erro = self.erros[self.indice]
        posicao = erro["posicao"]

        iter_erro = doc.get_iter_at_offset(posicao)

        # Retrocede para achar o início do parágrafo
        iter_inicio = iter_erro.copy()
        while not iter_inicio.is_start() and iter_inicio.get_char() != "\n":
            iter_inicio.backward_char()
        if iter_inicio.get_char() == "\n":
            iter_inicio.forward_char()

        # Avança para achar o fim do parágrafo
        iter_fim = iter_erro.copy()
        while not iter_fim.is_end() and iter_fim.get_char() != "\n":
            iter_fim.forward_char()

        paragrafo = doc.get_text(iter_inicio, iter_fim, True).strip()

        if paragrafo:
            self.orca_fala(f"No parágrafo: {paragrafo}")
        else:
            self.orca_fala("Não foi possível isolar o parágrafo.")

    def proximo_erro(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Control Shift H.")
            return

        if self.indice < len(self.erros) - 1:
            self.indice += 1
            self.anunciar_erro_atual()
        else:
            self.orca_fala("Você chegou ao último erro.")
            return

    def erro_anterior(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Control Shift H.")
            return

        if self.indice > 0:
            self.indice -= 1
            self.anunciar_erro_atual()
        else:
            self.orca_fala("Você está no primeiro erro.")
            return

    def aceitar_sugestao(self, action):
        if not self.erros or self.indice < 0:
            self.orca_fala("Nenhum erro selecionado para corrigir")
            return

        erro = self.erros[self.indice]
        palavra_errada = erro["palavra"]
        sugestao = erro.get("sugestao", "sem sugestão")

        if sugestao == "sem sugestão":
            self.orca_fala("Não há soluções válidas para esta palavra.")
            return

        doc = self.window.get_active_document()
        if not doc:
            return

        posicao = erro["posicao"]

        iter_inicio = doc.get_iter_at_offset(posicao)
        iter_fim = doc.get_iter_at_offset(posicao + len(palavra_errada))

        doc.begin_user_action()
        doc.delete(iter_inicio, iter_fim)
        doc.insert(iter_inicio, sugestao)
        doc.end_user_action()

        self.orca_fala(f"Corrigido para {sugestao}.")

        diferenca_tamanho = len(sugestao) - len(palavra_errada)
        if diferenca_tamanho != 0:
            for i in range(self.indice + 1, len(self.erros)):
                if self.erros[i]["posicao"] > posicao:
                    self.erros[i]["posicao"] += diferenca_tamanho

    def ignorar_erro(self, action):
        if not self.erros:
            return
        self.orca_fala("Erro ignorado.")
        self.proximo_erro(action)