import logging
import os
import argparse
import platform
import shutil
import string
import tempfile
import random
from typing import List, Optional

import ffmpeg

import wannacri
from .codec import Sofdec2Codec
from .usm import is_usm, Usm, Vp9, OpMode


def extract_usm():
    """One of the main functions in the command-line program. Extracts a USM or extracts
    multiple USMs given a path as input."""
    parser = argparse.ArgumentParser("WannaCRI Extract USM", allow_abbrev=False)
    parser.add_argument(
        "operation",
        metavar="operation",
        type=str,
        choices=OP_LIST,
        help="Specify operation.",
    )
    parser.add_argument(
        "input",
        metavar="input file/folder",
        type=existing_path,
        help="Path to USM file or path.",
    )
    parser.add_argument(
        "-k", "--key", type=key, default=None, help="Decryption key for encrypted USMs."
    )
    parser.add_argument(
        "-e",
        "--encoding",
        type=str,
        default="shift-jis",
        help="Character encoding used in USM. Defaults to shift-jis.",
    )
    parser.add_argument(
        "-p",
        "--pages",
        action="store_const",
        default=False,
        const=True,
        help="Toggle to save USM pages when extracting.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=dir_path,
        default="./output",
        help="Output path. Defaults to a folder named output in CWD.",
    )
    args = parser.parse_args()

    usmfiles = find_usm(args.input)

    for i, usmfile in enumerate(usmfiles):
        filename = os.path.basename(usmfile)
        print(f"Processing {i+1} of {len(usmfiles)}... ", end="", flush=True)
        try:
            usm = Usm.open(usmfile, encoding=args.encoding, key=args.key)

            usm.demux(
                path=args.output,
                save_video=True,
                save_audio=True,
                save_pages=args.pages,
                folder_name=filename,
            )
        except ValueError:
            print("ERROR")
            print(f"Please run probe on {usmfile}")
        else:
            print("DONE")


def probe_usm():
    """One of the main functions in the command-line program. Probes a USM or finds
    multiple USMs and probes them when given a path as input."""
    parser = argparse.ArgumentParser("WannaCRI Probe USM", allow_abbrev=False)
    parser.add_argument(
        "operation",
        metavar="operation",
        type=str,
        choices=OP_LIST,
        help="Specify operation.",
    )
    parser.add_argument(
        "input",
        metavar="input file/folder",
        type=existing_path,
        help="Path to USM file or path.",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        type=str,
        default="shift-jis",
        help="Character encoding used in USM. Defaults to shift-jis.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=dir_path,
        default="./usmlogs",
        help="Output path. Defaults to a folder named usmlogs in CWD.",
    )
    parser.add_argument(
        "--ffprobe",
        type=str,
        default=".",
        help="Path to ffprobe executable or directory. Defaults to CWD.",
    )
    args = parser.parse_args()

    usmfiles = find_usm(args.input)

    os.makedirs(args.output)
    temp_dir = tempfile.mkdtemp()
    ffprobe_path = find_ffprobe(args.ffprobe)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    format_str = "%(levelname)-8s %(message)s"
    for i, usmfile in enumerate(usmfiles):
        print(f"Processing {i + 1} of {len(usmfiles)}")
        filename = os.path.basename(usmfile)
        random_str = "".join(random.choices(string.ascii_letters + string.digits, k=3))

        # Initialize logger
        logname = os.path.join(args.output, f"{filename}_{random_str}.log")
        newfilehandler = logging.FileHandler(logname, "w", encoding="UTF-8")
        newformatter = logging.Formatter(format_str)
        newfilehandler.setFormatter(newformatter)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        logger.addHandler(newfilehandler)

        # Start logging
        logging.info("Path: %s", usmfile.replace(args.input, ""))
        logging.info("Version: %s", wannacri.__version__)
        logging.info("OS: %s %s", platform.system(), platform.release())
        logging.info("Using local ffprobe: %s", "No" if ffprobe_path is None else "Yes")

        try:
            usm = Usm.open(usmfile, encoding=args.encoding)
        except ValueError:
            logging.exception("main: Error occured in parsing usm file")
            continue

        logging.info("Extracting files")
        try:
            videos, audios = usm.demux(
                path=temp_dir, save_video=True, save_audio=True, save_pages=False
            )
        except ValueError:
            logging.exception("main: Error occured in demuxing usm file")
            continue

        logging.info("Probing videos")
        try:
            for video in videos:
                info = ffmpeg.probe(
                    video,
                    show_entries="packet=dts,pts_time,pos,flags",
                    cmd="ffprobe" if ffprobe_path is None else ffprobe_path,
                )
                logging.info("Video %s info", video)
                logging.info("format: %s", info.get("format"))
                logging.info("streams: %s", info.get("streams"))
                logging.info("packets: %s", info.get("packets"))
        except (ValueError, RuntimeError):
            logging.exception("main: Error occurred in ffmpeg probe in videos")
            continue
        except ffmpeg.Error as e:
            logging.exception(
                "main: FFmpeg error occurred in ffmpeg probe in videos. stderr: %s",
                e.stderr,
            )
            continue

        logging.info("Probing audios")
        try:
            for audio in audios:
                info = ffmpeg.probe(
                    audio,
                    show_entries="packet=dts,pts_time,pos,flags",
                    cmd="ffprobe" if ffprobe_path is None else ffprobe_path,
                )
                logging.info("Audio %s info", audio)
                logging.info("format: %s", info.get("format"))
                logging.info("streams: %s", info.get("streams"))
                logging.info("packets: %s", info.get("packets"))
        except (ValueError, RuntimeError):
            logging.exception("main: Error occurred in ffmpeg probe in audios")
            continue
        except ffmpeg.Error as e:
            logging.exception(
                "main: FFmpeg error occurred in ffmpeg probe in audios. stderr: %s",
                e.stderr,
            )
            continue

        logging.info("Done probing usm file")
        for filename in os.listdir(temp_dir):
            shutil.rmtree(os.path.join(temp_dir + filename))

    shutil.rmtree(temp_dir)
    print(f'Probe complete. All logs are stored in "{args.output}" folder')


