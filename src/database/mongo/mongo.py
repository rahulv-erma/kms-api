import pymongo
import os
from bson.objectid import ObjectId
import logging
import time


class MongoConnect():
    """Class to handle mongo connection"""

    def __init__(self, log: logging.Logger, database: str = None):
        self.log = log
        self.client = self.__connect()
        self.database = self.__database(database=database)

    def __connect(self) -> pymongo.MongoClient:
        """Function to connect to database

        Raises:
            ConnectionRefusedError: Raises error for no connection

        Returns:
            MongoClient: Returns mongo client
        """
        try:
            if self.client.server_info():
                return self.client
        except Exception:
            pass
        try:
            client = pymongo.MongoClient(
                host=os.getenv('MONGO_CONNECTION_URI')
            )
            return client
        except Exception:
            self.log.exception(
                "Unable to establish a connection to Mongo database")
            raise ConnectionRefusedError

    def __database(self, database: str) -> pymongo.MongoClient:
        """Initializes connection to database

        Args:
            database (str): database name to connect to

        Raises:
            ConnectionRefusedError: If failed connection

        Returns:
            MongoClient: Client for mongo connection to the database
        """
        try:
            return self.client[database]
        except Exception:
            self.log.exception(
                f"Unable to establish a connection to Mongo Database: {database}")
            raise ConnectionRefusedError

    def objectID(self) -> ObjectId:
        """Function to generate mongo object ID

        Returns:
            ObjectId: Returns object ID
        """
        return ObjectId()

    def close(self):
        """Function to close a connection
        """
        self.client.close()

    def insert(self, collection: str, content: dict) -> bool:
        """Function to insert single document into mongo

        Args:
            collection (str): collection to insert into
            content (dict): content of the insert

        Raises:
            ValueError: Missing values

        Returns:
            bool: returns bool for if the insert was successful
        """
        if not collection:
            raise ValueError("No collection supplied for insert")
        if not content:
            raise ValueError("No content supplied to be inserted")
        retries = 0
        while True:
            try:
                content['_id'] = self.objectID()
                self.database[collection].insert_one(content)
                return True
            except Exception:
                if retries == 10:
                    self.log.exception(
                        f"Failed to insert content into collection: {collection}")
                    break
                retries += 1
                time.sleep(5)
        return False

    def insert_bulk(self, collection: str, content: list) -> bool:
        """Function to insert bul document into mongo

        Args:
            collection (str): collection to insert into
            content (list): list of content of the insert

        Raises:
            ValueError: Missing values

        Returns:
            bool: returns bool for if the insert was successful
        """
        if not collection:
            raise ValueError("No collection supplied for insert")
        if not content:
            raise ValueError("No content supplied to be inserted")
        bulk_operations = []
        chunk_index = 0
        CHUNK_SIZE = 20

        while True:
            chunk = content[chunk_index:chunk_index+CHUNK_SIZE]
            if not len(chunk):
                break

            operations = []
            for item in chunk:
                item['_id'] = self.objectID()
                operations.append(pymongo.InsertOne(item))
            bulk_operations.append(operations)

            chunk_index += CHUNK_SIZE

        for operations in bulk_operations:
            retries = 0
            while True:
                try:
                    self.database[collection].bulk_write(operations)
                    break
                except Exception:
                    if retries == 10:
                        self.log.exception(
                            f"Failed to insert content into collection: {collection}")
                        return False
                    retries += 1
                time.sleep(5)
        return True

    def find(self, collection: str, content: dict, exclude: dict = None) -> dict:
        """function to find from db

        Args:
            collection (str): collection to find in
            content (dict): what to find based on
            exclude (dict, optional): what not to return, aka _id, etc. Defaults to None.

        Raises:
            ValueError: no collection given
            ValueError: no content given

        Returns:
            dict: what was needed from the database
        """

        if not collection:
            raise ValueError("No collection supplied for insert")
        if not content:
            raise ValueError("No content supplied to be inserted")
        retries = 0
        while True:
            try:
                if not exclude:
                    return self.database[collection].find(content)
            except Exception:
                if retries == 10:
                    self.log.exception(
                        f"Failed to find content from collection: {collection}")
                    break
                retries += 1
                time.sleep(5)
        return False

    def find_one(self, collection: str, content: dict, exclude: dict = None) -> dict:
        if not collection:
            raise ValueError("No collection supplied for insert")
        if not content:
            raise ValueError("No content supplied to be inserted")
        retries = 0
        while True:
            try:
                if not exclude:
                    return self.database[collection].find_one(content)
            except Exception:
                if retries == 10:
                    self.log.exception(
                        f"Failed to find content from collection: {collection}")
                    break
                retries += 1
                time.sleep(5)
        return False

    def update(self, collection: str, content: dict, query: dict, many: bool = False):
        """function to update in db

        Args:
            collection (str): collection to update query in
            content (dict): what to update it with
            query (dict): query of what needs to be found to update
            many (bool, optional): whether multiple to update or not. Defaults to False.

        Raises:
            ValueError: no collection given
            ValueError: no content given
            ValueError: no query given

        Returns:
            bool: true if worked, false if not
        """

        if not collection:
            raise ValueError("No collection supplied for insert")
        if not content:
            raise ValueError("No content supplied to be inserted")
        if not query:
            raise ValueError("No query supplied to be inserted")
        retries = 0
        while True:
            try:
                if many:
                    self.database[collection].update_many(
                        query, {"$set": content})
                else:
                    self.database[collection].update_one(
                        query, {"$set": content})
                return True
            except Exception:
                if retries == 10:
                    self.log.exception(
                        f"Failed to update content in collection: {collection}")
                    break
                retries += 1
                time.sleep(5)
        return False

    def delete(self, collection: str, query: dict, many: bool = False):
        """function to delete from mongodb

        Args:
            collection (str): collection to make delete from
            query (dict): query to find what needs to be deleted, etc.
            many (bool, optional): whether it needs to delete multiple or not. Defaults to False.

        Raises:
            ValueError: if no collection provided
            ValueError: if no query provided

        Returns:
            bool: true if worked, false if failed
        """

        if not collection:
            raise ValueError("No collection supplied for insert")
        if not query:
            raise ValueError("No query supplied to be inserted")
        retries = 0
        while True:
            try:
                if many:
                    self.database[collection].delete_many(query)
                else:
                    self.database[collection].delete_one(query)
                return True
            except Exception:
                if retries == 10:
                    self.log.exception(
                        f"Failed to delete content from collection: {collection}")
                    break
                retries += 1
                time.sleep(5)
        return False
