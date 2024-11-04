from jose import jwt
import os
import datetime


def generate_token(user_id: str) -> str:
    """Function to generate a session id from a user_id, creates a jwt token

    Args:
        user_id (str): user id of the user

    Returns:
        str: returns jwt token
    """
    jwt_token = jwt.encode(
        claims={
            "user_id": user_id,
            "createdAt": str(datetime.datetime.utcnow())
        },
        key=os.getenv("JWT_SECRET"),
        algorithm="HS256"
    )

    return jwt_token


def decode_token(sessionId: str) -> str:
    """Function to decode session id of user

    Args:
        sessionId (str): session id from user session

    Returns:
        str: returns a user id
    """
    user_id = jwt.decode(
        token=sessionId,
        key=os.getenv("JWT_SECRET"),
        algorithms=["HS256"]
    )

    return user_id
