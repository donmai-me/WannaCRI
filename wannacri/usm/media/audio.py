import os.path
import typing
from typing import Generator, Optional, List, Any
import struct
from .protocols import UsmAudio
from ..page import UsmPage
from collections import OrderedDict
from .tools import create_audio_header_page, create_audio_crid_page, AUDIO_CODEC
from pathlib import Path
import math


class GenericAudio(UsmAudio):
    """Generic audios container used for storing audios
    channels in Usm files. Use other containers when creating
    USMs from audios files."""

    def __init__(
        self,
        stream: Generator[bytes, None, None],
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


class HCA(UsmAudio):
    def __init__(
            self,
            filepath: str,
            channel_number: int = 1,
            format_version: int = 0
    ):

        metadata = self._get_metadata(filepath)
        # have no idea how this is done, pure guess based on minbuf guess elsewhere
        minbuf = math.ceil(metadata["CompHeader"]["FrameSize"][0] * 54.4140625)
        # Estimated comparing video fps to audio fps, avg bitrate
        # Framesize bit is sort of extrapolated from that
        avbps = round(0.0399607 * metadata["FormatHeader"]["FrameCount"][0] * metadata["CompHeader"]["FrameSize"][0])

        self._crid_page = create_audio_crid_page(
            Path(filepath).name,
            os.path.getsize(filepath),
            format_version,
            metadata["FormatHeader"]["ChannelCount"][0],
            minbuf,
            avbps
        )

        self._header_page = create_audio_header_page(
            AUDIO_CODEC.HCA,
            metadata["FormatHeader"]["SampleRate"][0],
            metadata["FormatHeader"]["ChannelCount"][0],
            1,  # There should be only one metadata page for HCA
            256,  # HCA metadata is always 256 long I think?
            27860,  # I have no idea
        )

        def packet_gen(
            path: str
        ) -> Generator[typing.Tuple[bytes, bool], None, None]:
            video = open(path, "rb")
            yield video.read(96)
            for i in range(metadata["FormatHeader"]["FrameCount"][0]):
                yield video.read(metadata["CompHeader"]["FrameSize"][0])
            video.close()

        self._stream = packet_gen(filepath)
        self._length = metadata["FormatHeader"]["FrameCount"][0] + 1
        self._channel_number = metadata["FormatHeader"]["ChannelCount"][0]
        self._metadata_pages = None

    def _get_metadata(self, filepath: str):
        metadata_blocks = [HCAHeader, FormatHeader, CompHeader]
        metadata = {}
        seek = 0
        with open(filepath, "rb") as f:
            while metadata_blocks:
                block_id = self._get_metadata_chunk_id(f)
                f.seek(seek)
                for block in metadata_blocks:
                    if block.ID == block_id:
                        data = f.read(block.size())
                        metadata[block.__name__] = block.unpack(data)
                        seek += block.size()
                        metadata_blocks.remove(block)
                        break
        return metadata

    def _get_metadata_chunk_id(self, file: typing.IO):
        format_string = ">cccc"
        size = struct.calcsize(format_string)
        data = struct.unpack(format_string, file.read(size))
        return b"".join(data)


class ClassStruct:
    FORMAT: OrderedDict = OrderedDict()
    CONVERT_TYPES = {}
    @classmethod
    def unpack(cls, string: bytes) -> dict:
        values = {}
        start = 0
        for key, value in cls.FORMAT.items():
            size = struct.calcsize(value)
            values[key] = struct.unpack(value, string[start: start+size])
            start += size
        for key, value in cls.CONVERT_TYPES.items():
            data = bytearray(b"".join(values[key]))
            # doesn't take endianness into account, could break things
            while len(data) % 4 != 0:
                data.insert(0, 0)
            values[key] = struct.unpack(value, data)
        return values

    @classmethod
    def pack(cls, values: dict) -> bytes:
        byte_values = []
        for key, value in cls.FORMAT.items():
            try:
                data = values[key]
            except KeyError:
                raise Exception(f"Key {key} missing in pack dictionary")
            byte_values.append(struct.pack(value, data))
        return b"".join(byte_values)

    @classmethod
    def size(cls):
        return sum([struct.calcsize(value) for value in cls.FORMAT.values()])



class HCAHeader(ClassStruct):
    ID = b'HCA\x00'
    FORMAT = OrderedDict((
        ("Signature", ">cccc"),
        ("VersionMajor", ">B"),
        ("VersionMinor", ">B"),
        ("HeaderSize", ">H"),
    ))


# Only unpacks, does not pack correctly
class FormatHeader(ClassStruct):
    ID = b'fmt\x00'
    FORMAT = OrderedDict((
        ("Signature", ">cccc"),
        ("ChannelCount", ">c"), # 8 bit integer
        ("SampleRate", ">ccc"), # 24 bit integer
        ("FrameCount", ">I"),
        ("InsertedSamples", ">H"),
        ("AppendedSamples", ">H"),
    ))
    CONVERT_TYPES = {
        "ChannelCount": ">I",
        "SampleRate": ">I"
    }

class CompHeader(ClassStruct):
    ID = b"comp"
    FORMAT = OrderedDict((
        ("Signature", ">cccc"),
        ("FrameSize", ">H"),
        ("MinResolution", ">b"),
        ("MaxResolution", ">b"),
        ("TrackCount", ">b"),
        ("ChannelConfig", ">b"),
        ("TotalBandCount", ">B"),
        ("BaseBandCount", ">B"),
        ("StereoBandCount", ">B"),
        ("BandsPerHfrGroup", ">B"),
        ("reserved1", ">b"),
        ("reserved2", ">b"),
    ))
