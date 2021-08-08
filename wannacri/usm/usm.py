from __future__ import annotations

import math
import os
import logging
import pathlib
import threading
from collections import defaultdict
from dataclasses import dataclass
from tempfile import TemporaryFile
from typing import List, Optional, Union, Tuple, Dict, Generator, IO, Callable

from .tools import (
    generate_keys,
    chunk_size_and_padding,
    bytes_to_hex,
    is_usm,
    video_sink,
    audio_sink,
    slugify,
    pad_to_next_sector,
)
from .types import ChunkType, PayloadType, ElementType, OpMode
from .page import UsmPage, keyframes_from_seek_pages
from .chunk import UsmChunk
from .media import GenericVideo, GenericAudio, UsmVideo, UsmAudio


@dataclass
class UsmChannel:
    """Intermediate class for holding information on a UsmVideo
    and UsmAudio from a parsed Usm."""

    stream: List[Tuple[int, int]]
    header: UsmPage
    metadata: Optional[List[UsmPage]] = None


class Usm:
    def __init__(
        self,
        video: List[UsmVideo],
        audio: Optional[List[UsmAudio]] = None,
        key: Optional[int] = None,
        usm_crid: Optional[UsmPage] = None,
        version: int = 16777984,
    ) -> None:
        if len(video) == 0:
            raise ValueError("No videos given.")

        if audio is None:
            self.audios = []
        else:
            self.audios = audio
            self.audios.sort()

        self.version = version
        self.videos = video
        self.videos.sort()

        self._usm_crid = usm_crid
        self._max_packet_size = 1

        logging.info("Usm format version: %x", self.version)
        logging.info(
            "%d videos channels and %d audios channels given",
            len(self.videos),
            len(self.audios),
        )

        self.max_frame = 0
        for vid in self.videos:
            self.max_frame = max(self.max_frame, len(vid))

        for aud in self.audios:
            self.max_frame = max(self.max_frame, len(aud))

        if key is None:
            self.video_key: Optional[bytes] = None
            self.audio_key: Optional[bytes] = None
        else:
            logging.info("Key provided")
            self.video_key, self.audio_key = generate_keys(key)

    @property
    def filename(self) -> str:
        if self._usm_crid is not None:
            return self._usm_crid.get("filename").val.split("/")[-1]

        return (
            self.videos[0].crid_page.get("filename").val.split("/")[-1].split(".")[0]
            + ".usm"
        )

    def usm_crid_page(self, size_after_crid_part: Optional[int] = None) -> UsmPage:
        if self._usm_crid is not None:
            return self._usm_crid

        if size_after_crid_part is None:
            raise ValueError("Size after crid part not given.")

        crid = UsmPage("CRIUSF_DIR_STREAM")
        crid.update("fmtver", ElementType.INT, self.version)
        crid.update("filename", ElementType.STRING, self.filename)
        crid.update("filesize", ElementType.INT, 0x800 + size_after_crid_part)
        crid.update("datasize", ElementType.INT, 0)
        crid.update("stmid", ElementType.INT, 0)
        crid.update("chno", ElementType.SHORT, -1)
        crid.update("minchk", ElementType.SHORT, 1)

        # TODO: Find formula for minbuf
        minbuf = round(self._max_packet_size * 1.98746)
        minbuf += 0x10 - (minbuf % 0x10) if minbuf % 0x10 != 0 else 0
        crid.update("minbuf", ElementType.INT, minbuf)

        bitrate = 0
        for video in self.videos:
            bitrate += int(video.crid_page["avbps"].val)

        for audio in self.audios:
            bitrate += int(audio.crid_page["avbps"].val)

        crid.update("avbps", ElementType.INT, bitrate)

        return crid

    @classmethod
    def open(
        cls,
        filepath: Union[str, pathlib.Path],
        key: Optional[int] = None,
        encoding: str = "UTF-8",
    ) -> Usm:
        filesize = os.path.getsize(filepath)
        if filesize <= 0x20:
            raise ValueError(f"File {filepath} too small.")

        usmfile = open(filepath, "rb")
        filename = os.path.basename(filepath)
        logging.info(
            "Loading Usm from file. File: %s, File size: %d, Encoding: %s",
            filename,
            filesize,
            encoding,
        )

        signature = usmfile.read(4)

        if not is_usm(signature):
            raise ValueError(f"Invalid file signature: {bytes_to_hex(signature)}")

        crids, video_channels, audio_channels = _process_chunks(
            usmfile, filesize, encoding
        )

        # We don't need a mutex because of the GIL but it feels dirty without one
        usmmutex = threading.Lock()
        videos = []
        audios = []
        version: Optional[int] = None
        for channel_number, video_channel in video_channels.items():
            crid = [
                page
                for page in crids
                if page.get("chno").val == channel_number
                and page.get("stmid").val == 0x40534656  # @SFV
            ]

            if len(crid) == 0:
                raise ValueError(f"No crid page found for videos ch {channel_number}.")
            if channel_number == 0:
                version = crid[0].get("fmtver").val

            videos.append(
                GenericVideo(
                    video_sink(
                        usmfile,
                        usmmutex,
                        video_channel.stream,
                        keyframes_from_seek_pages(video_channel.metadata),
                    ),
                    crid[0],
                    video_channel.header,
                    channel_number,
                )
            )

        for channel_number, audio_channel in audio_channels.items():
            crid = [
                page
                for page in crids
                if page.get("chno").val == channel_number
                and page.get("stmid").val == 0x40534641  # @SFA
            ]

            if len(crid) == 0:
                raise ValueError(f"No crid page found for audios ch {channel_number}.")

            audios.append(
                GenericAudio(
                    audio_sink(usmfile, usmmutex, audio_channel.stream),
                    crid[0],
                    audio_channel.header,
                    channel_number,
                )
            )

        usm_crid = [page for page in crids if page.get("chno").val == -1]
        if len(usm_crid) == 0:
            raise ValueError("No usm crid page found.")
        if version is None:
            raise ValueError("Format version not found.")

        return cls(
            version=version, video=videos, audio=audios, key=key, usm_crid=usm_crid[0]
        )

    def demux(
        self,
        path: str,
        save_video: bool = True,
        save_audio: bool = True,
        save_pages: bool = False,
        folder_name: Optional[str] = None,
    ) -> Tuple[List[str], List[str]]:
        """Saves all videos, audios, pages (depending on configuration) of a Usm."""
        if folder_name is None:
            folder_name = self.filename

        folder_name = slugify(folder_name, allow_unicode=True)
        output = os.path.join(path, folder_name)
        if os.path.exists(output) and os.path.isfile(output):
            raise FileExistsError

        os.makedirs(output)

        videos = []
        audios = []

        if save_video:
            logging.info("Saving videos")
            mode = OpMode.NONE if self.video_key is None else OpMode.DECRYPT
            vid_output = os.path.join(output, "videos")
            if not os.path.exists(vid_output):
                os.mkdir(vid_output)

            for vid in self.videos:
                filename = os.path.join(vid_output, vid.filename)
                with open(filename, "wb+") as f:
                    for packet, _ in vid.stream(mode, self.video_key):
                        f.write(packet)

                videos.append(filename)

        if save_audio:
            logging.info("Saving audios")
            mode = OpMode.NONE if self.audio_key is None else OpMode.DECRYPT
            aud_output = os.path.join(output, "audios")
            if not os.path.exists(aud_output):
                os.mkdir(aud_output)

            for aud in self.audios:
                filename = os.path.join(aud_output, aud.filename)
                with open(filename, "wb+") as f:
                    for packet in aud.stream(mode, self.audio_key):
                        f.write(packet)

                audios.append(filename)

        if save_pages:
            logging.info("Saving pages")
            raise NotImplementedError

        return videos, audios

    def _generate_prestream_chunks(
        self,
        stream_filesize: int,
        keyframe_index_and_offsets: dict,
        encoding: str,
    ) -> Generator[UsmChunk, None, None]:
        header_metadata_chunks = []
        header_metadata_size = 0
        for chunk, position in _generate_header_metadata_chunks(
            self.videos, self.audios, keyframe_index_and_offsets, encoding
        ):
            header_metadata_chunks.append(chunk)
            header_metadata_size = position

        usm_crid_page = self.usm_crid_page(
            0x800 + header_metadata_size + stream_filesize
        )
        pages = [usm_crid_page]
        for video in self.videos:
            pages.append(video.crid_page)

        for audio in self.audios:
            pages.append(audio.crid_page)

        yield UsmChunk(
            chunk_type=ChunkType.INFO,
            payload_type=PayloadType.HEADER,
            payload=pages,
            padding=pad_to_next_sector(position=0),
            encoding=encoding,
        )

        for chunk in header_metadata_chunks:
            yield chunk

    def chunks(
        self, mode: OpMode = OpMode.NONE, encoding: str = "UTF-8"
    ) -> Generator[UsmChunk, None, None]:
        (
            stream_file,
            filesize,
            max_packet_size,
            keyframe_index_and_offsets,
        ) = _pack_stream(
            self.max_frame,
            self.videos,
            self.audios,
            mode,
            self.video_key,
            self.audio_key,
        )
        self._max_packet_size = max_packet_size

        for chunk in self._generate_prestream_chunks(
            stream_filesize=filesize,
            keyframe_index_and_offsets=keyframe_index_and_offsets,
            encoding=encoding,
        ):
            yield chunk

        while filesize > stream_file.tell():
            # Peek to read chunk's true size and _padding.
            temp_buf = stream_file.read(0x20)
            stream_file.seek(-0x20, 1)

            chunk_size, chunk_padding = chunk_size_and_padding(temp_buf)
            yield UsmChunk.from_bytes(stream_file.read(chunk_size), encoding=encoding)
            stream_file.seek(chunk_padding, 1)

    def stream(
        self, mode: OpMode = OpMode.NONE, encoding: str = "UTF-8"
    ) -> Generator[bytes, None, None]:
        (
            stream_file,
            filesize,
            max_packet_size,
            keyframe_index_and_offsets,
        ) = _pack_stream(
            self.max_frame,
            self.videos,
            self.audios,
            mode,
            self.video_key,
            self.audio_key,
        )
        self._max_packet_size = max_packet_size

        for chunk in self._generate_prestream_chunks(
            stream_filesize=filesize,
            keyframe_index_and_offsets=keyframe_index_and_offsets,
            encoding=encoding,
        ):
            yield chunk.pack()

        while filesize > stream_file.tell():
            yield stream_file.read(0x800)


