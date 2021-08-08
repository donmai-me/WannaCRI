import math
from typing import Tuple, IO, List, Callable
import threading
import unicodedata
import re


def slugify(value, allow_unicode=True):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    with modifications. Convert to ASCII if 'allow_unicode' is False.
    Convert spaces or repeated dashes to single dashes. Remove characters that
    aren't alphanumerics, underscores, dots, commas, pluses, or hyphens. Convert to lowercase.
    Also strip leading and trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

    value = re.sub(r"[^\w\s.,+-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def is_valid_chunk(signature: bytes) -> bool:
    """Check if the first four bytes of a chunk are valid Usm chunks.
    Returns true if valid, and false if invalid or the given input is less
    than four bytes.
    """
    signature = bytearray(signature)
    if len(signature) < 4:
        return False

    valid_signatures = [
        bytearray("CRID", "UTF-8"),  # CRI USF DIR STREAM
        bytearray("@SFV", "UTF-8"),  # Video
        bytearray("@SFA", "UTF-8"),  # Audio
    ]
    return signature[:4] in valid_signatures


def chunk_size_and_padding(header: bytes) -> Tuple[int, int]:
    header = bytearray(header)
    signature = header[0:4]
    if not is_valid_chunk(signature):
        raise ValueError("Invalid signature")

    size = int.from_bytes(header[4:8], "big")
    offset = header[9]
    padding_size = int.from_bytes(header[10:12], "big")
    size -= offset + padding_size
    if size < 0:
        raise ValueError("Negative size")

    return size, padding_size


def generate_keys(key_num: int) -> Tuple[bytes, bytes]:
    """Taken from Usm.crid, adapted for Python 3.
    Takes a integer that can fit in at most 8 bytes and generates 2 keys.
    Returns 2 bytes type in the following order: Video key and audios key.
    Video key has length of 0x40 bytes, and audios key has length of 0x20 bytes.
    """
    cipher_key = key_num.to_bytes(8, "little")

    key = bytearray(0x20)
    key[0x00] = cipher_key[0]
    key[0x01] = cipher_key[1]
    key[0x02] = cipher_key[2]
    key[0x03] = (cipher_key[3] - 0x34) & 0xFF
    key[0x04] = (cipher_key[4] + 0xF9) & 0xFF
    key[0x05] = cipher_key[5] ^ 0x13
    key[0x06] = (cipher_key[6] + 0x61) & 0xFF
    key[0x07] = key[0x00] ^ 0xFF
    key[0x08] = (key[0x01] + key[0x02]) & 0xFF
    key[0x09] = (key[0x01] - key[0x07]) & 0xFF
    key[0x0A] = key[0x02] ^ 0xFF
    key[0x0B] = key[0x01] ^ 0xFF
    key[0x0C] = (key[0x0B] + key[0x09]) & 0xFF
    key[0x0D] = (key[0x08] - key[0x03]) & 0xFF
    key[0x0E] = key[0x0D] ^ 0xFF
    key[0x0F] = (key[0x0A] - key[0x0B]) & 0xFF
    key[0x10] = (key[0x08] - key[0x0F]) & 0xFF
    key[0x11] = key[0x10] ^ key[0x07]
    key[0x12] = key[0x0F] ^ 0xFF
    key[0x13] = key[0x03] ^ 0x10
    key[0x14] = (key[0x04] - 0x32) & 0xFF
    key[0x15] = (key[0x05] + 0xED) & 0xFF
    key[0x16] = key[0x06] ^ 0xF3
    key[0x17] = (key[0x13] - key[0x0F]) & 0xFF
    key[0x18] = (key[0x15] + key[0x07]) & 0xFF
    key[0x19] = (0x21 - key[0x13]) & 0xFF
    key[0x1A] = key[0x14] ^ key[0x17]
    key[0x1B] = (key[0x16] + key[0x16]) & 0xFF
    key[0x1C] = (key[0x17] + 0x44) & 0xFF
    key[0x1D] = (key[0x03] + key[0x04]) & 0xFF
    key[0x1E] = (key[0x05] - key[0x16]) & 0xFF
    key[0x1F] = key[0x1D] ^ key[0x13]

    audio_t = bytes("URUC", "UTF-8")
    video_key = bytearray(0x40)
    audio_key = bytearray(0x20)

    for i in range(0x20):
        video_key[i] = key[i]
        video_key[0x20 + i] = key[i] ^ 0xFF
        audio_key[i] = audio_t[(i >> 1) % 4] if i % 2 != 0 else key[i] ^ 0xFF

    return bytes(video_key), bytes(audio_key)


def decrypt_video_packet(packet: bytes, video_key: bytes) -> bytes:
    """Decrypt an encrypted videos stream payload. Skips decryption if packet is
    less than 0x240 bytes.
    """
    if len(video_key) < 0x40:
        raise ValueError(f"Video key should be 0x40 bytes long. Given {len(video_key)}")

    data = bytearray(packet)
    encrypted_part_size = len(data) - 0x40
    if encrypted_part_size >= 0x200:
        rolling = bytearray(video_key)
        for i in range(0x100, encrypted_part_size):
            data[0x40 + i] ^= rolling[0x20 + i % 0x20]
            rolling[0x20 + i % 0x20] = data[0x40 + i] ^ video_key[0x20 + i % 0x20]

        for i in range(0x100):
            rolling[i % 0x20] ^= data[0x140 + i]
            data[0x40 + i] ^= rolling[i % 0x20]

    return bytes(data)


def encrypt_video_packet(packet: bytes, video_key: bytes) -> bytes:
    """Encrypt an encrypted videos stream payload. Skips decryption if packet is
    less than 0x240 bytes.
    """
    if len(video_key) < 0x40:
        raise ValueError(f"Video key should be 0x40 bytes long. Given {len(video_key)}")

    data = bytearray(packet)
    if len(data) >= 0x240:
        encrypted_part_size = len(data) - 0x40
        rolling = bytearray(video_key)
        for i in range(0x100):
            rolling[i % 0x20] ^= data[0x140 + i]
            data[0x40 + i] ^= rolling[i % 0x20]

        for i in range(0x100, encrypted_part_size):
            plainbyte = data[0x40 + i]
            data[0x40 + i] ^= rolling[0x20 + i % 0x20]
            rolling[0x20 + i % 0x20] = plainbyte ^ video_key[0x20 + i % 0x20]

    return bytes(data)


def _crypt_audio_packet(packet: bytes, key: bytes) -> bytes:
    """Encrypt/decrypt a plaintext/encrypted audios stream payload. Skips encryption/decryption
    if packet is less than or equal to 0x140 bytes.
    """
    data = bytearray(packet)
    if len(data) > 0x140:
        for i in range(0x140, len(data)):
            data[i] ^= key[i % 0x20]

    return bytes(data)


# Encrypting and decrypting audios stream payload are the same operation
encrypt_audio_packet = _crypt_audio_packet
decrypt_audio_packet = _crypt_audio_packet


# TODO: Rename this to get_metadata_end_offset
# TODO: Generalize to multiple CD sectors
def pad_to_next_sector(position: int) -> Callable[[int], int]:
    def pad(chunk_size: int) -> int:
        unpadded_position = position + chunk_size
        multiple = math.ceil(unpadded_position / 0x800)
        return 0x800 * multiple - unpadded_position

    return pad


def get_video_header_end_offset(num_keyframes: int) -> int:
    seek_info_offset = 0xA40
    # 0x20 for part headers and another 0x20 for pages headers
    seek_info_headers_size = 0x40
    strings_size = 0x38
    # There are four elements for every page: ofs_byte, ofs_frmid,
    # num_skip, and resv.
    # 1 byte for every element's type, 4 bytes for every element's name offset.
    # Then add the sizes of all elements with common values: num_skip
    # and resv. num_skip and resv are both shorts (2 bytes)
    s_array_size = 1 * 4 + 4 * 4 + 2 + 2
    # d_array contains all element values that can differ. For VIDEO_SEEKINFO
    # it is ofs_byte and ofs_frmid. ofs_byte is a longlong (8 bytes)
    # and ofs_frmid is an int (4 bytes)
    d_array_size = num_keyframes * 8 + num_keyframes * 4
    total_size = (
        seek_info_offset
        + seek_info_headers_size
        + s_array_size
        + d_array_size
        + strings_size
    )
    # Offset is always a multiple of 0x80
    padding = 0x80 - (total_size % 0x80)
    return total_size + padding


def bytes_to_hex(data: bytes) -> str:
    result = ""
    for byte in bytearray(data):
        result += "{:02x} ".format(byte)

    return result


def is_usm(magic: bytes) -> bool:
    magic = bytearray(magic)
    if len(magic) < 4:
        return False

    return magic[:4] == bytearray("CRID", "UTF-8")


def video_sink(
    usmfile: IO,
    usmmutex: threading.Lock,
    offsets_and_sizes: List[Tuple[int, int]],
    keyframes: List[int],
):
    """A generator for videos chunk payloads. Takes a handle of a usm file, a mutex,
    a list of tuples of a chunk payload's offset and size, and a list of keyframes'
    frame number.

    Yields the raw chunk payload and a bool whether the frame is a keyframe or not.
    All in chronological order."""
    num_frames = len(offsets_and_sizes)
    for i in range(num_frames):
        offset, size = offsets_and_sizes[i]
        is_keyframe = i in keyframes
        with usmmutex:
            usmfile.seek(offset)
            frame = usmfile.read(size)

        yield frame, is_keyframe


def audio_sink(usmfile: IO, usmmutex: threading.Lock, offsets_and_sizes: list):
    """A generator for audios chunk payloads. Takes a handle of a usm file, a mutex,
    and a list of tuples of a chunk payload's offset and size.

    Yields the raw chunk payload in chronological order."""
    num_frames = len(offsets_and_sizes)
    for i in range(num_frames):
        offset, size = offsets_and_sizes[i]
        with usmmutex:
            usmfile.seek(offset)
            frame = usmfile.read(size)

        yield frame
