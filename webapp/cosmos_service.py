from azure.cosmos import CosmosClient
from django.conf import settings

class CosmosService:
    def __init__(self):
        self.client = CosmosClient(settings.COSMOS_DB_URL, credential=settings.COSMOS_DB_KEY)
        self.database = self.client.get_database_client(settings.COSMOS_DB_DATABASE)
        self.container = self.database.get_container_client(settings.COSMOS_DB_CONTAINER)

    def create_item(self, item):
        return self.container.upsert_item(item)

    def get_items(self, query=None):
        if query:
            return list(self.container.query_items(query=query, enable_cross_partition_query=True))
        return list(self.container.read_all_items())