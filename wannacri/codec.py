from __future__ import annotations

from enum import Enum, auto
import ffmpeg


class Sofdec2Codec(Enum):
    PRIME = auto()  # MPEG2
    H264 = auto()
    VP9 = auto()

    @staticmethod
    def from_file(path: str, ffprobe_path: str = "ffprobe") -> Sofdec2Codec:
        info = ffmpeg.probe(path, cmd=ffprobe_path)

        if len(info.get("streams")) == 0:
            raise ValueError("File has no videos streams.")

        codec_name = info.get("streams")[0].get("codec_name")
        if codec_name == "vp9":
            if info.get("format").get("format_name") != "ivf":
                raise ValueError("VP9 file must be stored as an ivf.")

            return Sofdec2Codec.VP9
        if codec_name == "h264":
            # TODO: Check if we need to have extra checks on h264 bitstreams
            return Sofdec2Codec.H264
        if codec_name == "mpeg2video":
            # TODO: Check if we need to have extra checks on h264 bitstreams
            return Sofdec2Codec.PRIME

        raise ValueError(f"Unknown codec {codec_name}")
