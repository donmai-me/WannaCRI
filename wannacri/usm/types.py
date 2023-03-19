from __future__ import annotations
from enum import Enum, auto
from typing import List

from .tools import bytes_to_hex


class ChunkType(Enum):
    INFO = b"CRID"
    VIDEO = b"@SFV"
    AUDIO = b"@SFA"
    ALPHA = b"@ALP"
    SUBTITLE = b"@SBT"
    CUE = b"@CUE"

    # Rare chunk types from Youjose's PyCriCodecs
    SFSH = b"SFSH"
    AHX = b"@AHX"
    USR = b"@USR"
    PST = b"@PST"

    @staticmethod
    def from_bytes(data: bytes) -> ChunkType:
        data = bytearray(data)
        enums = [(enum.value, enum) for enum in ChunkType]
        for enum_value, enum_type in enums:
            if data[:4] == enum_value:
                return enum_type

        raise ValueError(f"Unknown chunk signature: {bytes_to_hex(data[:4])}")

    @staticmethod
    def all_values() -> List[bytes]:
        return [enum.value for enum in ChunkType]

    @staticmethod
    def is_valid_chunk(signature: bytes) -> bool:
        """Check if the first four bytes of a chunk are valid Usm chunks.
        Returns true if valid, and false if invalid or the given input is less
        than four bytes.
        """
        if len(signature) < 4:
            return False

        valid_signatures = ChunkType.all_values()
        return signature[:4] in valid_signatures

    def to_int(self) -> int:
        return int.from_bytes(self.value, "big")

    def __str__(self):
        return str(self.value, "UTF-8")


class PayloadType(Enum):
    STREAM = 0
    HEADER = 1
    SECTION_END = 2
    METADATA = 3

    @staticmethod
    def from_int(value: int) -> PayloadType:
        enums = [(enum.value, enum) for enum in PayloadType]
        for enum_value, enum_type in enums:
            if value == enum_value:
                return enum_type

        raise ValueError(f"Value {value} is outside of valid values.")


class ElementOccurrence(Enum):
    RECURRING = 1
    NON_RECURRING = 2

    @staticmethod
    def from_int(value: int) -> ElementOccurrence:
        enums = [(enum.value, enum) for enum in ElementOccurrence]
        for enum_value, enum_type in enums:
            if value == enum_value:
                return enum_type

        raise ValueError(f"Value {value} is outside of valid values.")


class ElementType(Enum):
    I8 = 0x10  # 1 byte
    U8 = 0x11  # 1 byte
    I16 = 0x12  # 2 bytes
    U16 = 0x13  # 2 bytes
    I32 = 0x14  # 4 bytes
    U32 = 0x15  # 4 bytes
    I64 = 0x16  # 8 bytes
    U64 = 0x17  # 8 bytes
    F32 = 0x18  # 4 bytes
    # TODO: Confirm f64's existence
    F64 = 0x19  # 8 bytes
    STRING = 0x1A  # Null byte terminated
    BYTES = 0x1B  # Bytes

    @staticmethod
    def from_int(value: int) -> ElementType:
        enums = [(enum.value, enum) for enum in ElementType]
        for enum_value, enum_type in enums:
            if value == enum_value:
                return enum_type

        raise ValueError(f"Value {value} is outside of valid values.")


class OpMode(Enum):
    NONE = auto()
    ENCRYPT = auto()
    DECRYPT = auto()
