from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.config import settings


# ============================================================
# 1. 创建 SQLAlchemy Engine
# ============================================================

engine: Engine = create_engine(
    settings.database_url,

    # 在真正使用连接之前检查连接是否仍然有效
    pool_pre_ping=True,

    # 避免连接长时间存在导致 MySQL 主动断开
    pool_recycle=3600,

    # 正式项目建议 False
    # 如果改成 True，会在控制台打印 SQL
    echo=False
)


# ============================================================
# 2. 测试数据库连接
# ============================================================

def test_database_connection() -> bool:
    """
    测试 Python 是否能够正常连接 MySQL。

    成功：
        返回 True

    失败：
        SQLAlchemy / PyMySQL 会直接抛出异常
    """

    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT 1")
        )

        value = result.scalar()

        return value == 1


# ============================================================
# 3. 获取数据库表结构
# ============================================================

def get_database_schema() -> str:
    """
    获取 Data Agent 允许查询的数据表结构。

    注意：
    不会把整个数据库所有表都提供给大模型。

    只会读取 .env 的：

        ALLOWED_TABLES

    例如：

        customers,orders

    最终返回类似：

        表名: customers
          - id: INTEGER, NOT NULL
          - customer_name: VARCHAR(100), NOT NULL
          - city: VARCHAR(50), NULL

        表名: orders
          - id: INTEGER, NOT NULL
          - customer_id: INTEGER, NOT NULL
          - product_name: VARCHAR(100), NOT NULL
          - amount: DECIMAL(10,2), NOT NULL
    """

    inspector = inspect(engine)

    # 获取当前数据库真正存在的表
    existing_tables = set(
        inspector.get_table_names()
    )

    schema_blocks: list[str] = []

    # 只遍历我们允许查询的表
    for table_name in settings.allowed_table_list:

        # 如果配置文件写了这个表，
        # 但数据库实际上没有，就跳过
        if table_name not in existing_tables:
            continue

        # 获取这个表的所有字段
        columns = inspector.get_columns(
            table_name
        )

        column_lines: list[str] = []

        for column in columns:

            column_name = column["name"]

            column_type = str(
                column["type"]
            )

            nullable = column.get(
                "nullable",
                True
            )

            nullable_text = (
                "NULL"
                if nullable
                else "NOT NULL"
            )

            column_lines.append(
                f"  - {column_name}: "
                f"{column_type}, "
                f"{nullable_text}"
            )

        table_schema = (
            f"表名: {table_name}\n"
            + "\n".join(column_lines)
        )

        schema_blocks.append(
            table_schema
        )

    if not schema_blocks:
        raise RuntimeError(
            "没有读取到允许访问的数据表，"
            "请检查 ALLOWED_TABLES 配置"
        )

    return "\n\n".join(
        schema_blocks
    )


# ============================================================
# 4. 执行 SELECT 查询
# ============================================================

def execute_select_query(
    sql: str
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    执行查询 SQL。

    参数：

        sql:
            已经经过 sql_guard.py
            安全校验后的 SELECT SQL

    返回：

        columns:
            字段名称列表

        rows:
            查询数据列表

    例如：

        columns = [
            "id",
            "customer_name"
        ]

        rows = [
            {
                "id": 1,
                "customer_name": "张三"
            },
            {
                "id": 2,
                "customer_name": "李四"
            }
        ]
    """

    with engine.connect() as connection:

        result = connection.execute(
            text(sql)
        )

        columns = list(
            result.keys()
        )

        rows = [
            dict(row._mapping)
            for row in result.fetchall()
        ]

    return columns, rows