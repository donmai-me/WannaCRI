# WannaCRI
A (WIP) Python library for parsing, extracting, and generating Criware's various audio and video file formats.
If you're interested in reading more about USM, you can read my write-up about it [here](https://listed.to/@donmai/24921/criware-s-usm-format-part-1)

Currently supports the following formats with more planned:
* USM (encrypted and plaintext)
    * Vp9
    * h264 (in-progress)


This library has the following requirements:

A working FFmpeg and FFprobe installation. On Windows, you can download official ffmpeg and ffprobe binaries and place them on your path.

This project also heavily uses the [ffmpeg-python](https://pypi.org/project/ffmpeg-python) wrapper.

# Usage

If installed, there should be a command-line tool available.

For extracting USMs:

`wannacri extractusm /path/to/usm/file/or/folder --key 0xKEYUSEDIFENCRYPTED`

For creating USMs:

`wannacri createusm /path/to/vp9/file --key 0xKEYIFYOUWANTTOENCRYPT`

# Licence

This is an open-sourced application licensed under the MIT License

