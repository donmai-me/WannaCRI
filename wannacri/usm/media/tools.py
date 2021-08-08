from typing import List

from ..page import UsmPage
from ..types import ElementType


def create_video_crid_page(
    filename: str,
    filesize: int,
    max_size: int,
    format_version: int,
    channel_number: int,
    bitrate: int,
) -> UsmPage:
    crid = UsmPage("CRIUSF_DIR_STREAM")
    crid.update("fmtver", ElementType.INT, format_version)
    crid.update("filename", ElementType.STRING, filename)
    crid.update("filesize", ElementType.INT, filesize)
    crid.update("datasize", ElementType.INT, 0)
    crid.update("stmid", ElementType.INT, 1079199318)  # @SFV
    crid.update("chno", ElementType.SHORT, channel_number)
    crid.update("minchk", ElementType.SHORT, 3)
    crid.update("minbuf", ElementType.INT, max_size)
    crid.update("avbps", ElementType.INT, bitrate)
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
    header.update("width", ElementType.INT, ffprobe_video_stream.get("width"))
    header.update("height", ElementType.INT, ffprobe_video_stream.get("height"))
    header.update("mat_width", ElementType.INT, ffprobe_video_stream.get("width"))
    header.update("mat_height", ElementType.INT, ffprobe_video_stream.get("height"))
    header.update("disp_width", ElementType.INT, ffprobe_video_stream.get("width"))
    header.update("disp_height", ElementType.INT, ffprobe_video_stream.get("height"))
    header.update("scrn_width", ElementType.INT, 0)
    header.update("mpeg_dcprec", ElementType.CHAR, mpeg_dcprec)
    header.update("mpeg_codec", ElementType.CHAR, mpeg_codec)
    # TODO: Check if videos has transparency
    header.update("alpha_type", ElementType.INT, 0)
    header.update("total_frames", ElementType.INT, num_frames)
    header.update("framerate_n", ElementType.INT, int(framerate * 1000))
    header.update("framerate_d", ElementType.INT, 1000)
    header.update("metadata_count", ElementType.INT, 1)
    header.update("metadata_size", ElementType.INT, num_keyframes)
    header.update("ixsize", ElementType.INT, max_packed_size)
    # TODO: What are the other values for these and what do they mean
    header.update("pre_padding", ElementType.INT, 0)
    header.update("max_picture_size", ElementType.INT, 0)
    header.update("color_space", ElementType.INT, 0)
    header.update("picture_type", ElementType.INT, 0)
    return header
