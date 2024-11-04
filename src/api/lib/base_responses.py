from fastapi.responses import JSONResponse, FileResponse
from typing import Union


def is_valid_status(lower: int, higher: int, status_code: int):
    """Returns bool whether status code is valid

    Args:
        lower int: Lower limit of status code.
        higher int: Higher limit of status code.
        status_code int: Status code being checked.

    Returns:
        bool: Value between range is valid or not
    """
    return lower <= status_code <= higher


def file_response(status_code: int = 200, filename: str = None, file_path: str = None) -> Union[FileResponse, None]:
    """File response generation for api responses

    Args:
        status_code (int, optional): Status code to be sent along with the content. Defaults to 200.
        filename (str, optional): File name of file. Defaults to None.
        file_path (str, optional): Path to file. Defaults to None.

    Returns:
        Union[FileResponse, None]: Returns either file response or none
    """
    return FileResponse(
        filename=filename,
        status_code=status_code,
        path=file_path
    )


def successful_response(status_code: int = 200, message: str = None, payload: any = None, success: bool = True) -> JSONResponse:
    """Successful response generation for api responses

    Args:
        status_code (int, optional): Status code to be sent along with the content. Defaults to 200.
        message (str, optional): Message if needed for api response. Defaults to None.
        payload (any, optional): Data of response. Defaults to None.

    Returns:
        JSONResponse: FastAPI response with status code
    """

    body = {
        "success": success
    }

    if message:
        body["message"] = message
    if payload:
        body["payload"] = payload

    if not is_valid_status(lower=200, higher=300, status_code=status_code):
        raise ValueError(f"Invalid status code {status_code}")

    return JSONResponse(
        status_code=status_code,
        content=body
    )


def server_error(status_code: int = 500, message: str = None, payload: any = None) -> JSONResponse:
    """Server Error response generation for api responses

    Args:
        status_code (int, optional): Status code to be sent along with the content. Defaults to 200.
        message (str, optional): Message if needed for api response. Defaults to None.
        payload (any, optional): Data of response. Defaults to None.

    Returns:
        JSONResponse: FastAPI response with status code
    """

    body = {}
    if message:
        body["message"] = message
    if payload:
        body["payload"] = payload

    if not is_valid_status(lower=500, higher=600, status_code=status_code):
        raise ValueError(f"Invalid status code {status_code}")

    return JSONResponse(
        status_code=status_code,
        content=body
    )


def user_error(status_code: int = 400, message: str = None, payload: any = None) -> JSONResponse:
    """Server Error response generation for api responses

    Args:
        status_code (int, optional): Status code to be sent along with the content. Defaults to 200.
        message (str, optional): Message if needed for api response. Defaults to None.
        payload (any, optional): Data of response. Defaults to None.

    Returns:
        JSONResponse: FastAPI response with status code
    """

    body = {}
    if message:
        body["message"] = message
    if payload:
        body["payload"] = payload

    if not is_valid_status(lower=400, higher=500, status_code=status_code):
        raise ValueError(f"Invalid status code {status_code}")

    return JSONResponse(
        status_code=status_code,
        content=body
    )
