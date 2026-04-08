import pyodbc

# 请务必替换以下信息为你 Azure 数据库的真实值
server = 'titaninc-server-siying.database.windows.net'  # 你的服务器全称
database = 'titanic_db'                                 # 数据库名
username = 'titanic_admin'                              # 管理员登录名（不加 @服务器名）
password = ''                                           # 密码 自己输入

conn_str = f"""
    Driver={{ODBC Driver 18 for SQL Server}};
    Server={server},1433;
    Database={database};
    Uid={username};
    Pwd={password};
    Encrypt=yes;
    TrustServerCertificate=no;
    Connection Timeout=90;
"""

print("try to connet...")
try:
    conn = pyodbc.connect(conn_str)
    print("✅ connect successfully! ")
    conn.close()
except Exception as e:
    print(f"❌ connect failed: {e}")