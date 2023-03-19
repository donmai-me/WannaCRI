from typing import Optional, Generator, Tuple, List, Protocol

from wannacri.usm.types import ChunkType, PayloadType, OpMode
from wannacri.usm.page import UsmPage, ElementType
from wannacri.usm.usm import UsmChunk
from wannacri.usm.tools import (
    encrypt_video_packet,
    decrypt_video_packet,
    slugify,
    encrypt_audio_packet,
    decrypt_audio_packet,
)


class UsmMedia(Protocol):
    """Base protocol for UsmVideo and UsmAudio protocols. Contains
    properties and methods common for both of these protocols.

    See this protocol attributes that needs to be implemented to take advantage
    of default method implementations."""

    # Classes that explicitly inherit UsmAudio and UsmVideo should have
    # these attributes to take advantage of default implementations
    _crid_page: UsmPage
    _header_page: UsmPage
    _length: int
    _channel_number: int
    _metadata_pages: Optional[List[UsmPage]]

    @property
    def crid_page(self) -> UsmPage:
        """A Usm videos or audios's CRIUSF_DIR_STREAM page."""
        return self._crid_page

    @property
    def metadata_pages(self) -> Optional[List[UsmPage]]:
        """An optional list of Usm pages used for Usm Video's
        VIDEO_SEEKINFO and Usm Audio's AUDIO_HDRINFO.

        UsmVideos generated from videos should return None for
        the Usm class' pack method to generate and assign VIDEO_SEEKINFO."""
        return self._metadata_pages

    @metadata_pages.setter
    def metadata_pages(self, pages: Optional[List[UsmPage]]):
        if pages is not None and len(pages) == 0:
            raise ValueError("Given empty list of Usm pages.")

        self._metadata_pages = pages

    @property
    def channel_number(self) -> int:
        return self._channel_number

    @channel_number.setter
    def channel_number(self, new_channel_number: int):
        if new_channel_number < 0:
            raise ValueError(f"Given negative channel number: {new_channel_number}")

        self._channel_number = new_channel_number

    @property
    def header_page(self) -> UsmPage:
        return self._header_page

    @header_page.setter
    def header_page(self, new_header_page: UsmPage):
        self._header_page = new_header_page

    @property
    def filename(self) -> str:
        """A slugified filename, which is stored inside the crid_page.
        Handles case where stored filename is actually a path."""
        filename = self.crid_page["filename"]
        if filename.type is not ElementType.STRING:
            raise ValueError(f"filename is not a string {filename.val}")

        # Handle case when encoded filename is a path.
        result: str = filename.val.split("/")[-1]
        return slugify(result, allow_unicode=True)

    @filename.setter
    def filename(self, new_filename: str):
        new_filename = slugify(new_filename, allow_unicode=True)
        self.crid_page["filename"].type = ElementType.STRING
        self.crid_page["filename"].val = new_filename

    def __len__(self) -> int:
        """The number of packets a Usm videos or audios has."""
        return self._length

    def __lt__(self, other):
        return self.channel_number < other.channel_number

    def __gt__(self, other):
        return self.channel_number > other.channel_number


class UsmVideo(UsmMedia, Protocol):
    """Required protocol for videos objects to be used in Usm generation.
    See UsmMedia protocol for more properties and methods required.

    Explicitly inherit this protocol and implement UsmVideo and
    UsmMedia's attributes to use some or all the default methods."""

    # Classes that explicitly inherit UsmVideo should have this attribute
    # to use the default stream and chunks methods.
    _stream: Generator[Tuple[bytes, bool], None, None]
    is_alpha: bool

    def stream(
        self, mode: OpMode = OpMode.NONE, key: Optional[bytes] = None
    ) -> Generator[Tuple[bytes, bool], None, None]:
        """A generator of bytes from the videos file source
        and a bool which is true when the current packet is a keyframe.
        By default it returns raw bytes but given a mode and key,
        the function generates encrypted or decrypted bytes.

        Args:
            mode: An optional OpMode that instructs the generator
                to encrypt, decrypt, or leave the packets as-is from
                the source videos file. Defaults to OpMode.NONE.
            key: An optional bytes object required for encrypting
                or decrypting the videos packets. Defaults to None.

        Raises:
            ValueError: When key is not supplied when mode is set
                to encrypt or decrypt. And when mode is an unknown
                operation.
        """
        if mode is not OpMode.NONE and key is None:
            raise ValueError("No keys given for encrypt or decrypt mode.")

        for packet, is_keyframe in self._stream:
            if mode is OpMode.NONE:
                payload = packet
            elif mode is OpMode.ENCRYPT:
                payload = encrypt_video_packet(packet, key)
            elif mode is OpMode.DECRYPT:
                payload = decrypt_video_packet(packet, key)
            else:
                raise ValueError(f"Unknown mode {mode}.")

            yield payload, is_keyframe

    def chunks(
        self, mode: OpMode = OpMode.NONE, key: Optional[bytes] = None
    ) -> Generator[Tuple[List[UsmChunk], bool], None, None]:
        """A generator of UsmChunks to be consumed for a Usm file
        and a bool which is true when the current packet is a keyframe.
        At the last packet, two UsmChunk are generated. The second one
        is a SECTION_END payload for the respective Usm video.
        In total this method will yield len(self) chunks.

        By default it generates chunks from raw bytes of the videos
        source but given a mode and key, the function generates
        encrypted or decrypted chunks.

        Args:
            mode: An optional OpMode that instructs the generator
                to encrypt, decrypt, or leave as-is the packets from
                the source videos file. Defaults to OpMode.NONE.
            key: An optional bytes object required for encrypting
                or decrypting the videos packets. Defaults to None.

        Raises:
            ValueError: When key is not supplied when mode is set
                to encrypt or decrypt.
        """
        if mode is not OpMode.NONE and key is None:
            raise ValueError("Key is required for encryption/decryption.")

        framerate_n = self.header_page.get("framerate_n")
        framerate_d = self.header_page.get("framerate_d")
        if framerate_n is not None and framerate_d is not None:
            framerate = int(framerate_n.val) / int(framerate_d.val)
        else:
            framerate = 30

        for i, (payload, is_keyframe) in enumerate(self.stream(mode, key)):
            # TODO: Find real frame_time formula
            frame_time = int(i * 99.9)

            padding_size = (
                0x20 - (len(payload) % 0x20) if len(payload) % 0x20 != 0 else 0
            )

            if i != self._length - 1:
                yield (
                    [
                        UsmChunk(
                            ChunkType.VIDEO,
                            PayloadType.STREAM,
                            payload=payload,
                            frame_rate=int(framerate * 100),
                            frame_time=frame_time,
                            padding=padding_size,
                            channel_number=self.channel_number,
                        )
                    ],
                    is_keyframe,
                )
            else:
                yield (
                    [
                        UsmChunk(
                            ChunkType.VIDEO,
                            PayloadType.STREAM,
                            payload=payload,
                            frame_rate=int(framerate * 100),
                            frame_time=frame_time,
                            padding=padding_size,
                            channel_number=self.channel_number,
                        ),
                        UsmChunk(
                            ChunkType.VIDEO,
                            PayloadType.SECTION_END,
                            payload=bytes("#CONTENTS END   ===============", "UTF-8")
                            + bytes(1),
                            frame_rate=int(framerate * 100),
                            channel_number=self.channel_number,
                        ),
                    ],
                    is_keyframe,
                )


