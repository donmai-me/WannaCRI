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

    @property
    def header_page(self) -> UsmPage:
        return self._header_page

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
        self, mode: OpMode.NONE, key: Optional[bytes] = None
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


# TODO: Delete the comments when done rewriting

# class VP9:
#     def __init__(self, filepath: str):
#         self.filename = os.path.basename(filepath)
#         self.filesize = os.path.getsize(filepath)
#         self.info = ffmpeg.probe(filepath, show_entries="packet=dts,pts_time,pos,flags")

#         if len(self.info.get("streams")) == 0:
#             raise Exception("No streams found")
#         elif len(self.info.get("streams")) > 1:
#             raise NotImplementedError("Can only accept one stream")
#         elif self.info.get("format").get("format_name") != "ivf":
#             raise Exception("Not an ivf file")
#         elif self.info.get("streams")[0].get("codec_name") != "vp9":
#             raise Exception("Not a VP9 videos")

#         video_stream = self.info.get("streams")[0]
#         self.bitrate = int(self.info.get("format").get("bit_rate"))
#         self.width = int(video_stream.get("width"))
#         self.height = int(video_stream.get("height"))
#         self.framerate_n = int(video_stream.get("r_frame_rate").split("/")[0])
#         self.framerate_d = int(video_stream.get("r_frame_rate").split("/")[1])

#         self.frames = self.info.get("packets")
#         self.keyframes = [frame for frame in self.frames if frame.get("flags") == "K_"]
#         self.total_frames = len(self.frames)
#         self.file = open(filepath, "rb")

#     def export(
#         self, encrypt: bool, key: Optional[int] = None, encoding: str = "UTF-8"
#     ) -> bytes:
#         if encrypt:
#             video_key1, video_key2, _ = generate_keys(key)

#         debug = open("FRAME_TIME_DEBUG", "w+")
#         stream_chunks = bytearray()
#         keyframe_usm_offsets = []
#         max_frame_size = 0
#         max_packed_frame_size = 0
#         max_keyframe_to_keyframe_size = 0
#         current_keyframe_to_keyframe_size = 0
#         self.file.seek(0, 0)
#         for i, frame in enumerate(self.frames):
#             # frame_time formula is based on existing usm files.
#             # TODO: Does this hold up for videos that's not 30fps?
#             debug.write("Frame {}: time = {}".format(i, frame.get("pts_time")))
#             # frame_time = int(99.86891 * i)
#             frame_time = int(i * 99.9)
#             if frame in self.keyframes:
#                 keyframe_usm_offsets.append(len(stream_chunks))

#             if i == len(self.frames) - 1:
#                 # Last frame
#                 frame_size = self.filesize - int(frame.get("pos"))
#             else:
#                 frame_size = int(self.frames[i + 1].get("pos")) - int(frame.get("pos"))

#             if i == 0:
#                 # Include 32 byte header for first frame
#                 max_frame_size = frame_size + 32
#                 packet = self.file.read(frame_size + 32)
#             else:
#                 if frame_size > max_frame_size:
#                     max_frame_size = frame_size

#                 packet = self.file.read(frame_size)

#             if frame.get("flags") != "K_":
#                 current_keyframe_to_keyframe_size += frame_size
#             elif current_keyframe_to_keyframe_size > max_keyframe_to_keyframe_size:
#                 max_keyframe_to_keyframe_size = current_keyframe_to_keyframe_size
#                 current_keyframe_to_keyframe_size = frame_size

#             if encrypt:
#                 packet = encrypt_video_packet(packet, video_key1, video_key2)

#             padding_size = 0x20 - (len(packet) % 0x20) if len(packet) % 0x20 != 0 else 0
#             packed_frame_chunk = generate_packed_chunk(
#                 "@SFV",
#                 0,
#                 int(100 * self.framerate_n / self.framerate_d),
#                 frame_time,
#                 packet,
#                 padding_size,
#             )
#             if len(packed_frame_chunk) > max_packed_frame_size:
#                 max_packed_frame_size = len(packed_frame_chunk)

#             stream_chunks += packed_frame_chunk

#         stream_chunks += generate_packed_chunk(
#             "@SFV",
#             2,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             bytes("#CONTENTS END   ===============", "UTF-8") + bytes(1),
#             0,
#         )

#         seek_chunks = bytearray()
#         keyframe_pages = []
#         video_header_end_offset = get_video_header_end_offset(len(self.keyframes))
#         # Offset of videos header end offset plus length of videos header end
#         stream_offset = video_header_end_offset + 0x40
#         for i, keyframe in enumerate(self.keyframes):
#             keyframe_usm_offset = keyframe_usm_offsets[i]
#             keyframe_offset = stream_offset + keyframe_usm_offset
#             keyframe_page = UsmPage("VIDEO_SEEKINFO", i)
#             keyframe_page.add("ofs_byte", ElementType.clonglong, keyframe_offset)
#             keyframe_page.add("ofs_frmid", ElementType.cuint, keyframe.get("dts"))
#             keyframe_page.add("num_skip", ElementType.cushort, 0)
#             keyframe_page.add("resv", ElementType.cushort, 0)
#             keyframe_pages.append(keyframe_page)

