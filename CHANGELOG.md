# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2022-07-11
### Added
- Support for H.264 USM creation. Courtesy of [keikei14][https://github.com/keikei14]
- Command `createusm` also now takes m4v h264 files as input.

## [0.2.5] - 2022-04-08
### Added
- New operation in command-line called `encryptusm` which encrypts an existing USM file.
- Support for new USM Chunk `@ALP` which is used for alpha transparency videos. Currently, supports probe and extraction operations only. Thank you to [EmirioBomb](https://github.com/EmirioBomb) for bringing this to my attention and providing sample files.

### Changed
- Renamed Usm constructor parameters.

### Removed
- Check for chunk header in `chunk_size_and_padding` function

## [0.2.4] - 2022-03-28
### Changed
- pack\_pages function now return an empty byte when given an empty list instead of throwing an exception.

### Fixed
- Fixed GenericVideo initialization in Usm open method.

## [0.2.3] - 2022-03-28
### Changed
- Improved USM probe handling of unknown chunks

## [0.2.2] - 2021-09-09
### Fixed
- Fixed bug in command-line extractusm mode where it fails to find usms when given a directory.

## [0.2.1] - 2021-09-01
### Added
- This changelog

### Fixed
- Fixed bug in non-encrypted USM creation by [@emoose](https://github.com/emoose).

## [0.2.0] - 2021-08-11
### Added
- \_\_main\_\_.py.
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

[Unreleased]: https://github.com/donmai-me/WannaCRI/compare/0.2.5...HEAD
[0.2.5]: https://github.com/donmai-me/WannaCRI/compare/0.2.4...0.2.5
[0.2.4]: https://github.com/donmai-me/WannaCRI/compare/0.2.3...0.2.4
[0.2.3]: https://github.com/donmai-me/WannaCRI/compare/0.2.2...0.2.3
[0.2.2]: https://github.com/donmai-me/WannaCRI/compare/0.2.1...0.2.2
[0.2.1]: https://github.com/donmai-me/WannaCRI/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/donmai-me/WannaCRI/compare/0.1.0...0.2.0
