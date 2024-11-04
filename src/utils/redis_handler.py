import redis
import os
from typing import Union


class RedisClient:
    """Class to handle redis connections
    """

    def __init__(self, db: int = 0):
        self.redis_client = redis.Redis.from_url(
            f"{os.getenv('REDIS_URI', None)}/{db}")

    def publish(self, channel: str, data: str):
        if not channel:
            print("No channel present for redis")
            return None

        if not data:
            print("No data present for redis")
            return None

        try:
            number = self.redis_client.publish(channel, data)
        except Exception as e:
            print(
                f"An exception occured while publishing to redis, exception {e}")
            return None

        if not number:
            print("No number present from redis")
            return None

        return True

    def set_key(self, key: str = None, token: str = None, ex: int = None) -> Union[str, None]:
        """Function to set a key in redis

        Args:
            key (str, optional): key of redis. Defaults to None.
            token (str, optional): value to set in redis. Defaults to None.
            ex (int, optional): expiry of redis. Defaults to None.

        Returns:
            Union[str, None]: Returns either a key or none
        """
        if not key:
            return None

        if not ex:
            ex = 86400

        self.redis_client.set(key, str(token), ex)

        return key

    def get_key(self, redis_key: str = None) -> Union[str, None]:
        """Function to get key from redis

        Args:
            redis_key (str, optional): key from redis to get. Defaults to None.

        Returns:
            Union[str, None]: Returns either a redis value or none
        """
        if not redis_key:
            return None

        token = self.redis_client.get(redis_key)
        if token:
            return token.decode()

        return None

    def delete_key(self, redis_key: str = None) -> Union[int, None]:
        """Function to delete a redis key

        Args:
            redis_key (str, optional): key of redis to delete. Defaults to None.

        Returns:
            Union[int, None]: Returns amount deleted or none
        """
        if not redis_key:
            return None

        return self.redis_client.delete(redis_key)

    def set_hset(self, redis_key: str = None, values: dict = None) -> bool:
        if not redis_key or not values:
            return False

        return self.redis_client.hmset(redis_key, values)

    def get_hset(self, redis_key: str = None) -> Union[dict, None]:
        if not redis_key:
            return None

        found_dict = self.redis_client.hgetall(redis_key)
        if found_dict:
            return found_dict
        return None
