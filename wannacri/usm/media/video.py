import os
from typing import Generator, Tuple, Optional, List

import ffmpeg

from .tools import create_video_crid_page, create_video_header_page
from .protocols import UsmVideo
from ..page import UsmPage


class GenericVideo(UsmVideo):
    """Generic videos container used for storing videos
    channels in Usm files. Use other containers when creating
    USMs from videos files."""

    def __init__(
        self,
        stream: Generator[Tuple[bytes, bool], None, None],
        crid_page: UsmPage,
        header_page: UsmPage,
        length: int,
        channel_number: int = 0,
        metadata_pages: Optional[List[UsmPage]] = None,
    ):
        self._stream = stream
        self._crid_page = crid_page
        self._header_page = header_page
        self._length = length
        self._channel_number = channel_number
        self._metadata_pages = metadata_pages


class Vp9(UsmVideo):
    def __init__(
        self,
        filepath: str,
        channel_number: int = 0,
        format_version: int = 16777984,
        ffprobe_path: Optional[str] = None,
    ):
        if ffprobe_path is None:
            info = ffmpeg.probe(filepath, show_entries="packet=dts,pts_time,pos,flags")
        else:
            info = ffmpeg.probe(
                filepath,
                cmd=ffprobe_path,
                show_entries="packet=dts,pts_time,pos,flags",
            )

        if len(info.get("streams")) == 0:
            raise ValueError("File has no videos streams.")
        if info.get("format").get("format_name") != "ivf":
            raise ValueError("File is not an ivf.")
        if info.get("streams")[0].get("codec_name") != "vp9":
            raise ValueError("File is not a VP9 videos.")

        filesize = os.path.getsize(filepath)
        filename = os.path.basename(filepath)

        video_stream = info.get("streams")[0]
        framerate = int(video_stream.get("r_frame_rate").split("/")[0]) / int(
            video_stream.get("r_frame_rate").split("/")[1]
        )

        frames = info.get("packets")
        keyframes = [kf.get("dts") for kf in frames if "K" in kf.get("flags")]
        max_size = 0
        sizes = []
        for i, frame in enumerate(frames):
            frame_offset = int(frame.get("pos"))
            if i == len(frames) - 1:
                frame_size = filesize - frame_offset
            elif i == 0:
                frame_size = int(frames[i + 1].get("pos"))
            else:
                frame_size = int(frames[i + 1].get("pos")) - frame_offset

            max_size = max(max_size, frame_size)
            sizes.append(frame_size)

        max_padding_size = 0x20 - (max_size % 0x20) if max_size % 0x20 != 0 else 0
        max_packed_size = 0x18 + max_size + max_padding_size

        self._crid_page = create_video_crid_page(
            filename=filename,
            filesize=filesize,
            max_size=max_size,
            format_version=format_version,
            channel_number=channel_number,
            bitrate=int(info.get("format").get("bit_rate")),
        )

        self._header_page = create_video_header_page(
            num_frames=len(frames),
            num_keyframes=len(keyframes),
            framerate=framerate,
            max_packed_size=max_packed_size,
            mpeg_codec=9,  # Value for VP9 USMs
            mpeg_dcprec=0,  # Value for VP9 USMs
            ffprobe_video_stream=video_stream,
        )

        def packet_gen(
            path: str, packet_sizes: List[int], keyframe_indexes: List[int]
        ) -> Generator[Tuple[bytes, bool], None, None]:
            video = open(path, "rb")
            for index, size in enumerate(packet_sizes):
                is_keyframe = index in keyframe_indexes
                yield video.read(size), is_keyframe

            video.close()

        self._stream = packet_gen(filepath, sizes, keyframes)
        self._length = len(frames)
        self._channel_number = channel_number
        self._metadata_pages = None
