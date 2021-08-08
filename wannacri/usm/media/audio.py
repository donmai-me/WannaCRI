from typing import Generator, Optional, List

from .protocols import UsmAudio
from ..page import UsmPage


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
