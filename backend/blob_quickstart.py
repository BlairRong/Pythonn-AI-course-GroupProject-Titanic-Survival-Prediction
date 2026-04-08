import os
from azure.storage.blob import BlobServiceClient

# Connection string (copied from Azure portal) 连接字符串（从 Azure 门户复制）
conn_str = conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")

# create 创建 BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(conn_str)

# 1. Create a container (equivalent to a folder).创建容器（相当于文件夹）
container_name = "my-test-container"
container_client = blob_service_client.create_container(container_name)
print(f"container '{container_name}' create successfully")

# 2. upload file 上传文件
blob_name = "sample.txt"
blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
content = b"Hello, Azure Storage!"
blob_client.upload_blob(content)
print(f"file '{blob_name}' upload successfully")

# 3. list all blob from container 列出容器中的所有 blob
print("\nfile from container:")
blob_list = blob_service_client.get_container_client(container_name).list_blobs()
for blob in blob_list:
    print(f"- {blob.name}")

# 4. download file 下载文件
downloaded = blob_client.download_blob().readall()
print(f"\ndownload the content: {downloaded.decode()}")

# 5. clean the resource(option) 清理资源（可选）
# blob_client.delete_blob()
# blob_service_client.delete_container(container_name)