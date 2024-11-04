from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
import os
from typing import Union
import requests

from src import log
from src.api.api_models import global_models
from src.database.sql.user_functions import get_user
from src.utils.session import get_session


class AuthClient(HTTPBearer):
    """Class to handle authorization functionality"""

    def __init__(self, auto_error: bool = True, use_auth: bool = True, permission_nodes: list = None):
        super(AuthClient, self).__init__(auto_error=auto_error)
        self.use_auth = use_auth
        self.external_auth = str(
            os.getenv("EXTERNAL_AUTH", 'false')).lower() == 'true'
        self.auth_url = str(os.getenv("AUTH_URL"))
        if self.use_auth and self.external_auth and not self.auth_url:
            raise ValueError("Must provide enviornment variable AUTH_URL")
        self.permission_nodes = permission_nodes

    async def __call__(self, request: Request) -> Union[bool, HTTPException]:
        """Function to route api endpoints through Bearer authentification

        Args:
            request (Request): FastAPI request passed through a function

        Raises:
            HTTPException: If no authorized, raises http exception

        Returns:
            Union[bool, HTTPException]: Bool to depict authorization granted or error for no authorization
        """
        if not self.use_auth:
            return True  # returns true if no auth service needed
        credentials: HTTPAuthorizationCredentials = await super(AuthClient, self).__call__(request)
        if not credentials:
            raise HTTPException(
                status_code=403, detail="Must provide an authorization token")
        if not credentials.scheme == 'Bearer':
            raise HTTPException(
                status_code=403, detail=f"Invalid authorization scheme {credentials.scheme}")
        user = await self.has_access(credentials.credentials)
        if user:
            return user
        raise HTTPException(status_code=403, detail="Not Authorized")

    async def has_access(self, auth_token: str) -> bool:
        """Function that is used to validate the token in the case that it requires it

        Args:
            auth_token (str): Bearer token passed through from the api request

        Returns:
            bool: Returns true or false depending on if authorization is granted
        """
        if not auth_token:
            return False

        if self.external_auth:
            if await self.call_auth_service(auth_token):
                return True
            return False

        user = await self.check_auth(auth_token)
        if user:
            return user

        return False

    async def call_auth_service(self, auth_token: str) -> bool:
        """Function to call auth service if necessary (external)

        Args:
            auth_token (str): Bearer token passed through from the api request

        Returns:
            bool: Returns true or false depending on if authorization is granted
        """
        json_body = None
        if self.permission_nodes:
            json_body = {
                "permission_nodes": self.permission_nodes
            }

        response = requests.get(
            url=self.auth_url,
            json=json_body
        )

        if not response.status_code == 200:
            # Do something here, i suggest making this function loop and retrying if you have a status code that isnt 200
            return False

        if not response.json()["success"]:
            return False

        return True

    async def check_auth(self, auth_token: str) -> Union[bool, global_models.User]:
        """Function to call auth service if necessary (internal)

        Args:
            auth_token (str): Bearer token passed through from the api request

        Returns:
            bool: Returns true or false depending on if authorization is granted
        """
        try:
            user_id = get_session(auth_token)
            if not user_id:
                return False

            # TODO: need to check perms
            user = await get_user(user_id=user_id)
            if not user:
                return False

            return user

        except Exception:
            log.exception(f"Failed to check auth for auth token {auth_token}")