class UsmAudio(UsmMedia, Protocol):
    """Required protocol for audios objects to be used in Usm generation.
    See UsmMedia protocol for more properties and methods required.

    Explicitly inherit this protocol and implement UsmAudio and
    UsmMedia's attributes to use some or all the default methods."""

    # Classes that explicitly inherit UsmAudio should have this attribute
    # to use the default stream and chunks methods.
    _stream: Generator[bytes, None, None]

    def stream(
        self, mode: OpMode = OpMode.NONE, key: Optional[bytes] = None
    ) -> Generator[bytes, None, None]:
        """A generator of bytes from the audios file source.
        By default it returns raw bytes but given a mode and key,
        the function generates encrypted or decrypted bytes.

        Args:
            mode: An optional OpMode that instructs the generator
                to encrypt, decrypt, or leave the packets as-is from
                the source audios file. Defaults to OpMode.NONE.
            key: An optional bytes object required for encrypting
                or decrypting the audios packets. Defaults to None.

        Raises:
            ValueError: When key is not supplied when mode is set
                to encrypt or decrypt. And when mode is an unknown
                operation.
        """
        if mode is not OpMode.NONE and key is None:
            raise RuntimeError("No keys given for encrypt or decrypt mode.")

        for packet in self._stream:
            if mode is OpMode.NONE:
                payload = packet
            elif mode is OpMode.ENCRYPT:
                payload = encrypt_audio_packet(packet, key)
            elif mode is OpMode.DECRYPT:
                payload = decrypt_audio_packet(packet, key)
            else:
                raise ValueError(f"Unknown mode: {mode}.")

            yield payload

    def chunks(
        self, mode: OpMode = OpMode.NONE, key: Optional[bytes] = None
    ) -> Generator[List[UsmChunk], None, None]:
        """A generator of UsmChunks to be consumed for a Usm file.
        The last generated UsmChunk is a SECTION_END payload for
        the respective Usm audios. In total this method will yield
        len(self) + 1 chunks.

        By default it generates chunks from raw bytes of the audios
        source but given a mode and key, the function generates
        encrypted or decrypted chunks.

        Params:
            mode: An optional OpMode that instructs the generator
                to encrypt, decrypt, or leave as-is the packets from
                the source audios file. Defaults to OpMode.NONE.
            key: An optional bytes object required for encrypting
                or decrypting the audios packets. Defaults to None.

        Raises:
            ValueError: When key is not supplied when mode is set
                to encrypt or decrypt.
        """
        if mode in ["encrypt", "decrypt"] and key is None:
            raise ValueError("No key given for encrypt or decrypt mode")

        for i, payload in enumerate(self.stream(mode, key)):
            # TODO: Find real frame_time formula
            frame_time = int(i * 99.9)

            padding_size = (
                0x20 - (len(payload) % 0x20) if len(payload) % 0x20 != 0 else 0
            )

            # If last packet, return two chunks. The second chunk is a section end chunk
            if i != self._length - 1:
                yield [
                    UsmChunk(
                        ChunkType.AUDIO,
                        PayloadType.STREAM,
                        payload=payload,
                        frame_rate=3000,
                        frame_time=frame_time,
                        channel_number=self.channel_number,
                        padding=padding_size,
                    )
                ]
            else:
                yield [
                    UsmChunk(
                        ChunkType.AUDIO,
                        PayloadType.STREAM,
                        payload=payload,
                        frame_rate=3000,
                        frame_time=frame_time,
                        channel_number=self.channel_number,
                        padding=padding_size,
                    ),
                    UsmChunk(
                        ChunkType.AUDIO,
                        PayloadType.SECTION_END,
                        payload=bytes("#CONTENTS END   ===============", "UTF-8")
                        + bytes(1),
                        frame_rate=3000,
                        channel_number=self.channel_number,
                    ),
                ]
