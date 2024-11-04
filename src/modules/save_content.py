import uuid
import aiofiles
from fastapi import UploadFile
from typing import List, Tuple

from src import log

TYPES = {
    'application/pdf': "pdf",
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': "xlsx",
    'application/vnd.ms-excel': "xls",
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': "docx",
    'application/msword': "doc",
    'application/vnd.ms-powerpoint': "ppt",
    'image/png': "png",
    'image/jpeg': "jpeg",
    'image/jpg': "jpg",
    'text/csv': "csv",
}


async def save_content(types: str = None, file: UploadFile = None, content_types: List[str] = None) -> Tuple[bool, str]:
    """Function to save any sort of content to folder

    Args:
        types (str, optional): Whether its a pdf, image, etc.. Defaults to None.
        file_str (str, optional): Nulled out now i believe. Defaults to None.
        content_types (List[str], optional): File type, PNG/JPEG, etc. Defaults to None.

    Returns:
        Tuple[bool, str]: True with message if image saved, false with message  if not
    """

    fileId = str(uuid.uuid4())

    if not types:
        return (False, "Type needs to be provided")

    try:
        format = file.content_type
        if format not in content_types:
            log.error(f" FAILED Content type: {format}")
            return {
                "success": False,
                "reason": "Non supported file type."
            }

        format = TYPES[format] if TYPES.get(format) else format

        filePath = f"./src/content/{types}/{fileId}.{format}"
        async with aiofiles.open(filePath, 'wb') as f:
            await f.write(await file.read())

        return {
            "success": True,
            "file_name": file.filename,
            "file_id": f"{fileId}.{format}"
        }

    except Exception:
        log.exception("Failed to save file")

    return {
        "success": False,
        "reason": "Failed to save file"
    }
