# Synthetic media fixtures

`vbr-no-xing.mp3` is an original generated test signal: 2 seconds of a 440 Hz sine followed by noise, encoded with LAME VBR quality 4, with Xing and ID3 disabled. It contains no user music.

`vbr-duration.txt` is the sum of independently inspected coded MP3 packet durations (5.407254 s), including codec padding. AVFoundation precise timing should agree within one MP3 frame. This fixture exposes duration estimation errors on varying bit-rate audio without a summary header.

The WAV and PNG/MP4 fixtures are generated at test time; the 2x2 PNG used by portable CRC tests was constructed directly from PNG chunks and zlib. No neural image quality is inferred from these synthetic fixtures.
