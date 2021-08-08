import struct
import logging
from typing import List, Any, Tuple, Dict, NamedTuple, Set, Optional

from .tools import bytes_to_hex
from .types import ArrayType, ElementType


class Element(NamedTuple):
    val: Any
    type: ElementType


class UsmPage:
    def __init__(
        self, name: str, dictionary: Optional[Dict[str, Element]] = None
    ) -> None:
        self.name = name

        if dictionary is not None:
            self._dict: Dict[str, Element] = dictionary
        else:
            self._dict = {}

    @property
    def dict(self) -> Dict[str, Element]:
        return self._dict

    def update(self, name: str, element_type: ElementType, element: Any) -> None:
        # Replace ugly Windows path style with Unix style
        if name == "filename":
            element = element.replace("\\", "/")

        self._dict.update({name: Element(element, element_type)})

    def __getitem__(self, item) -> Element:
        return self._dict[item]

    def get(self, name: str) -> Optional[Element]:
        if name in self._dict.keys():
            return self._dict[name]

        return None


def get_pages(info: bytearray, encoding: str = "UTF-8") -> List[UsmPage]:
    # START OF 8 BYTE PAYLOAD HEADER
    if bytearray(info[0:4]) != bytearray("@UTF", "UTF-8"):
        raise ValueError(f"Invalid info data signature: {info[0:4]}")

    # payload_size doesn't include the 8 byte header
    payload_size = int.from_bytes(info[4:8], "big")
    # END OF 8 BYTE PAYLOAD HEADER

    unique_array_offset = int.from_bytes(info[8:12], "big")
    strings_offset = int.from_bytes(info[12:16], "big")
    byte_array_offset = int.from_bytes(info[16:20], "big")
    page_name_offset = int.from_bytes(info[20:24], "big")

    num_elements_per_page = int.from_bytes(info[24:26], "big")
    unique_array_size_per_page = int.from_bytes(info[26:28], "big")
    num_pages = int.from_bytes(info[28:32], "big")

    # Offsets are always **after** the 8 byte header
    string_array = info[(8 + strings_offset) : (8 + byte_array_offset)]
    byte_array = info[8 + byte_array_offset : 8 + payload_size]

    # Strings are null-byte terminated
    page_name_end = page_name_offset + string_array[page_name_offset:].index(0x00)
    page_name = string_array[page_name_offset:page_name_end].decode("UTF-8")

    logging.debug(
        "get_pages: Identifier: %s, payload size: %s, unique array offset: %x, "
        + "string array offset: %x, bytearray offset: %x, name offset %x, "
        + "element count per page: %x, unique array size per page: %x, page count: %x",
        bytes_to_hex(info[0:4]),
        payload_size,
        unique_array_offset,
        strings_offset,
        byte_array_offset,
        page_name_offset,
        num_elements_per_page,
        unique_array_size_per_page,
        num_pages,
    )

    pages = [UsmPage(page_name) for _ in range(num_pages)]

    unique_array = info[
        8
        + unique_array_offset : 8
        + unique_array_offset
        + unique_array_size_per_page * num_pages
    ]
    for page in pages:
        shared_array = info[0x20 : 8 + unique_array_offset]
        for _ in range(num_elements_per_page):
            element_type = shared_array[0] & 0x1F
            element_occurrence = shared_array[0] >> 5

            element_name_offset = int.from_bytes(shared_array[1:5], "big")
            element_end = element_name_offset + string_array[
                element_name_offset:
            ].index(0x00)
            element_name = string_array[element_name_offset:element_end].decode(
                encoding
            )

            shared_array = shared_array[5:]
            try:
                element_type = ElementType.from_int(element_type)

                if element_occurrence == ArrayType.SHARED.value:
                    current_array = shared_array
                elif element_occurrence == ArrayType.UNIQUE.value:
                    current_array = unique_array
                else:
                    raise ValueError(f"Unknown case: {element_occurrence}")

            except ValueError:
                logging.error(
                    "get_pages: Unknown element. Name: %s, type: %s, occurrence: %x, "
                    + "shared array next four bytes: %s, unique array next four bytes: %s",
                    element_name,
                    element_type,
                    element_occurrence,
                    bytes_to_hex(shared_array[:4]),
                    bytes_to_hex(unique_array[:4]),
                )
                raise

            if element_type == ElementType.CHAR:
                page.update(element_name, ElementType.CHAR, current_array[0])
                element_size = 1
            elif element_type == ElementType.UCHAR:
                page.update(element_name, ElementType.UCHAR, current_array[0])
                element_size = 1
            elif element_type == ElementType.SHORT:
                page.update(
                    element_name,
                    ElementType.SHORT,
                    int.from_bytes(current_array[0:2], "big", signed=True),
                )
                element_size = 2
            elif element_type == ElementType.USHORT:
                page.update(
                    element_name,
                    ElementType.USHORT,
                    int.from_bytes(current_array[0:2], "big"),
                )
                element_size = 2
            elif element_type == ElementType.INT:
                page.update(
                    element_name,
                    ElementType.INT,
                    int.from_bytes(current_array[0:4], "big", signed=True),
                )
                element_size = 4
            elif element_type == ElementType.UINT:
                page.update(
                    element_name,
                    ElementType.UINT,
                    int.from_bytes(current_array[0:4], "big"),
                )
                element_size = 4
            elif element_type == ElementType.LONGLONG:
                page.update(
                    element_name,
                    ElementType.LONGLONG,
                    int.from_bytes(current_array[0:8], "big", signed=True),
                )
                element_size = 8
            elif element_type == ElementType.ULONGLONG:
                page.update(
                    element_name,
                    ElementType.ULONGLONG,
                    int.from_bytes(current_array[0:8], "big"),
                )
                element_size = 8
            elif element_type == ElementType.FLOAT:
                page.update(
                    element_name,
                    ElementType.FLOAT,
                    # < means little-endian
                    struct.unpack("<f", current_array[0:4]),
                )
                element_size = 4
            elif element_type == ElementType.STRING:
                string_offset = int.from_bytes(current_array[0:4], "big")
                string_end = string_offset + string_array[string_offset:].index(0x00)
                string = string_array[string_offset:string_end].decode(encoding)
                page.update(element_name, ElementType.STRING, string)
                element_size = 4
            elif element_type == ElementType.BYTES:
                data_offset = int.from_bytes(current_array[0:4], "big")
                data_end = int.from_bytes(current_array[4:8], "big")
                page.update(
                    element_name,
                    ElementType.BYTES,
                    byte_array[data_offset:data_end],
                )
                element_size = 8
            else:
                # Should be caught at element_type's initialization
                raise ValueError(f"Unknown element type: {element_type}")

            if element_occurrence == ArrayType.SHARED.value:
                shared_array = shared_array[element_size:]
            else:
                unique_array = unique_array[element_size:]

    return pages


