from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from typing import Annotated
from typing_extensions import TypedDict


class State(TypedDict):
    messages:Annotated[list[AnyMessage],add_messages]