##Versão de código inicial

import subprocess
import gi
gi.require_version('Pluma', '1.0')
from gi.repository import GObject, Pluma, Gtk

#1. Inicializando com uma classe que permite a entrada de uma janela 
#no Pluma, que lerá o que foi digitado pelo professor. 
class OrcaSpellPlugin(GObject.Object, Pluma.WindowActivatable):
    __gtype_name__ = "OrcaSpellPlugin"
    window = GObject.Property(type=Pluma.Window)

    def __init__ (self):
        GObject.Object.__init__(self)
        self.erros = []
        self.indice = 0

    #primeiro método rodará quando o professor ativa o plugin nas configurações do pluma
    def do_activate(self):
        with open("/tmp/orcaspell.log", "w") as f:
            f.write("do_activate chamado!\n")
        self.orca_fala("Plugin OrcaSpell ativado.")
        self.adicionar_atalhos()
    #segundo método rodará quando o professor desativar o plugin
    def do_deactivate(self):
        pass

    #terceiro método rodará toda vez que o estado da janela mudar.
    def do_update_state(self):
        pass

    def adicionar_atalhos(self):
        accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(accel_group)

        key, mod = Gtk.accelerator_parse("<Control>F9")
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self._iniciar_revisao_accel)

        key, mod = Gtk.accelerator_parse("<Alt>n")
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self._proximo_erro_accel)

        key, mod = Gtk.accelerator_parse("<Alt>p")
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self._erro_anterior_accel)



    def _iniciar_revisao_accel(self, group, window, key, mod):
        with open("/tmp/orcaspell.log", "a") as f:
            f.write("_iniciar_revisao_accel chamado!\n")
        self.iniciar_revisao(None)
        return True

    def _proximo_erro_accel(self, group, window, key, mod):
        self.proximo_erro(None)
        return True

    def _erro_anterior_accel(self, group, window, key, mod):
        self.erro_anterior(None)
        return True

            
    def orca_fala(self, texto):
        subprocess.Popen(["spd-say", "-l", "pt", texto])

    def obter_texto(self):
        doc = self.window.get_active_document()
        inicio = doc.get_start_iter()
        fim = doc.get_end_iter()
        return doc.get_text(inicio, fim, True)
    
    def iniciar_revisao(self, action):
        texto = self.obter_texto()
        if not texto.strip():
            self.orca_fala("O documento está vazio.")
            return
        
        resultado = subprocess.run(
            ["hunspell", "-d", "pt_BR", "-l"],
            input = texto, capture_output=True, text = True
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
        self.orca_fala(f"{len(self.erros)} erros encontrados. Pressione Alt N para o primeiro")
    

    def anunciar_erro_atual(self):
        if not self.erros:
            self.orca_fala(f"Nenhum erro para navegar.")
            return
        erro = self.erros[self.indice]
        palavra = erro ["palavra"]

        #sugestão de correção
        resultado = subprocess.run(
            ["hunspell", "-d", "pt_BR"],
            input = palavra, capture_output=True, text=True
        )
        sugestao = "sem sugestão"
        for linha in resultado.stdout.split("\n"):
            if linha.startswith("&"):
                partes = linha.split(":")
                if len(partes) > 1:
                    sugestao = partes[1].strip().split(",")[0].strip()
                    break
        self.orca_fala(
            f"Erro {self.indice + 1} de {len(self.erros)}."
            f"Palavra: {palavra}. Sugestão: {sugestao}."
        )


    def proximo_erro(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Alt E.")
            return
        if self.indice < len(self.erros) - 1:
            self.indice += 1 
        else:
            self.orca_fala("Você chegou ao último erro.")
            return
        self.anunciar_erro_atual()

    
    def erro_anterior(self, action):
        if not self.erros:
            self.orca_fala("Inicie a revisão primeiro com Alt E.")
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
        self.orca_fala("Erro ignorado")
        self.proximo_erro(action)