def _process_chunks(
    usmfile: IO,
    filesize: int,
    encoding: str,
) -> Tuple[List[UsmPage], Dict[int, UsmChannel], Dict[int, UsmChannel]]:
    crids: List[UsmPage] = []
    video_ch: Dict[int, UsmChannel] = defaultdict(
        lambda: UsmChannel(stream=[], header=UsmPage(""))
    )
    audio_ch: Dict[int, UsmChannel] = defaultdict(
        lambda: UsmChannel(stream=[], header=UsmPage(""))
    )

    usmfile.seek(0, 0)
    prev_payload_type = PayloadType.HEADER
    while filesize > usmfile.tell():
        # Peek to read chunk's true size and _padding.
        temp_buf = usmfile.read(0x20)
        usmfile.seek(-0x20, 1)

        chunk_size, chunk_padding = chunk_size_and_padding(temp_buf)
        offset = usmfile.tell()

        # Read chunk data and the 0x20 byte chunk header. Then skip _padding.
        data = usmfile.read(chunk_size + 0x20)
        usmfile.seek(chunk_padding, 1)

        chunk = UsmChunk.from_bytes(data, encoding=encoding)
        if chunk.payload_type is not prev_payload_type:
            logging.info("New Usm section at %x hex offset", offset)

        if chunk.chunk_type is ChunkType.INFO:
            if isinstance(chunk.payload, list):
                crids.extend(chunk.payload)
            else:
                logging.warning(
                    "_process_chunk: Received info chunk that's not a list %s",
                    chunk.payload,
                )
        elif chunk.chunk_type is ChunkType.VIDEO:
            if chunk.payload_type == PayloadType.STREAM:
                video_ch[chunk.channel_number].stream.append(
                    (offset + chunk.payload_offset, len(chunk.payload))
                )
            elif chunk.payload_type == PayloadType.SECTION_END:
                if isinstance(chunk.payload, bytes):
                    logging.debug(
                        "_process_chunk: @SFV section end %s",
                        bytes_to_hex(chunk.payload),
                    )
                else:
                    logging.debug(
                        "_process_chunk: @SFV section end %s", str(chunk.payload)
                    )
            elif chunk.payload_type == PayloadType.HEADER:
                video_ch[chunk.channel_number].header = chunk.payload
            elif chunk.payload_type == PayloadType.METADATA:
                video_ch[chunk.channel_number].metadata = chunk.payload

        elif chunk.chunk_type is ChunkType.AUDIO:
            if chunk.payload_type == PayloadType.STREAM:
                audio_ch[chunk.channel_number].stream.append(
                    (offset + chunk.payload_offset, len(chunk.payload))
                )
            elif chunk.payload_type == PayloadType.SECTION_END:
                if isinstance(chunk.payload, bytes):
                    logging.debug(
                        "_process_chunk: @SFA section end %s",
                        bytes_to_hex(chunk.payload),
                    )
                else:
                    logging.debug(
                        "_process_chunk: @SFA section end %s", str(chunk.payload)
                    )
            elif chunk.payload_type == PayloadType.HEADER:
                audio_ch[chunk.channel_number].header = chunk.payload
            elif chunk.payload_type == PayloadType.METADATA:
                audio_ch[chunk.channel_number].metadata = chunk.payload

        prev_payload_type = chunk.payload_type

    return crids, video_ch, audio_ch