def pack_pages(
    pages: List[UsmPage],
    encoding: str,
    string_padding: int = 0,
) -> bytes:
    if len(pages) == 0:
        raise ValueError("No pages given.")

    page_name = pages[0].name
    keys = set()
    num_keys = len(pages[0].dict.keys())

    # Check if pages have the same name and the same keys.
    for page in pages:
        if page_name != page.name:
            raise ValueError("Pages don't have the same names.")
        if num_keys != len(page.dict.keys()):
            raise ValueError("Pages don't have the same keys.")

        for key in page.dict.keys():
            keys.add(key)

    if len(keys) != num_keys:
        raise ValueError("Pages don't have the same keys.")

    # Initialize string array with "<NULL>" and terminate string with null-byte (C-string)
    # TODO: What does "<NULL>" suppose to mean?
    string_array = bytearray()
    string_array += bytes("<NULL>", "UTF-8") + bytes(1)

    page_name_offset = len(string_array)
    string_array += bytes(page_name, "UTF-8") + bytes(1)

    # Dict with all the values
    # Key is page key
    # Tuple is the element name offset and the set is a set of all pages' values
    elements: Dict[str, Tuple[int, Set[Element]]] = {}

    for key in keys:
        element_name_offset = len(string_array)
        string_array += bytes(key, "UTF-8") + bytes(1)

        values = set()
        for page in pages:
            values.add(page[key])

        elements.update({key: (element_name_offset, values)})

    common_elements = [
        name
        for name, (_, values) in elements.items()
        if len(values) == 1 and len(pages) > 1
    ]

    # Generate s and d array
    shared_array = bytearray()
    unique_array = bytearray()
    byte_array = bytearray()
    for i, page in enumerate(pages):
        for element_name, element in page.dict.items():
            element_type_packed = int(element.type.value)
            if element_name in common_elements:
                # We only need to encode data once since it's recurring for the same key
                if i != 0:
                    continue

                element_type_packed += int(ArrayType.SHARED.value) << 5
                shared_array += element_type_packed.to_bytes(1, "big")

                element_name_offset = elements[element_name][0]
                shared_array += element_name_offset.to_bytes(4, "big")

                current_array = shared_array
            else:
                # We only need to encode data **about** non-recurring values once
                # But we encode actual data every time since they're not recurring
                if i == 0:
                    element_type_packed += int(ArrayType.UNIQUE.value) << 5
                    shared_array += element_type_packed.to_bytes(1, "big")

                    element_name_offset = elements[element_name][0]
                    shared_array += element_name_offset.to_bytes(4, "big")

                current_array = unique_array

            if element.type == ElementType.CHAR:
                current_array += element.val.to_bytes(1, "big", signed=True)
            elif element.type == ElementType.UCHAR:
                current_array += element.val.to_bytes(1, "big")
            elif element.type == ElementType.SHORT:
                current_array += element.val.to_bytes(2, "big", signed=True)
            elif element.type == ElementType.USHORT:
                current_array += element.val.to_bytes(2, "big")
            elif element.type == ElementType.INT:
                current_array += element.val.to_bytes(4, "big", signed=True)
            elif element.type == ElementType.UINT:
                current_array += element.val.to_bytes(4, "big")
            elif element.type == ElementType.LONGLONG:
                current_array += element.val.to_bytes(8, "big", signed=True)
            elif element.type == ElementType.ULONGLONG:
                current_array += element.val.to_bytes(8, "big")
            elif element.type == ElementType.FLOAT:
                # < means little-endian
                current_array += struct.pack("<f", element.val)
            elif element.type == ElementType.STRING:
                value_offset = len(string_array)
                string_array += bytes(element.val, encoding) + bytes(1)
                current_array += value_offset.to_bytes(4, "big")
            elif element.type == ElementType.BYTES:
                bytes_offset = len(byte_array)
                bytes_end = bytes_offset + len(element.val)
                current_array += bytes_offset.to_bytes(4, "big")
                current_array += bytes_end.to_bytes(4, "big")
                byte_array += element.val
            else:
                raise ValueError(f"Unknown element type {element.type}.")

    string_array += bytes(string_padding)

    # Combine everything together
    result = bytearray("@UTF", "UTF-8")

    # 24 bytes for offset and page number info
    data_size = (
        24 + len(shared_array) + len(unique_array) + len(string_array) + len(byte_array)
    )
    result += data_size.to_bytes(4, "big")

    unique_array_offset = 24 + len(shared_array)
    result += unique_array_offset.to_bytes(4, "big")
    strings_offset = 24 + len(shared_array) + len(unique_array)
    result += strings_offset.to_bytes(4, "big")
    byte_array_offset = 24 + len(shared_array) + len(unique_array) + len(string_array)
    result += byte_array_offset.to_bytes(4, "big")

    result += page_name_offset.to_bytes(4, "big")
    result += len(keys).to_bytes(2, "big")

    unique_array_size_per_page = len(unique_array) // len(pages)
    result += unique_array_size_per_page.to_bytes(2, "big")

    result += len(pages).to_bytes(4, "big")

    result += shared_array
    result += unique_array
    result += string_array
    result += byte_array
    return bytes(result)


def keyframes_from_seek_pages(seek_pages: Optional[List[UsmPage]]) -> List[int]:
    result = []
    if seek_pages is None:
        return result

    for seek in seek_pages:
        if seek.name != "VIDEO_SEEKINFO":
            raise ValueError("Page name is not 'VIDEO_SEEKINFO'")

        result.append(seek["ofs_frmid"].val)

    return result
