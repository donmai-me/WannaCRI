# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2021-09-01
### Added
- This changelog

### Fixed
- Fixed bug in non-encrypted USM creation by [@emoose](https://github.com/emoose).

## [0.2.0] - 2021-08-11
### Added
- __main__.py.
- is_payload_list_pages function that checks whether payload is a list of pages by its first four bytes.

### Changed
- Renamed ArrayType to ElementType.
- UsmChunk from_bytes method now determines payload type by the first four bytes of a payload. 
- Changed logging format to JSON.
- is_valid_chunk function no longer recasts byte input to bytearray.
- Command-line now prints installed version.

### Fixed
- Fixed bug in extractusm that causes it to fail when output directory doesn't exist.
- Fixed bug where program fails when directory exists.

[0.2.1]: https://github.com/donmai-me/WannaCRI/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/donmai-me/WannaCRI/compare/0.1.0...0.2.0