def _generate_header_metadata_chunks(
    videos: List[UsmVideo],
    audios: List[UsmAudio],
    keyframe_index_and_offsets: Dict[int, List[Tuple[int, int]]],
    encoding: str,
) -> Generator[Tuple[UsmChunk, int], None, None]:
    current_position = 0
    # ========= YIELD HEADER PAGE CHUNKS ==========

    for video in videos:
        chunk = UsmChunk(
            chunk_type=ChunkType.VIDEO,
            payload_type=PayloadType.HEADER,
            payload=[video.header_page],
            padding=0x18,  # Based from real USMs
            channel_number=video.channel_number,
            encoding=encoding,
        )
        current_position += len(chunk)
        yield chunk, current_position

    for audio in audios:
        chunk = UsmChunk(
            chunk_type=ChunkType.AUDIO,
            payload_type=PayloadType.HEADER,
            payload=[audio.header_page],
            padding=0x8,  # Based from real USMs
            channel_number=audio.channel_number,
            encoding=encoding,
        )
        current_position += len(chunk)
        yield chunk, current_position

    # ========== YIELD HEADER END CHUNKS ==========

    header_end_payload = "#HEADER END     ===============".encode("UTF-8") + bytes(1)
    for video in videos:
        chunk = UsmChunk(
            chunk_type=ChunkType.VIDEO,
            payload_type=PayloadType.SECTION_END,
            payload=header_end_payload,
            padding=0,  # Based from real USMs
            channel_number=video.channel_number,
            encoding=encoding,
        )
        current_position += len(chunk)
        yield chunk, current_position

    for audio in audios:
        chunk = UsmChunk(
            chunk_type=ChunkType.AUDIO,
            payload_type=PayloadType.SECTION_END,
            payload=header_end_payload,
            padding=0,  # Based from real USMs
            channel_number=audio.channel_number,
            encoding=encoding,
        )
        current_position += len(chunk)
        yield chunk, current_position

    # ========== PROCESS METADATA CHUNKS ==========

    def metadata_pad(size: int) -> int:
        # TODO: Find cases where this does not hold for metadata chunks
        if size <= 0xF0:
            return 0xF0 - size
        else:
            return math.ceil(size / 0x8) * 0x8 - size

    metadata_section_size = 0
    metadata_section_chunks_vid = []
    metadata_section_chunks_aud = []
    metadata_section_chunks_sec_end = []

    for video in videos:
        if video.metadata_pages is None:
            index_and_offsets = keyframe_index_and_offsets[video.channel_number]
            metadata_pages: List[UsmPage] = []
            for index, offset in index_and_offsets:
                page = UsmPage("VIDEO_SEEKINFO")
                # ofs_byte is modified later
                page.update("ofs_byte", ElementType.LONGLONG, offset)
                page.update("ofs_frmid", ElementType.UINT, index)
                page.update("num_skip", ElementType.USHORT, 0)
                page.update("resv", ElementType.USHORT, 0)
                metadata_pages.append(page)
        else:
            metadata_pages = video.metadata_pages

        chunk = UsmChunk(
            chunk_type=ChunkType.VIDEO,
            payload_type=PayloadType.METADATA,
            payload=metadata_pages,
            padding=metadata_pad,
            channel_number=video.channel_number,
            encoding=encoding,
        )
        metadata_section_size += len(chunk)
        metadata_section_chunks_vid.append(chunk)

    for audio in audios:
        if audio.metadata_pages is None:
            continue

        chunk = UsmChunk(
            chunk_type=ChunkType.AUDIO,
            payload_type=PayloadType.METADATA,
            payload=audio.metadata_pages,
            padding=metadata_pad,
            channel_number=audio.channel_number,
            encoding=encoding,
        )
        metadata_section_size += len(chunk)
        metadata_section_chunks_aud.append(chunk)

    metadata_end_payload = bytes("#METADATA END   ===============", "UTF-8") + bytes(1)
    for video in videos:
        chunk = UsmChunk(
            chunk_type=ChunkType.VIDEO,
            payload_type=PayloadType.SECTION_END,
            payload=metadata_end_payload,
            padding=0,  # Based from real USMs
            channel_number=video.channel_number,
            encoding=encoding,
        )
        metadata_section_size += len(chunk)
        metadata_section_chunks_sec_end.append(chunk)

    for audio in audios:
        if audio.metadata_pages is None:
            continue

        chunk = UsmChunk(
            chunk_type=ChunkType.AUDIO,
            payload_type=PayloadType.SECTION_END,
            payload=metadata_end_payload,
            padding=0,  # Based from real USMs
            channel_number=audio.channel_number,
            encoding=encoding,
        )
        metadata_section_size += len(chunk)
        metadata_section_chunks_sec_end.append(chunk)

    # ========= YIELD METADATA CHUNKS ==========

    for chunk in metadata_section_chunks_vid:
        payload = chunk.payload
        if isinstance(payload, bytes):
            raise ValueError("Video metadata is not list of pages.")
        else:
            # Add 0x800(crid chunks and _padding) and the size of the entire
            # metadata section to offsets of stream file
            for metadata in payload:
                offset = metadata["ofs_byte"].val
                offset += 0x800 + current_position + metadata_section_size
                metadata.update("ofs_byte", ElementType.LONGLONG, offset)

        yield chunk, current_position + metadata_section_size

    for chunk in metadata_section_chunks_aud:
        yield chunk, current_position + metadata_section_size

    for chunk in metadata_section_chunks_sec_end:
        yield chunk, current_position + metadata_section_size


