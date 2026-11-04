# Bundled components and corresponding sources

AVEN's Python/Tk frontend invokes separate executables. Preserve this directory when redistributing the portable package. Licenses/readmes from upstream binary archives are copied into ThirdParty during packaging.

- stable-diffusion.cpp: MIT, official release `master-1043-3be2378`; https://github.com/leejet/stable-diffusion.cpp/tree/master-1043-3be2378 . Corresponding source: https://github.com/leejet/stable-diffusion.cpp/archive/refs/tags/master-1043-3be2378.tar.gz . Includes ggml and upstream dependencies listed in that source tree.
- CUDA redistributable runtime from that same official release: NVIDIA CUDA Toolkit redistribution terms, https://docs.nvidia.com/cuda/eula/index.html . Requires the user's separately installed NVIDIA driver. No CUDA compiler or driver installer is bundled.
- FFmpeg GPL build: BtbN release `autobuild-2026-11-03-12-50`, FFmpeg commit `ec887b13a8`, as identified by the immutable binary filename. Corresponding FFmpeg source: https://github.com/FFmpeg/FFmpeg/archive/ec887b13a8.tar.gz . Exact build scripts and dependency recipes: https://github.com/BtbN/FFmpeg-Builds/tree/autobuild-2026-11-03-12-50 . Sources for linked libraries, including x264, are specified in those recipes. FFmpeg build configuration is included as ffmpeg-buildconf.txt; FFmpeg's upstream COPYING and LICENSE files remain included. See https://ffmpeg.org/legal.html .
- Microsoft Visual C++ runtime: files taken from Visual Studio's x64 redistributable CRT directory; https://visualstudio.microsoft.com/license-terms/vs2022-crt/ .
- Python 3.12 and Tcl/Tk: Python and Tcl/Tk licenses included by PyInstaller's runtime distribution; https://docs.python.org/3/license.html and https://www.tcl.tk/software/tcltk/license.html .
- Pillow 11.3.0: HPND, https://github.com/python-pillow/Pillow/tree/11.3.0 .
- PyInstaller 6.16.0: GPL with bootloader exception, https://pyinstaller.org/en/v6.16.0/license.html .

Model weights are not bundled. Pinned source URLs and SHA256 values are in `aven/weights.json`, retained from the Mac project. Wan2.1 is published under Apache-2.0; text encoder and repackaged-weight license information is available on the linked model repositories.
