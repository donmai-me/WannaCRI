from __future__ import annotations
import logging
from typing import List, Union, Callable

from .types import ChunkType, PayloadType
from .page import UsmPage, pack_pages, get_pages
from .tools import bytes_to_hex, is_payload_list_pages


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
        """Initialise UsmChunk from raw bytes."""
        chunk = bytearray(chunk)
        try:
            chunk_type: Union[ChunkType, bytes] = ChunkType.from_bytes(chunk[:0x4])
        except ValueError:
            chunk_type = chunk[:0x4]

        chunksize = int.from_bytes(chunk[0x4:0x8], "big")
        # r08: 1 byte
        payload_offset = chunk[0x9]
        padding_size = int.from_bytes(chunk[0xA:0xC], "big")
        channel_number = chunk[0xC]
        # r0D: 1 byte
        # r0E: 1 byte

        frame_time = int.from_bytes(chunk[0x10:0x14], "big")
        frame_rate = int.from_bytes(chunk[0x14:0x18], "big")
        # r18: 4 bytes
        # r1C: 4 bytes

        payload_begin = 0x08 + payload_offset
        payload_size = chunksize - padding_size - payload_offset
        payload_raw = chunk[payload_begin : payload_begin + payload_size]

        try:
            payload_type: Union[PayloadType, int] = PayloadType.from_int(
                chunk[0xF] & 0x3
            )
        except ValueError:
            logging.debug(
                "Chunk unknown payload", extra={"payload": bytes_to_hex(payload_raw)}
            )
            payload_type = chunk[0xF]

        logging.debug(
            "Chunk info",
            extra={
                "type": chunk_type
                if isinstance(chunk_type, ChunkType)
                else bytes_to_hex(chunk_type),
                "chunksize_after_header": chunksize,
                "r08": chunk[0x8],
                "payload_offset": payload_offset,
                "padding_size": padding_size,
                "channel_number": channel_number,
                "r0D_r0E": bytes_to_hex(chunk[0xD:0xF]),
                "payload_type": payload_type,
                "frame_time": frame_time,
                "frame_rate": frame_rate,
                "r18_r1B": bytes_to_hex(chunk[0x18:0x1C]),
                "r1C_r1F": bytes_to_hex(chunk[0x1C:0x20]),
            },
        )

        if not isinstance(chunk_type, ChunkType):
            raise ValueError(f"Invalid signature: {bytes_to_hex(chunk_type)}")

        if not isinstance(payload_type, PayloadType):
            raise ValueError(f"Invalid payload type: {payload_type}")

        if is_payload_list_pages(payload_raw[:4]):
            payload: Union[List[UsmPage], bytearray] = get_pages(payload_raw, encoding)
            logging.debug(
                "Page list payload content",
                extra={
                    "page_name": payload[0].name if len(payload) > 0 else None,
                    "num_entries": len(payload),
                    "contents": [page.dict for page in payload],
                },
            )
        else:
            payload = payload_raw

        return cls(
            chunk_type,
            payload_type,
            payload,
            frame_rate,
            frame_time=frame_time,
            padding=padding_size,
            channel_number=channel_number,
            payload_offset=payload_begin,
        )

    def pack(self) -> bytes:
        """Transform UsmChunk to raw bytes."""
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
