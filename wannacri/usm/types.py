from __future__ import annotations
from enum import Enum, auto

from .tools import bytes_to_hex


class ChunkType(Enum):
    INFO = bytearray("CRID", "UTF-8")
    VIDEO = bytearray("@SFV", "UTF-8")
    AUDIO = bytearray("@SFA", "UTF-8")

    @staticmethod
    def from_bytes(data: bytes) -> ChunkType:
        data = bytearray(data)
        enums = [(enum.value, enum) for enum in ChunkType]
        for enum_value, enum_type in enums:
            if data[:4] == enum_value:
                return enum_type

        raise ValueError(f"Unknown chunk signature: {bytes_to_hex(data[:4])}")


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


class ArrayType(Enum):
    SHARED = 1
    UNIQUE = 2

    @staticmethod
    def from_int(value: int) -> ArrayType:
        enums = [(enum.value, enum) for enum in ArrayType]
        for enum_value, enum_type in enums:
            if value == enum_value:
                return enum_type

        raise ValueError(f"Value {value} is outside of valid values.")


class ElementType(Enum):
    CHAR = 0x10  # 1 byte
    UCHAR = 0x11  # 1 byte
    SHORT = 0x12  # 2 bytes
    USHORT = 0x13  # 2 bytes
    INT = 0x14  # 4 bytes
    UINT = 0x15  # 4 bytes
    LONGLONG = 0x16  # 8 bytes
    ULONGLONG = 0x17  # 8 bytes
    FLOAT = 0x18  # 4 bytes
    # TODO: Confirm DOUBLE's existence
    # DOUBLE = 0x19 # 8 bytes
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
