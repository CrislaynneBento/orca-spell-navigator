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

        # 🇧🇷 🇺🇸 Configuração inicial: Começa em Português com o Faber
        self.idioma_atual = "pt_BR"
        self.modelo_voz = "~/.local/share/piper-voices/pt_BR-faber-medium.onnx"

    def do_activate(self):
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("do_activate chamado!\n")

        try:
            self.orca_fala("OrcaSpell ativado.")
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
        if self.processo_audio and self.processo_audio.poll() is None:
            self.processo_audio.terminate()
            self.processo_audio = None
        subprocess.Popen("pkill -f pw-play", shell=True)

    def alternar_idioma(self):
        """Alterna o dicionário e a voz correspondente do Piper (Faber <-> Amy)"""
        if self.idioma_atual == "pt_BR":
            self.idioma_atual = "en_US"
            # Muda para a voz da Amy (Inglês Americano)
            self.modelo_voz = "~/.local/share/piper-voices/en_US-amy-medium.onnx"
            self.orca_fala("Language changed to English.")
        else:
            self.idioma_atual = "pt_BR"
            # Volta para a voz do Faber (Português Brasileiro)
            self.modelo_voz = "~/.local/share/piper-voices/pt_BR-faber-medium.onnx"
            self.orca_fala("Idioma alterado para Português.")

    def on_key_press(self, window, event):
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        keyval = event.keyval

        # Alt + X -> Parada de Emergência (Silenciar)
        if state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_x:
            self.silenciar_faber()
            return True

        # Alt + I -> Alternar Idioma e Voz (Português/Faber <-> Inglês/Amy)
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_i:
            self.alternar_idioma()
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

        # Alt + C -> Aplicar Correção
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_c:
            self.aceitar_sugestao(None)
            return True

        # Alt + S -> Avançar sugestões
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_s:
            self.proxima_sugestao(None)
            return True

        # Alt + Z -> Voltar sugestão
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_z:
            self.sugestao_anterior(None)
            return True

        # Alt + L -> Ler o parágrafo do erro atual
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_l:
            self.ler_paragrafo_atual(None)
            return True

        # Alt + T -> Ler o texto todo
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_t:
            self.ler_texto_todo(None)
            return True

        # Alt + K -> Ler o parágrafo onde o cursor está AGORA (Escrita Livre)
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_k:
            self.ler_paragrafo_cursor_atual()
            return True

        # Alt + A -> Adicionar ao Dicionário Pessoal
        elif state == Gdk.ModifierType.MOD1_MASK and keyval == Gdk.KEY_a:
            self.adicionar_ao_dicionario()
            return True

        # Monitorização em Tempo Real (Espaço ou Enter)
        if state == 0 and (keyval == Gdk.KEY_space or keyval == Gdk.KEY_Return):
            GObject.idle_add(self.verificar_palavra_tempo_real)

        return False

    def orca_fala(self, texto):
        try:
            if self.processo_audio and self.processo_audio.poll() is None:
                self.processo_audio.terminate()

            # Usa a variável dinâmica self.modelo_voz que muda entre Faber e Amy
            comando_piper = (
                f"piper --model {self.modelo_voz} --output_raw | "
                "pw-play --rate 22050 --channels 1 --format s16 -"
            )
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
        doc = self.window.get_active_document()
        if not doc:
            return False

        cursor_iter = doc.get_iter_at_mark(doc.get_insert())
        iter_fim_palavra = cursor_iter.copy()
        iter_fim_palavra.backward_word_start()
        iter_fim_palavra.forward_word_end()

        iter_inicio_palavra = iter_fim_palavra.copy()
        iter_inicio_palavra.backward_word_start()

        palavra = doc.get_text(iter_inicio_palavra, iter_fim_palavra, True).strip()

        if not palavra or len(palavra) < 2 or not palavra.isalpha():
            return False

        resultado = subprocess.run(
            ["hunspell", "-d", self.idioma_atual, "-l"],
            input=palavra, capture_output=True, text=True
        )

        if resultado.stdout.strip():
            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"Aviso, erro na palavra: {palavra}")
            else:
                self.orca_fala(f"Warning, typo in word: {palavra}")

        return False

    def adicionar_ao_dicionario(self):
        if not self.erros or self.indice < 0:
            if self.idioma_atual == "pt_BR":
                self.orca_fala("Nenhum erro selecionado.")
            else:
                self.orca_fala("No error selected.")
            return

        erro_atual = self.erros[self.indice]
        palavra = erro_atual["palavra"]

        try:
            if not os.path.exists(self.caminho_dicionario):
                with open(self.caminho_dicionario, "w") as f:
                    f.write("PERSONAL_DICTIONARY\n")

            with open(self.caminho_dicionario, "a") as f:
                f.write(f"{palavra}\n")

            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"Palavra {palavra} adicionada ao dicionário.")
            else:
                self.orca_fala(f"Word {palavra} added to dictionary.")

            self.erros.pop(self.indice)
            self.indice -= 1
            self.proximo_erro(None)
        except Exception as e:
            self.orca_fala("Erro ao salvar palavra.")

    def iniciar_revisao(self, action):
        try:
            texto = self.obter_texto()
            if not texto.strip():
                if self.idioma_atual == "pt_BR":
                    self.orca_fala("O documento está vazio.")
                else:
                    self.orca_fala("The document is empty.")
                return

            palavras_erradas = set()

            resultado_hunspell = subprocess.run(
                ["hunspell", "-d", self.idioma_atual, "-l"],
                input=texto, capture_output=True, text=True, check=True
            )
            for p in resultado_hunspell.stdout.strip().split("\n"):
                if p.strip():
                    palavras_erradas.add(p.strip())

            if not palavras_erradas:
                if self.idioma_atual == "pt_BR":
                    self.orca_fala("Nenhum erro ortográfico encontrado.")
                else:
                    self.orca_fala("No spelling errors found.")
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

            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"{len(self.erros)} erros encontrados. Pressione Alt N para o primeiro.")
            else:
                self.orca_fala(f"{len(self.erros)} errors found. Press Alt N for the first one.")
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro em iniciar_revisao: {e}\n")
            self.orca_fala("Erro interno.")

    def anunciar_erro_atual(self):
        if not self.erros:
            return

        if self.indice >= len(self.erros):
            self.indice = len(self.erros) - 1
        if self.indice < 0:
            self.indice = 0

        erro = self.erros[self.indice]
        palavra = erro["palavra"]

        try:
            resultado = subprocess.run(
                ["hunspell", "-d", self.idioma_atual],
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

            if self.idioma_atual == "pt_BR":
                self.orca_fala(
                    f"No parágrafo {linha_atual} de {total_linhas}. "
                    f"Erro {self.indice + 1} de {len(self.erros)}. "
                    f"Palavra: {palavra}. Sugestão 1 de {total_sugestoes}: {sugestao_inicial}. "
                    f"Para ouvir o parágrafo completo, pressione Alt L."
                )
            else:
                # Amy assume os feedbacks em inglês!
                self.orca_fala(
                    f"In paragraph {linha_atual} of {total_linhas}. "
                    f"Error {self.indice + 1} of {len(self.erros)}. "
                    f"Word: {palavra}. Suggestion 1 of {total_sugestoes}: {sugestao_inicial}. "
                    f"To hear the full paragraph, press Alt L."
                )
        except Exception as e:
            with open("/tmp/orcaspell.log", "a") as f:
                f.write(f"Erro em anunciar_erro_atual: {e}\n")

    def proxima_sugestao(self, action):
        if not self.erros or self.indice < 0:
            return
        erro = self.erros[self.indice]
        lista = erro.get("lista_sugestoes", ["sem sugestão"])
        if len(lista) <= 1 or lista == ["sem sugestão"]:
            return
        erro["indice_sugestao"] = (erro["indice_sugestao"] + 1) % len(lista)
        erro["sugestao"] = lista[erro["indice_sugestao"]]

        if self.idioma_atual == "pt_BR":
            self.orca_fala(f"Sugestão {erro['indice_sugestao'] + 1} de {len(lista)}: {erro['sugestao']}.")
        else:
            self.orca_fala(f"Suggestion {erro['indice_sugestao'] + 1} of {len(lista)}: {erro['sugestao']}.")

    def sugestao_anterior(self, action):
        if not self.erros or self.indice < 0:
            return
        erro = self.erros[self.indice]
        lista = erro.get("lista_sugestoes", ["sem sugestão"])
        if len(lista) <= 1 or lista == ["sem sugestão"]:
            return
        erro["indice_sugestao"] = (erro["indice_sugestao"] - 1) % len(lista)
        erro["sugestao"] = lista[erro["indice_sugestao"]]

        if self.idioma_atual == "pt_BR":
            self.orca_fala(f"Sugestão {erro['indice_sugestao'] + 1} de {len(lista)}: {erro['sugestao']}.")
        else:
            self.orca_fala(f"Suggestion {erro['indice_sugestao'] + 1} of {len(lista)}: {erro['sugestao']}.")

    def ler_paragrafo_atual(self, action):
        if not self.erros or self.indice < 0:
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
            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"No parágrafo: {paragrafo}")
            else:
                self.orca_fala(f"In paragraph: {paragrafo}")

    def ler_paragrafo_cursor_atual(self):
        doc = self.window.get_active_document()
        if not doc:
            return
        cursor_iter = doc.get_iter_at_mark(doc.get_insert())

        iter_inicio = cursor_iter.copy()
        while not iter_inicio.is_start() and iter_inicio.get_char() != "\n":
            iter_inicio.backward_char()
        if iter_inicio.get_char() == "\n":
            iter_inicio.forward_char()

        iter_fim = cursor_iter.copy()
        while not iter_fim.is_end() and iter_fim.get_char() != "\n":
            iter_fim.forward_char()

        paragrafo = doc.get_text(iter_inicio, iter_fim, True).strip()
        if paragrafo:
            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"No parágrafo atual: {paragrafo}")
            else:
                self.orca_fala(f"Current paragraph: {paragrafo}")

    def ler_texto_todo(self, action):
        texto = self.obter_texto().strip()
        if texto:
            if self.idioma_atual == "pt_BR":
                self.orca_fala(f"Lendo o texto completo: {texto}")
            else:
                self.orca_fala(f"Reading full text: {texto}")

    def proximo_erro(self, action):
        if not self.erros:
            return
        if self.indice < len(self.erros) - 1:
            self.indice += 1
            self.anunciar_erro_atual()
        else:
            if self.idioma_atual == "pt_BR":
                self.orca_fala("Fim dos erros.")
            else:
                self.orca_fala("End of errors.")

    def erro_anterior(self, action):
        if not self.erros:
            return
        if self.indice > 0:
            self.indice -= 1
            self.anunciar_erro_atual()
        else:
            if self.idioma_atual == "pt_BR":
                self.orca_fala("Primeiro erro.")
            else:
                self.orca_fala("First error.")

    def aceitar_sugestao(self, action):
        if not self.erros or self.indice < 0:
            return
        erro = self.erros[self.indice]
        palavra_errada = erro["palavra"]
        sugestao = erro.get("sugestao", "sem sugestão")

        if sugestao in ["sem sugestão", "sem sugestao"]:
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

        if self.idioma_atual == "pt_BR":
            self.orca_fala(f"Corrigido para {sugestao}.")
        else:
            self.orca_fala(f"Corrected to {sugestao}.")

        diferenca_tamanho = len(sugestao) - len(palavra_errada)
        if diferenca_tamanho != 0:
            for i in range(self.indice + 1, len(self.erros)):
                if self.erros[i]["posicao"] > posicao:
                    self.erros[i]["posicao"] += diferenca_tamanho

    def ignorar_erro(self, action):
        self.proximo_erro(action)