from enum import Enum
from typing import List, Optional

from ..page import UsmPage
from ..types import ElementType


def create_video_crid_page(
    filename: str,
    filesize: int,
    max_size: int,
    channel_number: int,
    bitrate: int,
    format_version: Optional[int] = None,
) -> UsmPage:
    crid = UsmPage("CRIUSF_DIR_STREAM")
    if format_version is not None:
        crid.update("fmtver", ElementType.I32, format_version)

    crid.update("filename", ElementType.STRING, filename)
    crid.update("filesize", ElementType.I32, filesize)
    crid.update("datasize", ElementType.I32, 0)
    crid.update("stmid", ElementType.I32, 1079199318)  # @SFV
    crid.update("chno", ElementType.I16, channel_number)
    crid.update("minchk", ElementType.I16, 3)
    crid.update("minbuf", ElementType.I32, max_size)
    crid.update("avbps", ElementType.I32, bitrate)
    return crid


def create_video_header_page(
    num_frames: int,
    num_keyframes: int,
    framerate: float,
    max_packed_size: int,
    mpeg_codec: int,
    mpeg_dcprec: int,
    ffprobe_video_stream: dict,
) -> UsmPage:
    header = UsmPage("VIDEO_HDRINFO")
    header.update("width", ElementType.I32, ffprobe_video_stream.get("width"))
    header.update("height", ElementType.I32, ffprobe_video_stream.get("height"))
    header.update("mat_width", ElementType.I32, ffprobe_video_stream.get("width"))
    header.update("mat_height", ElementType.I32, ffprobe_video_stream.get("height"))
    header.update("disp_width", ElementType.I32, ffprobe_video_stream.get("width"))
    header.update("disp_height", ElementType.I32, ffprobe_video_stream.get("height"))
    header.update("scrn_width", ElementType.I32, 0)
    header.update("mpeg_dcprec", ElementType.I8, mpeg_dcprec)
    header.update("mpeg_codec", ElementType.I8, mpeg_codec)
    # TODO: Check if videos has transparency
    header.update("alpha_type", ElementType.I32, 0)
    header.update("total_frames", ElementType.I32, num_frames)
    header.update("framerate_n", ElementType.I32, int(framerate * 1000))
    header.update("framerate_d", ElementType.I32, 1000)
    header.update("metadata_count", ElementType.I32, 1)
    header.update("metadata_size", ElementType.I32, num_keyframes)
    header.update("ixsize", ElementType.I32, max_packed_size)
    # TODO: What are the other values for these and what do they mean
    header.update("pre_padding", ElementType.I32, 0)
    header.update("max_picture_size", ElementType.I32, 0)
    header.update("color_space", ElementType.I32, 0)
    header.update("picture_type", ElementType.I32, 0)
    return header


def create_audio_crid_page(
    filename: str,
    filesize: int,
    format_version: int,
    channel_number: int,
    minbuf: int,
    avbps: int,
) -> UsmPage:
    crid = UsmPage("CRIUSF_DIR_STREAM")
    crid.update("fmtver", ElementType.I32, format_version)
    crid.update("filename", ElementType.STRING, filename)
    crid.update("filesize", ElementType.I32, filesize)
    crid.update("datasize", ElementType.I32, 0)
    crid.update("stmid", ElementType.I32, 1079199297)  # @SFA
    crid.update("chno", ElementType.I16, channel_number)
    crid.update("minchk", ElementType.I16, 1)
    crid.update("minbuf", ElementType.I32, minbuf)
    crid.update("avbps", ElementType.I32, avbps)
    return crid


class AUDIO_CODEC(Enum):
    HCA = 4


def create_audio_header_page(
    audio_codec: AUDIO_CODEC,
    sampling_rate: int,
    num_channels: int,
    metadata_count: int,
    metadata_size: int,
    ixsize: int,
    ambisonics: int = 0,  # I have no idea, disabled?
) -> UsmPage:
    header = UsmPage("AUDIO_HDRINFO")
    header.update("audio_codec", ElementType.I8, audio_codec.value)
    header.update("sampling_rate", ElementType.I32, sampling_rate)
    header.update("num_channels", ElementType.I32, num_channels)
    header.update("metadata_count", ElementType.I32, metadata_count)
    header.update("metadata_size", ElementType.I32, metadata_size)
    header.update("ixsize", ElementType.I32, ixsize)
    header.update("ambisonics", ElementType.I8, ambisonics)  # IDK what this is
    return header
