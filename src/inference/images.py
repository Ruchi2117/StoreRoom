"""Decode JPEG/PNG content; filenames and MIME types are not trusted."""
from io import BytesIO
from pathlib import Path
import warnings
import sys
import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 25_000_000


class ImageInputError(ValueError):
    def __init__(self, message, status_code=422):
        super().__init__(message)
        self.status_code = status_code


def decode_image(source):
    """Return an owned uint8 BGR array, matching the existing OpenCV loader."""
    if isinstance(source, np.ndarray):
        if source.dtype != np.uint8 or source.ndim != 3 or source.shape[2] != 3 or not source.size:
            raise ImageInputError('Expected a non-empty uint8 BGR image')
        if source.shape[0] * source.shape[1] > MAX_PIXELS:
            raise ImageInputError('Image exceeds the 25 megapixel limit', 413)
        return np.ascontiguousarray(source.copy())
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise ImageInputError('Image file does not exist', 400)
        if path.stat().st_size > MAX_BYTES:
            raise ImageInputError('Image exceeds the 20 MiB limit', 413)
        with path.open('rb') as f:
            source = f.read(MAX_BYTES + 1)
    if not isinstance(source, bytes):
        raise ImageInputError('Expected image bytes, a local path, or a BGR array')
    if not source:
        raise ImageInputError('Image is empty', 400)
    if len(source) > MAX_BYTES:
        raise ImageInputError('Image exceeds the 20 MiB limit', 413)
    # Ultralytics patches Image.open with an optional HEIF auto-install fallback.
    # Use Pillow's original decoder: this endpoint deliberately supports JPEG/PNG only.
    patches = sys.modules.get('ultralytics.utils.patches')
    open_image = getattr(patches, '_image_open', Image.open)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with open_image(BytesIO(source)) as img:
                if img.format not in {'JPEG', 'PNG'}:
                    raise ImageInputError('Only JPEG and PNG images are supported', 415)
                if img.width * img.height > MAX_PIXELS:
                    raise ImageInputError('Image exceeds the 25 megapixel limit', 413)
                img.verify()
            with open_image(BytesIO(source)) as img:
                img.load()  # also reject truncated JPEG pixel data
    except ImageInputError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise ImageInputError('Image dimensions are too large', 413) from e
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        raise ImageInputError('Image cannot be decoded', 422) from e
    decoded = cv2.imdecode(np.frombuffer(source, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise ImageInputError('Image cannot be decoded', 422)
    return decoded
