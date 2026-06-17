from langchain_groq import ChatGroq
from dotenv import load_dotenv
from agent.tools import get_product_details,get_similar_products,get_user_profile
from util.filter import filter_products
from util.cart import add_to_cart,remove_from_cart,get_cart,update_cart_quantity,clear_cart,checkout
import os

tools = [filter_products,get_product_details,get_similar_products,add_to_cart,remove_from_cart,get_cart,update_cart_quantity,clear_cart,get_user_profile,checkout]

def create_llm():
    load_dotenv()

    os.environ["GROQ_API_KEY"]=os.getenv("GROQ_API_KEY")
 
    # llm = ChatGroq(model="openai/gpt-oss-20b")
    llm = ChatGroq(model="openai/gpt-oss-120b")
    llm_with_tools = llm.bind_tools(tools)
    return llm_with_tools 