#         seek_chunks_payload = pack_pages(keyframe_pages, string_padding=1)
#         # 0x20 bytes for chunk header.
#         seek_chunks_padding = (
#             video_header_end_offset - 0xA40 - 0x20 - len(seek_chunks_payload)
#         )
#         seek_chunks += generate_packed_chunk(
#             "@SFV",
#             3,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             seek_chunks_payload,
#             seek_chunks_padding,
#         )
#         metadata_size = len(seek_chunks)
#         seek_chunks += generate_packed_chunk(
#             "@SFV",
#             2,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             bytes("#METADATA END   ===============", "UTF-8") + bytes(1),
#             0,
#         )

#         header_page = UsmPage("VIDEO_HDRINFO", 0)
#         header_page.add("width", ElementType.cint, self.width)
#         header_page.add("height", ElementType.cint, self.height)
#         header_page.add("mat_width", ElementType.cint, self.width)
#         header_page.add("mat_height", ElementType.cint, self.height)
#         header_page.add("disp_width", ElementType.cint, self.width)
#         header_page.add("disp_height", ElementType.cint, self.height)
#         header_page.add("scrn_width", ElementType.cint, 0)
#         header_page.add("mpeg_dcprec", ElementType.cchar, 0)
#         header_page.add("mpeg_codec", ElementType.cchar, 9)
#         # TODO: Check if videos has transparency
#         header_page.add("alpha_type", ElementType.cint, 0)
#         header_page.add("total_frames", ElementType.cint, self.total_frames)

#         framerate_n = self.framerate_n
#         framerate_d = self.framerate_d

#         if framerate_d < 1000 and framerate_d != 1000:
#             framerate_d *= 1000
#             framerate_n *= 1000

#         header_page.add("framerate_n", ElementType.cint, framerate_n)
#         header_page.add("framerate_d", ElementType.cint, framerate_d)
#         header_page.add("metadata_count", ElementType.cint, 1)
#         header_page.add("metadata_size", ElementType.cint, metadata_size)
#         header_page.add("ixsize", ElementType.cint, max_packed_frame_size)
#         header_page.add("pre_padding", ElementType.cint, 0)
#         header_page.add("max_picture_size", ElementType.cint, 0)
#         header_page.add("color_space", ElementType.cint, 0)
#         header_page.add("picture_type", ElementType.cint, 0)

#         header_chunk_payload = pack_pages([header_page])
#         header_chunk_padding = 0xA00 - 0x800 - 0x20 - len(header_chunk_payload)
#         header_chunk = bytearray()
#         header_chunk += generate_packed_chunk(
#             "@SFV",
#             1,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             header_chunk_payload,
#             header_chunk_padding,
#         )
#         header_chunk += generate_packed_chunk(
#             "@SFV",
#             2,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             bytes("#HEADER END     ===============", "UTF-8") + bytes(1),
#             0,
#         )

#         directory_pages = []
#         for i in range(0, 2):
#             if i == 0:
#                 filename = os.path.splitext(self.filename)[0] + ".usm"
#                 # filename = r"I:\000125 千本桜\000125.usm"
#                 filesize = (
#                     0x800 + len(header_chunk) + len(seek_chunks) + len(stream_chunks)
#                 )
#                 stmid = 0
#                 chno = -1
#                 minchk = 1
#                 # TODO: Find formula for minbuf for usm
#                 minbuf = round(1.98746 * max_frame_size)
#                 minbuf += 0x10 - (minbuf % 0x10) if minbuf % 0x10 != 0 else 0
#             else:
#                 filename = self.filename
#                 # filename = r"I:\000125 千本桜\000125.ivf"

#                 filesize = self.filesize
#                 stmid = 1079199318  # @SFV
#                 chno = 0
#                 minchk = 3
#                 minbuf = max_frame_size

#             directory_part = UsmPage("CRIUSF_DIR_STREAM", 0)
#             directory_part.add("fmtver", ElementType.cint, 16777984)
#             directory_part.add("filename", ElementType.cstring, filename)
#             directory_part.add("filesize", ElementType.cint, filesize)
#             directory_part.add("datasize", ElementType.cint, 0)
#             directory_part.add("stmid", ElementType.cint, stmid)
#             directory_part.add("chno", ElementType.cshort, chno)
#             directory_part.add("minchk", ElementType.cshort, minchk)
#             directory_part.add("minbuf", ElementType.cint, minbuf)
#             directory_part.add("avbps", ElementType.cint, self.bitrate)
#             directory_pages.append(directory_part)

#         directory_chunk_payload = pack_pages(directory_pages, encoding, 5)
#         directory_chunk_padding = 0x800 - 0x20 - len(directory_chunk_payload)
#         directory_chunk = bytearray()
#         directory_chunk += generate_packed_chunk(
#             "CRID",
#             1,
#             int(self.framerate_n / self.framerate_d),
#             0,
#             directory_chunk_payload,
#             directory_chunk_padding,
#         )
#         result = directory_chunk + header_chunk + seek_chunks + stream_chunks
#         return bytes(result)

#     def close(self):
#         self.file.close()
