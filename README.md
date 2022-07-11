[![Version](https://img.shields.io/pypi/v/wannacri.svg)](https://pypi.org/project/WannaCRI)

WannaCRI
========
A (WIP) Python library for parsing, extracting, and generating Criware's various audio and video file formats.
If you're interested in reading more about USM, you can read my write-up about it [here](https://listed.to/@donmai/24921/criware-s-usm-format-part-1)

Support
=======
This currently supports the following formats with more planned:

✅: Implemented and tested ❓: Should work but not tested ❌: Not implemented

x/y: Extract support / Create support

## USM

### Video

| Codec | Not-encrypted | Encrypted |
| ----- | ----- |-----------|
| VP9 | ✅ / ✅  | ✅ / ✅     |
| H.264 | ✅ / ✅ | ✅ / ❓     |
| Prime | ❓ / ❌ | ❓ / ❌     |

### Audio

| Codec | Not-encrypted | Encrypted |
| ----- | ----- | ----- |
| CRI HCA | ✅ / ❌ | ✅ / ❌ |

Requirements
============
This library has the following requirements:

A working FFmpeg and FFprobe installation. On Windows, you can download official ffmpeg and ffprobe binaries and place them on your path.

This project heavily uses the [ffmpeg-python](https://pypi.org/project/ffmpeg-python) wrapper. And uses [python-json-logger](https://pypi.org/project/python-json-logger) for logging.

Usage
=====
If installed, there should be a command-line tool available.

For extracting USMs:

`wannacri extractusm /path/to/usm/file/or/folder --key 0xKEYUSEDIFENCRYPTED`

For creating USMs:

`wannacri createusm /path/to/vp9/file --key 0xKEYIFYOUWANTTOENCRYPT`

Licence
=======
This is an open-sourced application licensed under the MIT License

