from src.utils.log_handler import get_logger
from src.utils.redis_handler import RedisClient

log = get_logger("abc_api")
log.info("starting up app")

redis_client = RedisClient()
img_handler = RedisClient(db=1)
