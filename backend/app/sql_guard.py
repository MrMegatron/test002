import re

import sqlglot
from sqlglot import expressions as exp

from app.config import settings


class SqlValidationError(ValueError):
    """
    SQL安全检查失败时抛出的自定义异常。
    """

    pass


# 明确禁止出现的危险关键字
FORBIDDEN_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "REPLACE",
    "MERGE",
    "GRANT",
    "REVOKE",
    "CALL",
    "EXECUTE",
    "LOAD DATA",
    "INTO OUTFILE",
    "INTO DUMPFILE",
}


def clean_sql(sql: str) -> str:
    """
    清理大模型可能返回的 Markdown SQL 代码块。

    例如：

    ```sql
    SELECT id FROM customers;
    ```

    会被转换为：

    SELECT id FROM customers
    """

    sql = sql.strip()

    # 删除开头的 ```sql 或 ```
    sql = re.sub(
        r"^```(?:sql)?\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    # 删除结尾的 ```
    sql = re.sub(
        r"\s*```$",
        "",
        sql,
    )

    # 删除末尾分号
    sql = sql.strip().rstrip(";").strip()

    return sql


def validate_select_sql(sql: str) -> str:
    """
    检查 SQL 是否可以安全执行。

    当前规则：

    1. SQL不能为空
    2. 每次只能执行一条SQL
    3. 只能执行SELECT
    4. 禁止INSERT / UPDATE / DELETE等操作
    5. 只能访问ALLOWED_TABLES中的表
    6. 自动添加LIMIT
    7. LIMIT不能超过MAX_QUERY_ROWS

    返回：
        经过安全处理后的SQL
    """

    # -------------------------
    # 第1步：清理SQL
    # -------------------------

    sql = clean_sql(sql)

    if not sql:
        raise SqlValidationError(
            "SQL不能为空"
        )

    # -------------------------
    # 第2步：检查危险关键字
    # -------------------------

    upper_sql = sql.upper()

    for keyword in FORBIDDEN_KEYWORDS:

        if keyword in upper_sql:
            raise SqlValidationError(
                f"SQL中禁止使用：{keyword}"
            )

    # -------------------------
    # 第3步：使用sqlglot解析SQL
    # -------------------------

    try:

        statements = sqlglot.parse(
            sql,
            read="mysql",
        )

    except sqlglot.errors.ParseError as exc:

        raise SqlValidationError(
            f"SQL语法解析失败：{exc}"
        ) from exc

    # -------------------------
    # 第4步：只能有一条SQL
    # -------------------------

    if len(statements) != 1:

        raise SqlValidationError(
            "一次只能执行一条SQL"
        )

    statement = statements[0]

    # -------------------------
    # 第5步：必须包含SELECT
    # -------------------------

    select_node = statement.find(
        exp.Select
    )

    if select_node is None:

        raise SqlValidationError(
            "系统只允许执行SELECT查询"
        )

    # -------------------------
    # 第6步：禁止危险SQL节点
    # -------------------------

    forbidden_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
    )

    for node_type in forbidden_nodes:

        if statement.find(node_type):

            raise SqlValidationError(
                "检测到禁止执行的数据库操作"
            )

    # -------------------------
    # 第7步：获取SQL访问的所有表
    # -------------------------

    used_tables = {
        table.name
        for table in statement.find_all(
            exp.Table
        )
        if table.name
    }

    # -------------------------
    # 第8步：获取允许访问的表
    # -------------------------

    allowed_tables = set(
        settings.allowed_table_list
    )

    # -------------------------
    # 第9步：计算非法表
    # -------------------------

    illegal_tables = (
        used_tables - allowed_tables
    )

    if illegal_tables:

        raise SqlValidationError(
            "SQL访问了未授权的数据表："
            + ", ".join(
                sorted(illegal_tables)
            )
        )

    # -------------------------
    # 第10步：处理LIMIT
    # -------------------------

    limit_node = statement.args.get(
        "limit"
    )

    # SQL没有写LIMIT
    if limit_node is None:

        statement = statement.limit(
            settings.max_query_rows
        )

    else:

        try:

            current_limit = int(
                limit_node.expression.name
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
        ):

            current_limit = (
                settings.max_query_rows
            )

        # 如果用户写LIMIT 10000
        # 自动改成最大允许值
        if (
            current_limit
            > settings.max_query_rows
        ):

            statement = statement.limit(
                settings.max_query_rows
            )

    # -------------------------
    # 第11步：重新生成MySQL SQL
    # -------------------------

    safe_sql = statement.sql(
        dialect="mysql"
    )

    return safe_sql