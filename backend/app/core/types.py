# from typing import TypedDict
from typing import Any


# class QueryResult(TypedDict):
#     rows: list[dict]
#     columns: list[str]

Row = dict[str, Any]
Rows = list[Row]
