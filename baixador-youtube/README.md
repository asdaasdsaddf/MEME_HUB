# Baixador do YouTube

Programa simples para baixar vídeos (MP4) ou só o áudio (MP3) do YouTube sem
passar por sites de download cheios de anúncio. Por baixo ele usa o
[yt-dlp](https://github.com/yt-dlp/yt-dlp), um projeto open source mantido
ativamente. Também funciona com vários outros sites suportados pelo yt-dlp.

## Windows (jeito mais fácil)

1. Instale o Python 3.10 ou mais novo pelo site
   [python.org](https://www.python.org/downloads/). Na primeira tela do
   instalador, marque **"Add python.exe to PATH"**.
2. Dê dois cliques em `iniciar.bat`.
   - Na primeira vez ele prepara tudo, o que leva 1 ou 2 minutos. Nas próximas
     vezes abre rápido.
   - Sempre que abre, ele atualiza o yt-dlp. Isso é importante porque o
     YouTube muda com frequência.
3. Cole o link, escolha **Vídeo** ou **Só áudio** e clique em **Baixar**. Os
   arquivos vão para a pasta Downloads, mas dá para escolher outra.

## Mac / Linux

```sh
cd baixador-youtube
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python baixar_youtube.py
```

No Linux pode ser preciso instalar o Tkinter antes: `sudo apt install python3-tk`.

## Pelo terminal

Passando um link, o programa baixa direto, sem abrir a janela:

```sh
python baixar_youtube.py "https://www.youtube.com/watch?v=..."   # vídeo na melhor qualidade
python baixar_youtube.py "LINK" --qualidade 720                   # limita a 720p
python baixar_youtube.py "LINK" --audio                           # só o áudio, em MP3
python baixar_youtube.py "LINK_DA_PLAYLIST" --playlist --pasta "D:\Musicas"
```

## O que é instalado

- **yt-dlp**: faz o download.
- **deno**: runtime JavaScript que o yt-dlp precisa para funcionar no YouTube.
- **imageio-ffmpeg**: traz o ffmpeg, que junta vídeo e áudio em alta qualidade
  e converte para MP3. Se você já tiver o ffmpeg instalado, o programa usa o seu.

Tudo fica dentro da pasta `.venv`. Para desinstalar, é só apagar essa pasta.

## Se parar de funcionar

O YouTube muda o site de tempos em tempos e o yt-dlp acompanha com
atualizações. Feche o programa e abra de novo pelo `iniciar.bat`, que atualiza
sozinho, ou rode `pip install -U -r requirements.txt`.

## Uso responsável

Baixe só vídeos seus, de domínio público ou com licença livre, ou que você
tenha permissão para baixar. Os Termos de Serviço do YouTube restringem
downloads feitos fora dos recursos oficiais da plataforma.
