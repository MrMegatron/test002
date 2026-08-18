from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL



class Settings(BaseSettings):
    """
    Data Agent 全局配置。

    这些值默认从 backend/.env 文件读取。
    """

    # =========================
    # 应用配置
    # =========================

    app_name: str = "Data Agent API"

    # =========================
    # MySQL 配置
    # =========================

    mysql_host: str #= "127.0.0.1"

    mysql_port: int #= 3306

    mysql_user: str

    mysql_password: str

    mysql_database: str

    # =========================
    # DeepSeek 配置
    # =========================

    deepseek_api_key: str = ""

    deepseek_base_url: str = "https://api.deepseek.com"

    deepseek_model: str = ""

    # =========================
    # Data Agent 安全配置
    # =========================

    allowed_tables: str #= "customers,orders"

    max_query_rows: int = 200

    # =========================
    # Pydantic Settings 配置
    # =========================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def allowed_table_list(self) -> list[str]:
        """
        把：

        customers,orders

        转换成：

        ["customers", "orders"]
        """

        return [
            table.strip()
            for table in self.allowed_tables.split(",")
            if table.strip()
        ]

    @property
    def database_url(self) -> URL:
        """
        生成 SQLAlchemy 使用的数据库连接地址。

        最终相当于：

        mysql+pymysql://用户:密码@主机:端口/数据库
        """

        return URL.create(
            drivername="mysql+pymysql",

            username=self.mysql_user,

            password=self.mysql_password,

            host=self.mysql_host,

            port=self.mysql_port,

            database=self.mysql_database,

            query={
                "charset": "utf8mb4"
            }
        )


@lru_cache
def get_settings() -> Settings:
    """
    创建并缓存配置对象。

    程序运行期间只需要读取一次 .env。
    """

    return Settings()


settings = get_settings()
