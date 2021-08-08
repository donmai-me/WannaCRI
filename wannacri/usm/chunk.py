from __future__ import annotations
import logging
from typing import List, Union, Callable

from .types import ChunkType, PayloadType
from .page import UsmPage, pack_pages, get_pages
from .tools import bytes_to_hex, is_valid_chunk


class UsmChunk:
    def __init__(
        self,
        chunk_type: ChunkType,
        payload_type: PayloadType,
        payload: Union[bytes, List[UsmPage]],
        frame_rate: int = 30,
        frame_time: int = 0,
        padding: Union[int, Callable[[int], int]] = 0,
        channel_number: int = 0,
        payload_offset: int = 0x18,
        encoding: str = "UTF-8",
    ):
        self.chunk_type = chunk_type
        self.payload_type = payload_type
        self.payload = payload
        self.frame_rate = frame_rate
        self.frame_time = frame_time
        self._padding = padding
        self.channel_number = channel_number
        self.payload_offset = payload_offset
        self.encoding = encoding

    @property
    def padding(self) -> int:
        """The number of byte padding a chunk will have when packed."""
        if isinstance(self._padding, int):
            return self._padding

        if isinstance(self.payload, list):
            payload_size = len(pack_pages(self.payload, self.encoding))
        else:
            payload_size = len(self.payload)

        return self._padding(0x20 + payload_size)

    def __len__(self) -> int:
        """Returns the packed length of a chunk. Including _padding."""
        if isinstance(self.payload, list):
            payload_size = len(pack_pages(self.payload, self.encoding))
        else:
            payload_size = len(self.payload)

        if isinstance(self._padding, int):
            padding = self._padding
        else:
            padding = self._padding(0x20 + payload_size)

        return 0x20 + payload_size + padding

    @classmethod
    def from_bytes(cls, chunk: bytes, encoding: str = "UTF-8") -> UsmChunk:
        chunk = bytearray(chunk)
        signature = chunk[:0x4]

        chunksize = int.from_bytes(chunk[0x4:0x8], "big")
        # r08: 1 byte
        payload_offset = chunk[0x9]
        padding = int.from_bytes(chunk[0xA:0xC], "big")
        channel_number = chunk[0xC]
        # r0D: 1 byte
        # r0E: 1 byte

        payload_type = PayloadType.from_int(chunk[0xF] & 0x3)

        frame_time = int.from_bytes(chunk[0x10:0x14], "big")
        frame_rate = int.from_bytes(chunk[0x14:0x18], "big")
        # r18: 4 bytes
        # r1C: 4 bytes

        logging.debug(
            "UsmChunk: Chunk type: %s, chunk size: %x, r08: %x, payload offset: %x "
            + "padding: %x, chno: %x, r0D: %x, r0E: %x, payload type: %s "
            + "frame time: %x, frame rate: %d, r18: %s, r1C: %s",
            bytes_to_hex(signature),
            chunksize,
            chunk[0x8],
            payload_offset,
            padding,
            channel_number,
            chunk[0xD],
            chunk[0xE],
            payload_type,
            frame_time,
            frame_rate,
            bytes_to_hex(chunk[0x18:0x1C]),
            bytes_to_hex(chunk[0x1C:0x20]),
        )

        if not is_valid_chunk(signature):
            raise ValueError(f"Invalid signature: {bytes_to_hex(signature)}")

        payload_begin = 0x08 + payload_offset
        payload_size = chunksize - padding - payload_offset
        payload: bytearray = chunk[payload_begin : payload_begin + payload_size]

        # Get pages for header and seek payload types
        if payload_type in [PayloadType.HEADER, PayloadType.METADATA]:
            payload: List[UsmPage] = get_pages(payload, encoding)
            for page in payload:
                logging.debug("Name: %s, Contents: %s", page.name, page.dict)

        return cls(
            ChunkType.from_bytes(signature),
            payload_type,
            payload,
            frame_rate,
            frame_time=frame_time,
            padding=padding,
            channel_number=channel_number,
            payload_offset=payload_begin,
        )

    def pack(self) -> bytes:
        result = bytearray()
        result += self.chunk_type.value

        if isinstance(self.payload, list):
            payload = pack_pages(self.payload, self.encoding)
        else:
            payload = self.payload

        if isinstance(self._padding, int):
            padding = self._padding
        else:
            padding = self._padding(0x20 + len(payload))

        chunksize = 0x18 + len(payload) + padding
        result += chunksize.to_bytes(4, "big")
        result += bytes(1)
        result += (0x18).to_bytes(1, "big")
        result += padding.to_bytes(2, "big")
        result += self.channel_number.to_bytes(1, "big")
        result += bytes(2)
        result += self.payload_type.value.to_bytes(1, "big")
        result += self.frame_time.to_bytes(4, "big")
        result += self.frame_rate.to_bytes(4, "big")

        result += bytearray(8)
        result += payload
        result += bytearray(padding)
        return bytes(result)