def _pack_stream(
    max_frames: int,
    videos: List[UsmVideo],
    audios: List[UsmAudio],
    mode: OpMode = OpMode.NONE,
    video_key: Optional[bytes] = None,
    audio_key: Optional[bytes] = None,
) -> Tuple[IO, int, int, Dict[int, List[Tuple[int, int]]]]:
    videos_iter: List[Callable[[], Tuple[List[UsmChunk], bool]]] = [
        vid.chunks(mode=mode, key=video_key).__next__ for vid in videos
    ]
    audios_iter: List[Callable[[], List[UsmChunk]]] = [
        aud.chunks(mode=mode, key=audio_key).__next__ for aud in audios
    ]

    stream_file = TemporaryFile("wb+")
    keyframe_index_and_offsets: Dict[int, List[Tuple[int, int]]] = defaultdict(
        lambda: list()
    )
    max_packet_size = 1
    for index in range(max_frames):
        finished_video_iters = []
        finished_audio_iters = []

        # Process videos generators
        for i, vid_tuple in enumerate(videos_iter):
            try:
                chunks, is_keyframe = vid_tuple()
                if is_keyframe:
                    keyframe_index_and_offsets[chunks[0].channel_number].append(
                        (index, stream_file.tell())
                    )

                for chunk in chunks:
                    max_packet_size = max(len(chunk), max_packet_size)
                    stream_file.write(chunk.pack())
            except StopIteration:
                finished_video_iters.append(i)
                continue

        # Process audios generators
        for i, aud_chunk in enumerate(audios_iter):
            try:
                chunks = aud_chunk()
                for chunk in chunks:
                    max_packet_size = max(len(chunk), max_packet_size)
                    stream_file.write(chunk.pack())
            except StopIteration:
                finished_audio_iters.append(i)
                continue

        # Remove finished audios generators
        videos_iter = [
            vid for i, vid in enumerate(videos_iter) if i not in finished_video_iters
        ]
        audios_iter = [
            aud for i, aud in enumerate(audios_iter) if i not in finished_audio_iters
        ]

    stream_file.flush()
    filesize = stream_file.tell()
    stream_file.seek(0, 0)
    return stream_file, filesize, max_packet_size, keyframe_index_and_offsets
