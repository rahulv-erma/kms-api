import os

from src.database.mongo.mongo import MongoConnect
from src import log

mongo_client = MongoConnect(log=log, database=os.getenv("MONGO_DATABASE"))
