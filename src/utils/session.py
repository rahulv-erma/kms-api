from typing import Union

from src import redis_client, log
from src.utils.token import generate_token, decode_token


def create_session(user_id: str) -> Union[str, None]:
    """Function to create user session in redis

    Args:
        user_id (str): user id of user

    Returns:
        Union[str, None]: returns session id or none
    """
    try:
        token = generate_token(user_id=user_id)
        redis_client.set_key(
            key=token,
            token=user_id,
            ex=259200
        )

        return token

    except Exception:
        log.exception(f"Failed to create session for user {user_id}")
    return None


def get_session(sessionId: str) -> Union[str, None]:
    """Function to get user session from redis

    Args:
        sessionId (str): session id

    Returns:
        Union[str, None]: returns user id from session or none
    """
    try:
        session = redis_client.get_key(sessionId)
        if session:
            return decode_token(sessionId)["user_id"]
    except Exception:
        log.exception(f"Failed to get session for sessionId {sessionId}")
    return None


def delete_session(sessionId: str) -> bool:
    """Function to delete user session id from redis

    Args:
        sessionId (str): session id

    Returns:
        bool: returns bool true or false if it was successful
    """
    try:
        session = redis_client.get_key(sessionId)
        if session:
            redis_client.delete_key(sessionId)
            return True
    except Exception:
        log.exception(f"Failed to delete session for sessionId {sessionId}")
    return False
