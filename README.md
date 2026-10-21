# yt-transcript

Transcreve vídeos do YouTube (ou arquivos de áudio/vídeo locais) **localmente**:
o áudio é baixado com [yt-dlp](https://github.com/yt-dlp/yt-dlp) e transcrito na
sua máquina com [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(GPU NVIDIA quando disponível, CPU caso contrário). Nada é enviado a serviços externos.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala as dependências Python sozinho, em ambiente isolado)
- `yt-dlp` e `ffmpeg` no `PATH`
- Opcional: GPU NVIDIA com driver recente (cuBLAS/cuDNN do CUDA 12 vêm via pip)

## Instalação

```bash
git clone git@github.com:apolzek/yt-transcript.git
ln -s "$PWD/yt-transcript/yt-transcript" ~/.local/bin/yt-transcript
```

Na primeira execução o modelo (~1,6 GB para `large-v3-turbo`) é baixado e fica em cache.

## Uso

```bash
yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"   # imprime o texto
yt-transcript URL -o texto.txt                              # salva em arquivo
yt-transcript URL -f ts                                     # com [hh:mm:ss] por linha
yt-transcript URL -f srt -o legenda.srt                     # também: vtt
yt-transcript URL --lang pt                                 # força o idioma (padrão: detecção automática)
yt-transcript URL -m small                                  # modelo menor/mais rápido
yt-transcript URL --subs                                    # usa a legenda do YouTube (manual > automática)
yt-transcript video.mp4                                     # arquivo local
```

| Opção | Descrição |
|---|---|
| `-o, --output` | arquivo de saída (padrão: stdout) |
| `-f, --format` | `txt` (padrão), `ts`, `srt`, `vtt` |
| `-l, --lang` | idioma, ex. `pt`, `en` |
| `-m, --model` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo` (padrão) |
| `--device` | `auto` (padrão), `cuda`, `cpu` |
| `--subs` | usa legendas do YouTube; cai para Whisper se não houver |

Progresso e logs vão para stderr; o texto vai para stdout, então dá para usar em pipe:

```bash
yt-transcript URL | wc -w
```

## Desempenho

Vídeo de 32 min em português: ~1 min numa RTX 4070 Ti SUPER com `large-v3-turbo`.

## Licença

MIT
