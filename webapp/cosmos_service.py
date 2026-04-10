from azure.cosmos import CosmosClient
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class CosmosService:
    def __init__(self):
        self.client = None
        self.database = None
        self.container = None
        try:
            self.client = CosmosClient(settings.COSMOS_DB_URL, credential=settings.COSMOS_DB_KEY)
            self.database = self.client.get_database_client(settings.COSMOS_DB_DATABASE)
            self.container = self.database.get_container_client(settings.COSMOS_DB_CONTAINER)
        except Exception as e:
            logger.error(f"Cosmos DB connection failed: {e}")
            # 降级：服务不可用，后续操作会捕获异常

    def create_item(self, item):
        if not self.container:
            raise Exception("Cosmos DB container not available")
        return self.container.upsert_item(item)

    def get_items(self, query=None):
        if not self.container:
            return []
        if query:
            return list(self.container.query_items(query=query, enable_cross_partition_query=True))
        return list(self.container.read_all_items())