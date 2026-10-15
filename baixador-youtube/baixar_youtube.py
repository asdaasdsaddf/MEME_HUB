#!/usr/bin/env python3
"""Baixador de vídeos do YouTube: uma janela simples por cima do yt-dlp.

Com janela:   python baixar_youtube.py
No terminal:  python baixar_youtube.py URL [URL ...] [--audio] [--qualidade 720]
                                       [--pasta DIR] [--playlist]
"""
import argparse
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("O yt-dlp não está instalado. Rode:  pip install -r requirements.txt")

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None

QUALIDADES = {
    "Máxima disponível": None,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
}
PASTA_PADRAO = Path.home() / "Downloads"
if not PASTA_PADRAO.is_dir():
    PASTA_PADRAO = Path.home()


def localizar_ffmpeg():
    """ffmpeg do sistema; se não houver, o que vem no pacote imageio-ffmpeg."""
    caminho = shutil.which("ffmpeg")
    if caminho:
        return caminho
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def montar_opcoes(pasta, so_audio=False, altura_max=None, playlist=False, ffmpeg=None):
    """Opções do yt-dlp compartilhadas pela janela e pelo modo terminal."""
    opcoes = {
        "outtmpl": str(Path(pasta) / "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": not playlist,
        # Numa playlist, um vídeo com problema não interrompe os outros.
        "ignoreerrors": "only_download",
    }
    if ffmpeg:
        opcoes["ffmpeg_location"] = ffmpeg

    if so_audio:
        if ffmpeg:
            opcoes["format"] = "ba/b"
            opcoes["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            opcoes["format"] = "ba[ext=m4a]/ba/b"
        return opcoes

    # Sem ffmpeg não dá para juntar vídeo e áudio separados, então fica com o
    # melhor arquivo único. Com ffmpeg, prefere H.264/AAC em MP4, que abre em
    # qualquer player sem instalar codec.
    opcoes["format"] = "bv*+ba/b" if ffmpeg else "b"
    opcoes["format_sort"] = [f"res:{altura_max}" if altura_max else "res",
                             "vcodec:h264", "ext:mp4:m4a"]
    opcoes["merge_output_format"] = "mp4"
    return opcoes


def abrir_pasta(pasta):
    if sys.platform == "win32":
        os.startfile(pasta)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", pasta])
    else:
        subprocess.Popen(["xdg-open", pasta])


def formatar_bytes(n):
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n:.1f} TB"


class _Logger:
    """Silencia a saída do yt-dlp, guardando os erros para mostrar na janela."""

    def __init__(self):
        self.erros = []

    def debug(self, msg):
        pass

    info = warning = debug

    def error(self, msg):
        self.erros.append(msg.removeprefix("ERROR: "))


class App:
    def __init__(self, raiz):
        self.raiz = raiz
        self.fila = queue.Queue()
        self.ffmpeg = localizar_ffmpeg()
        self.ultimo_arquivo = None

        raiz.title("Baixador do YouTube")
        raiz.minsize(560, 0)
        quadro = ttk.Frame(raiz, padding=14)
        quadro.pack(fill="both", expand=True)
        quadro.columnconfigure(1, weight=1)

        ttk.Label(quadro, text="Link:").grid(row=0, column=0, sticky="w", pady=4)
        self.url = tk.StringVar()
        entrada = ttk.Entry(quadro, textvariable=self.url)
        entrada.grid(row=0, column=1, sticky="ew", padx=6)
        entrada.bind("<Return>", lambda _: self.baixar())
        entrada.focus()
        ttk.Button(quadro, text="Colar", command=self.colar).grid(row=0, column=2, sticky="ew")

        ttk.Label(quadro, text="Formato:").grid(row=1, column=0, sticky="w", pady=4)
        self.formato = tk.StringVar(value="video")
        linha_formato = ttk.Frame(quadro)
        linha_formato.grid(row=1, column=1, columnspan=2, sticky="w", padx=6)
        ttk.Radiobutton(linha_formato, text="Vídeo (MP4)", value="video",
                        variable=self.formato, command=self._ao_mudar_formato).pack(side="left")
        ttk.Radiobutton(linha_formato, text="Só áudio (MP3)", value="audio",
                        variable=self.formato, command=self._ao_mudar_formato).pack(side="left", padx=14)

        ttk.Label(quadro, text="Qualidade:").grid(row=2, column=0, sticky="w", pady=4)
        self.qualidade = tk.StringVar(value="1080p")
        self.combo_qualidade = ttk.Combobox(quadro, textvariable=self.qualidade, state="readonly",
                                            values=list(QUALIDADES), width=20)
        self.combo_qualidade.grid(row=2, column=1, sticky="w", padx=6)

        self.playlist = tk.BooleanVar(value=False)
        ttk.Checkbutton(quadro, text="Se o link for de uma playlist, baixar todos os vídeos",
                        variable=self.playlist).grid(row=3, column=1, columnspan=2, sticky="w", padx=6, pady=4)

        ttk.Label(quadro, text="Salvar em:").grid(row=4, column=0, sticky="w", pady=4)
        self.pasta = tk.StringVar(value=str(PASTA_PADRAO))
        ttk.Entry(quadro, textvariable=self.pasta).grid(row=4, column=1, sticky="ew", padx=6)
        ttk.Button(quadro, text="Escolher…", command=self.escolher_pasta).grid(row=4, column=2, sticky="ew")

        botoes = ttk.Frame(quadro)
        botoes.grid(row=5, column=0, columnspan=3, pady=(12, 6))
        self.botao_baixar = ttk.Button(botoes, text="Baixar", command=self.baixar)
        self.botao_baixar.pack(side="left", padx=4)
        ttk.Button(botoes, text="Abrir pasta", command=self.abrir_destino).pack(side="left", padx=4)

        self.progresso = ttk.Progressbar(quadro, maximum=100)
        self.progresso.grid(row=6, column=0, columnspan=3, sticky="ew", pady=4)
        self.status = ttk.Label(quadro, text="Cole um link e clique em Baixar.", wraplength=520)
        self.status.grid(row=7, column=0, columnspan=3, sticky="w")

        if not self.ffmpeg:
            self.status["text"] = ("Aviso: ffmpeg não encontrado. Os vídeos ficam limitados à qualidade "
                                   "de arquivo único e o áudio sai em M4A.")

        self.raiz.after(100, self._processar_fila)

    # --- ações da janela -------------------------------------------------

    def colar(self):
        try:
            self.url.set(self.raiz.clipboard_get().strip())
        except tk.TclError:
            pass

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(initialdir=self.pasta.get())
        if pasta:
            self.pasta.set(pasta)

    def abrir_destino(self):
        pasta = self.pasta.get()
        Path(pasta).mkdir(parents=True, exist_ok=True)
        abrir_pasta(pasta)

    def _ao_mudar_formato(self):
        self.combo_qualidade.state(["disabled"] if self.formato.get() == "audio" else ["!disabled", "readonly"])

    def baixar(self):
        url = self.url.get().strip()
        if not url:
            messagebox.showwarning("Baixador do YouTube", "Cole o link do vídeo primeiro.")
            return
        if self.botao_baixar.instate(["disabled"]):
            return

        opcoes = montar_opcoes(
            self.pasta.get(),
            so_audio=self.formato.get() == "audio",
            altura_max=QUALIDADES[self.qualidade.get()],
            playlist=self.playlist.get(),
            ffmpeg=self.ffmpeg,
        )
        opcoes.update({
            "quiet": True,
            "noprogress": True,
            "logger": _Logger(),
            "progress_hooks": [self._ao_progredir],
            "postprocessor_hooks": [self._ao_pos_processar],
            "post_hooks": [lambda caminho: self.fila.put(("arquivo", caminho))],
        })

        self.ultimo_arquivo = None
        self.botao_baixar.state(["disabled"])
        self.progresso["value"] = 0
        self.status["text"] = "Buscando informações do vídeo…"
        threading.Thread(target=self._executar, args=(url, opcoes), daemon=True).start()

    # --- roda na thread de download --------------------------------------

    def _executar(self, url, opcoes):
        logger = opcoes["logger"]
        try:
            with yt_dlp.YoutubeDL(opcoes) as ydl:
                falhou = ydl.download([url])
        except yt_dlp.utils.DownloadError as erro:
            self.fila.put(("erro", str(erro).removeprefix("ERROR: ")))
        except Exception as erro:
            self.fila.put(("erro", f"{type(erro).__name__}: {erro}"))
        else:
            if falhou:
                self.fila.put(("erro", "\n".join(logger.erros[-5:]) or "O download falhou."))
            else:
                self.fila.put(("fim", None))

    def _ao_progredir(self, d):
        if d["status"] != "downloading":
            return
        titulo = d.get("info_dict", {}).get("title", "")
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        baixado = d.get("downloaded_bytes") or 0
        pct = baixado * 100 / total if total else None

        partes = [f"Baixando: {titulo}"]
        if pct is not None:
            partes.append(f"{pct:.0f}% de {formatar_bytes(total)}")
        if d.get("speed"):
            partes.append(f"{formatar_bytes(d['speed'])}/s")
        if d.get("eta") is not None:
            partes.append(f"faltam {int(d['eta'])}s")
        self.fila.put(("progresso", (pct, " — ".join(partes))))

    def _ao_pos_processar(self, d):
        if d["status"] != "started":
            return
        mensagens = {
            "Merger": "Juntando vídeo e áudio…",
            "ExtractAudio": "Convertendo para MP3…",
        }
        if d["postprocessor"] in mensagens:
            self.fila.put(("progresso", (None, mensagens[d["postprocessor"]])))

    # --- volta para a thread da janela -----------------------------------

    def _processar_fila(self):
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == "progresso":
                    pct, texto = dado
                    if pct is not None:
                        self.progresso["value"] = pct
                    self.status["text"] = texto
                elif tipo == "arquivo":
                    self.ultimo_arquivo = dado
                elif tipo == "fim":
                    self.progresso["value"] = 100
                    destino = self.ultimo_arquivo or self.pasta.get()
                    self.status["text"] = f"Pronto! Salvo em:\n{destino}"
                    self.botao_baixar.state(["!disabled"])
                elif tipo == "erro":
                    self.progresso["value"] = 0
                    self.status["text"] = "Falhou. Veja a mensagem de erro."
                    self.botao_baixar.state(["!disabled"])
                    messagebox.showerror(
                        "Erro ao baixar",
                        f"{dado}\n\nSe o YouTube mudou algo, atualizar costuma resolver: "
                        "feche e abra pelo iniciar.bat (ele atualiza o yt-dlp) ou rode\n"
                        "pip install -U -r requirements.txt",
                    )
        except queue.Empty:
            pass
        self.raiz.after(100, self._processar_fila)


def main_terminal(argumentos):
    parser = argparse.ArgumentParser(
        description="Baixa vídeos do YouTube (e de outros sites suportados pelo yt-dlp).")
    parser.add_argument("urls", nargs="+", metavar="URL")
    parser.add_argument("-a", "--audio", action="store_true", help="baixa só o áudio, em MP3")
    parser.add_argument("-q", "--qualidade", type=int, metavar="ALTURA",
                        help="altura máxima do vídeo, ex.: 720 (padrão: a maior disponível)")
    parser.add_argument("-p", "--pasta", default=str(PASTA_PADRAO),
                        help="pasta de destino (padrão: %(default)s)")
    parser.add_argument("--playlist", action="store_true",
                        help="se o link tiver uma playlist, baixa todos os vídeos dela")
    args = parser.parse_args(argumentos)

    ffmpeg = localizar_ffmpeg()
    if not ffmpeg:
        print("Aviso: ffmpeg não encontrado; qualidade limitada e áudio em M4A.", file=sys.stderr)
    opcoes = montar_opcoes(args.pasta, so_audio=args.audio, altura_max=args.qualidade,
                           playlist=args.playlist, ffmpeg=ffmpeg)
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            return ydl.download(args.urls)
    except yt_dlp.utils.DownloadError:
        return 1  # o yt-dlp já imprimiu a mensagem de erro


def main():
    if len(sys.argv) > 1:
        sys.exit(main_terminal(sys.argv[1:]))
    if tk is None:
        sys.exit("Tkinter não está disponível. Use pelo terminal: python baixar_youtube.py URL")
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
