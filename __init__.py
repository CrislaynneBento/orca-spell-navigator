import os
import subprocess
from gi.repository import GObject, Pluma, Gtk, Gdk

class OrcaSpellPlugin(GObject.Object, Pluma.WindowActivatable):
    __gtype_name__ = "OrcaSpellPlugin"
    window = GObject.Property(type=Pluma.Window)

    def __init__(self):
        GObject.Object.__init__(self)
        self.erros = []
        self.indice = 0
        self.handler_id = 0
        self.processo_audio = None
        self.caminho_dicionario = os.path.expanduser("~/.hunspell_pt_BR")

    def do_activate(self):
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("do_activate chamado!\n")

        try:
            self.orca_fala("OrcaSpell ativado.")
            # Captura os eventos de teclado globais da janela do Pluma
            self.handler_id = self.window.connect("key-press-event", self.on_key_press)

            with open("/tmp/orcaspell.log", "a") as f:
                f.write("Atalhos nativos do GTK ativados com sucesso!\n")
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"ERRO ao ativar o plugin: {e}\n")

    def do_deactivate(self):
        if self.handler_id and self.window:
            self.window.disconnect(self.handler_id)
            self.handler_id = 0
        self.silenciar_faber()
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("Plugin desativado.\n")

    def do_update_state(self):
        pass

    def silenciar_faber(self):
        """Mata o processo atual de áudio para silenciar o Faber imediatamente"""
        if self.processo_audio and self.processo_audio.poll() is None:
            self.processo_audio.terminate()
            self.processo_audio = None
        # Comando de emergência no sistema para garantir que o pw-play para
        subprocess.Popen("pkill -f pw-play", shell=True)

    def on_key_press(self, window, event):
        """Gerenciador de atalhos nativo do GTK"""
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        keyval = event.keyval
        nome_tecla = Gdk.keyval_name(keyval)

        # 🛑 MELHORIA 1: Alt + X -> Parada de Emergência (Silenciar)
        if state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_x:
            self.silenciar_faber()
            return True

        # Ctrl + Shift + H ou Ctrl + F8 -> Iniciar Revisão
        alvo_mod = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if (state == alvo_mod and (keyval == Gdk.KEY_H or keyval == Gdk.KEY_h)) or \
           (state == Gdk.ModifierType.CONTROL_MASK and keyval == Gdk.KEY_F8):
            self.iniciar_revisao(None)
            return True

        # Alt + N -> Próximo Erro
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_n:
            self.proximo_erro(None)
            return True

        # Alt + P -> Erro Anterior
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_p:
            self.erro_anterior(None)
            return True

        # Alt + C -> Aplicar Correção/Sugestão
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_c:
            self.aceitar_sugestao(None)
            return True

        # Alt + S -> Avançar entre as sugestões
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_s:
            self.proxima_sugestao(None)
            return True

        # Alt + Z -> Voltar para a sugestão anterior
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_z:
            self.sugestao_anterior(None)
            return True

        # Alt + L -> Ler o parágrafo do erro atual
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_l:
            self.ler_paragrafo_atual(None)
            return True

        # Alt + T -> Ler o texto todo do documento
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_t:
            self.ler_texto_todo(None)
            return True

        # 📝 MELHORIA 2: Alt + A -> Adicionar Palavra Atual ao Dicionário Pessoal
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_a:
            self.adicionar_ao_dicionario()
            return True

        # 🔍 MELHORIA 3: Monitorização em Tempo Real (Espaço ou Enter acionam a verificação)
        if state == 0 and (keyval == Gdk.KEY_space or keyval == Gdk.KEY_Return):
            # Deixa o caractere ser inserido primeiro, depois verifica a palavra anterior
            GObject.idle_add(self.verificar_palavra_tempo_real)

        return False

    def orca_fala(self, texto):
        try:
            # Garante que silencia qualquer fala anterior antes de começar uma nova
            if self.processo_audio and self.processo_audio.poll() is None:
                self.processo_audio.terminate()

            comando_piper = (
                "piper --model ~/.local/share/piper-voices/pt_BR-faber-medium.onnx --output_raw | "
                "pw-play --rate 22050 --channels 1 --format s16 -"
            )
            # Guarda a referência do processo para conseguirmos pará-lo com o Alt+X
            self.processo_audio = subprocess.Popen(f'echo "{texto}" | {comando_piper}', shell=True)
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro ao executar Piper: {e}\n")

    def obter_texto(self):
        doc = self.window.get_active_document()
        if not doc:
            return ""
        inicio = doc.get_start_iter()
        fim = doc.get_end_iter()
        return doc.get_text(inicio, fim, True)

    def obter_situacao_linha(self, posicao_offset):
        doc = self.window.get_active_document()
        if not doc:
            return (1, 1)
        iter_erro = doc.get_iter_at_offset(posicao_offset)
        return (iter_erro.get_line() + 1, doc.get_line_count())

    def verificar_palavra_tempo_real(self):
        """Captura a última palavra digitada antes do cursor e valida no Hunspell"""
        doc = self.window.get_active_document()
        if not doc:
            return False

        cursor_iter = doc.get_iter_at_mark(doc.get_insert())
        
        # Anda para trás para isolar a última palavra terminada
        iter_fim_palavra = cursor_iter.copy()
        iter_fim_palavra.backward_word_start()
        iter_fim_palavra.forward_word_end()
        
        iter_inicio_palavra = iter_fim_palavra.copy()
        iter_inicio_palavra.backward_word_start()

        palavra = doc.get_text(iter_inicio_palavra, iter_fim_palavra, True).strip()
        
        # Ignora pontuações ou palavras vazias/curtas
        if not palavra or len(palavra) < 2 or not palavra.isalpha():
            return False

        # Valida rapidamente no Hunspell
        resultado = subprocess.run(
            ["hunspell", "-d", "pt_BR", "-l"],
            input=palavra, capture_output=True, text=True
        )
        
        if resultado.stdout.strip():
            # Palavra está errada! Faber dá um toque de aviso discreto
            self.orca_fala(f"Aviso, erro na palavra: {palavra}")
        
        return False

    def adicionar_ao_dicionario(self):
        """Adiciona a palavra atualmente selecionada na revisão ao dicionário pessoal"""
        if not self.erros or self.indice < 0:
            self.orca_fala("Nenhum erro selecionado para adicionar ao dicionário.")
            return

        erro_atual = self.erros[self.indice]
        palavra = erro_atual["palavra"]

        try:
            # Cria o ficheiro de dicionário pessoal se ele não existir
            if not os.path.exists(self.caminho_dicionario):
                with open(self.caminho_dicionario, "w") as f:
                    f.write("PERSONAL_DICTIONARY\n") # Cabeçalho padrão do Hunspell

            # Escreve a palavra nova lá dentro
            with open(self.caminho_dicionario, "a") as f:
                f.write(f"{palavra}\n")

            self.orca_fala(f"Palavra {palavra} adicionada ao seu dicionário pessoal.")
            
            # Remove este erro da lista atual para não precisares de o corrigir nesta sessão
            self.erros.pop(self.indice)
            self.indice -= 1
            self.proximo_erro(None)
        except Exception as e:
            self.orca_fala("Não foi possível salvar a palavra no dicionário.")

    def iniciar_revisao(self, action):
        try:
            texto = self.obter_texto()
            if not texto.strip():
                self.orca_fala("O documento está vazio.")
                return

            palavras_erradas = set()

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
        
        # Garante que o índice não sai das bordas caso tenhamos removido palavras (via dicionário)
        if self.indice >= len(self.erros):
            self.indice = len(self.erros) - 1
        if self.indice < 0:
            self.indice = 0

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

            erro["lista_sugestoes"] = lista_sugestoes if lista_sugestoes else ["sem sugestão"]
            erro["indice_sugestao"] = 0
            erro["sugestao"] = erro["lista_sugestoes"][0]

            sugestao_inicial = erro["sugestao"]
            total_sugestoes = len(erro["lista_sugestoes"]) if lista_sugestoes else 0

            linha_atual, total_linhas = self.obter_situacao_linha(erro["posicao"])

            self.orca_fala(
                f"No parágrafo {linha_atual} de {total_linhas}. "
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

        iter_inicio = iter_erro.copy()
        while not iter_inicio.is_start() and iter_inicio.get_char() != "\n":
            iter_inicio.backward_char()
        if iter_inicio.get_char() == "\n":
            iter_inicio.forward_char()

        iter_fim = iter_erro.copy()
        while not iter_fim.is_end() and iter_fim.get_char() != "\n":
            iter_fim.forward_char()

        paragrafo = doc.get_text(iter_inicio, iter_fim, True).strip()

        if paragrafo:
            self.orca_fala(f"No parágrafo: {paragrafo}")
        else:
            self.orca_fala("Não foi possível isolar o parágrafo.")

    def ler_texto_todo(self, action):
        texto = self.obter_texto().strip()
        if texto:
            self.orca_fala(f"Lendo o texto completo: {texto}")
        else:
            self.orca_fala("O documento está vazio.")

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