def create_usm():
    parser = argparse.ArgumentParser("WannaCRI Create USM", allow_abbrev=False)
    parser.add_argument(
        "operation",
        metavar="operation",
        type=str,
        choices=OP_LIST,
        help="Specify operation.",
    )
    parser.add_argument(
        "input",
        metavar="input file path",
        type=existing_file,
        help="Path to video file.",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        type=str,
        default="shift-jis",
        help="Character encoding used in creating USM. Defaults to shift-jis.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=dir_path,
        default=None,
        help="Output path. Defaults to the same place as input.",
    )
    parser.add_argument(
        "--ffprobe",
        type=str,
        default=".",
        help="Path to ffprobe executable or directory. Defaults to CWD.",
    )
    parser.add_argument(
        "-k", "--key", type=key, default=None, help="Encryption key for encrypted USMs."
    )
    args = parser.parse_args()

    ffprobe_path = find_ffprobe(args.ffprobe)

    # TODO: Add support for more video codecs and audio codecs
    codec = Sofdec2Codec.from_file(args.input)
    if codec is not Sofdec2Codec.VP9:
        raise NotImplementedError("Non-Vp9 files are not yet implemented.")

    video = Vp9(args.input, ffprobe_path=ffprobe_path)
    filename = os.path.splitext(args.input)[0]

    usm = Usm(video=[video], key=args.key)
    with open(filename + ".usm", "wb") as f:
        mode = None if args.key is None else OpMode.ENCRYPT

        for packet in usm.stream(mode, encoding=args.encoding):
            f.write(packet)

    print("Done creating USM file.")


OP_DICT = {"extractusm": extract_usm, "createusm": create_usm, "probeusm": probe_usm}
OP_LIST = list(OP_DICT.keys())


def main():
    parser = argparse.ArgumentParser("WannaCRI command line", allow_abbrev=False)
    parser.add_argument(
        "operation",
        metavar="operation",
        type=str,
        choices=OP_LIST,
        help="Specify operation",
    )
    args, _ = parser.parse_known_args()

    OP_DICT[args.operation]()


def find_usm(path: str) -> List[str]:
    """Walks a path to find USMs."""
    if os.path.isfile(path):
        with open(path, "rb") as test:
            if not is_usm(test.read(4)):
                raise ValueError("Not a usm file.")

        return [path]

    print("Finding USM files... ", end="", flush=True)
    usmfiles = []
    for path, _, files in os.walk(path):
        for f in files:
            path = os.path.join(path, f)
            with open(path, "rb") as test:
                if is_usm(test.read(4)):
                    usmfiles.append(path)

    print(f"Found {len(usmfiles)}")
    return usmfiles


def find_ffprobe(path: str) -> Optional[str]:
    """Find ffprobe.exe in given path."""
    if os.name != "nt":
        # Assume that ffmpeg is installed in Unix systems
        return

    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        cwdfiles = os.listdir(path)
        for cwdfile in cwdfiles:
            filename = os.path.basename(cwdfile)
            if filename == "ffprobe.exe":
                return os.path.abspath(os.path.join(path, "ffprobe.exe"))


def key(key_str) -> int:
    try:
        return int(key_str, 0)
    except ValueError:
        # Try again but this time we prepend a 0x and parse it as a hex
        key_str = "0x" + key_str

    return int(key_str, 16)


def existing_path(path) -> str:
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        return path.rstrip("/\\")

    raise FileNotFoundError(path)


def existing_file(path) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if os.path.isdir(path):
        raise IsADirectoryError(path)

    return path


def dir_path(path) -> str:
    if os.path.isdir(path):
        return path.rstrip("/\\")

    raise NotADirectoryError(path)
