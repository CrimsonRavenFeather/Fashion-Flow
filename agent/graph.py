from agent.llm import create_llm, tools
from agent.state import State
from langchain_core.messages import AIMessage,HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

llm_with_tools = create_llm()

def llm_tool(state:State):
    return {"messages":llm_with_tools.invoke(state["messages"])}

def create_graph():
    # Creating graph
    builder=StateGraph(State)

    builder.add_node("llm_tool",llm_tool)
    builder.add_node("tools",ToolNode(tools))

    builder.add_edge(START,"llm_tool")
    builder.add_conditional_edges(
        "llm_tool",
        # If the latest message (result) from assistant is a tool call -> tools_condition routes to tools
        # If the latest message (result) from assistant is not a tool call -> goes to END
        tools_condition
    )

    builder.add_edge("tools","llm_tool")

    # Adding memory to graph
    memory=MemorySaver()
    graph_builder=builder.compile(checkpointer=memory)

    return graph_builder
    