# Festgeschriebene Engine und Modellgewichte

Engine: [leejet/stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp), Commit `d30854463dbc75fb3671209b79016bb0d8ac321e` in `scripts/engine-revision.txt`. GGML-Submodul wird auf dem zugehörigen Commit ausgecheckt. Die MIT-Lizenztexte werden ins App-Paket kopiert.

Referenzen: [Wan-Anleitung](https://github.com/leejet/stable-diffusion.cpp/blob/d30854463dbc75fb3671209b79016bb0d8ac321e/docs/wan.md), [VACE-Rezept](https://github.com/leejet/stable-diffusion.cpp/blob/d30854463dbc75fb3671209b79016bb0d8ac321e/examples/server/recipes/wan21-vace.json), [offizielle VACE-Implementierung](https://github.com/Wan-Video/Wan2.1/blob/main/generate.py). Das Engine-Rezept verwendet 832×480, 33 Frames, Euler, CFG 5, Flow-Shift 16 und 20 Schritte. Die offizielle Wan-Implementierung verwendet für VACE 50 Schritte und Flow-Shift 16; der Solver ist dort nicht derselbe.

| Komponente | Datei | SHA256 |
|---|---|---|
| Diffusion Q4 | wan2.1-v3-vace-1.3b-q4_0.gguf | c9d2ad33427cef0e485c0c32b105c3cca8a33f6bfd8249b41b9685756aed4a74 |
| Diffusion Q8 | wan2.1-v3-vace-1.3b-q8_0.gguf | ac0dcf0f1dd271352be972ce4b425e994a061cc0c650410dcd8d9fdf7f4940dc |
| UMT5 Q3 | umt5-xxl-encoder-Q3_K_S.gguf | f64f8d6dc4d8a24276df69d0ccea789aae686f7417950a41e6568c30cb478a5c |
| UMT5 Q5 | umt5-xxl-encoder-Q5_K_M.gguf | eaea358bb438c5d211721a4feecc162000e3636e9cb96f51e216f1f44ebd12ce |
| Wan 2.1 VAE | wan_2.1_vae.safetensors | 2fc39d31359a4b0a64f55876d8ff7fa8d780956ae2cb13463b0223e15148976b |

Quellen: [calcuis GGUF](https://huggingface.co/calcuis/wan-1.3b-gguf/tree/0652f175f44055eb60cca26dd7cd89c14abe22ce), [city96 UMT5](https://huggingface.co/city96/umt5-xxl-encoder-gguf/tree/b535255bee98c2b0a59ea7c0ae2dcd0c6657b3b7), [Comfy-Org Wan 2.1](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/tree/123acf1cc74bccbb9bfff8ac1ee72edc08c2341d/split_files/vae). Bereits vorhandene gültige V3-Gewichte werden weiterverwendet. Der alte GGUF ohne VACE-Patch-Embedding wird nicht verwendet.

Die Gewichte unterliegen den jeweils auf der Modellseite genannten Lizenzen. Sie sind kein Bestandteil des Quellcode-Archivs. Nach dem einmaligen Download läuft die Generierung lokal.
