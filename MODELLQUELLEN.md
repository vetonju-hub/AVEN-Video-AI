# Modellquellen (separater Download)

Die App lädt die folgenden Dateien über HTTPS von Hugging Face, speichert sie in `~/Library/Application Support/AVEN Video AI/Models/` und arbeitet danach ohne Server:

| Komponente | Datei | Ungefährer Umfang |
|---|---|---:|
| Wan VACE Q4 Diffusionsnetz | `wan2.1-vace-1.3b-q4_0.gguf` | 1,35 GB |
| UMT5 Q3 Textencoder | `umt5-xxl-encoder-Q3_K_S.gguf` | 2,86 GB |
| Wan VAE | `wan_2.1_vae.safetensors` | 0,25 GB |
| Wan VACE Q8 (optional, viel RAM) | `wan2.1-vace-1.3b-q8_0.gguf` | 2,37 GB |
| UMT5 Q5 (optional) | `umt5-xxl-encoder-Q5_K_M.gguf` | 4,15 GB |

Modellgewicht-URLs und Dateinamen: https://huggingface.co/calcuis/wan-1.3b-gguf und https://huggingface.co/city96/umt5-xxl-encoder-gguf. Die tatsächlichen Downloadgrößen können sich ändern. Die App kontrolliert Mindestdateigrößen, aber keine kryptografischen Hashes; für sicherheitskritische Nutzung zusätzlich SHA-256 gegen offizielle Hashes verifizieren.

Engine: https://github.com/leejet/stable-diffusion.cpp , Wan-Dokumentation: https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/wan.md

Der Installer lädt Gewichte **nicht** automatisch. Der Nutzer entscheidet das ausdrücklich über den Button in der App.
