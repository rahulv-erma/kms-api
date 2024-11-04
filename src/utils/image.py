from PIL import Image, ImageOps, ExifTags

from src import log

allowed_sizes = [16, 24, 60, 300, 600, 1024]


def is_valid_image(file_path):
    try:
        with Image.open(file_path) as img:
            return img.format is not None
    except Exception:
        return False


def resize_image(image_path, size):
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)
    orientation = 0
    for tag, value in image.getexif().items():
        if ExifTags.TAGS.get(tag) == 'Orientation':
            orientation = value
            break

    if orientation == 3:
        image = image.rotate(180, expand=True)
    elif orientation == 6:
        image = image.rotate(270, expand=True)
    elif orientation == 8:
        image = image.rotate(90, expand=True)

    if size not in allowed_sizes:
        return f"{size} is not a valid size"

    try:
        image.thumbnail((size, size), Image.LANCZOS)

    except Exception as e:
        log.exception("An exception occured while resizing image")
        raise e

    return image
