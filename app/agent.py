from typing import Optional
from typing_extensions import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langsmith import traceable
import os
from app.config import get_settings

class AgentState(TypedDict):
    """
    TypedDict for the state of the agent.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model_used: str

class ProductionAgent:
    """
    Production Agent class that manages the state and behavior of the agent.
    """

    def __init__(self):
        self.settings = get_settings()

        self.settings = get_settings()

        os.environ["LANGCHAIN_TRACING_V2"] = str(
            self.settings.langchain_tracing_v2
        ).lower()
        os.environ["LANGCHAIN_API_KEY"] = self.settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = self.settings.langchain_project

        self.main_llm = ChatGoogleGenerativeAI(
            model=self.settings.primary_model,
            api_key=self.settings.gemini_api_key,
        )

        self.fallback_llm = ChatGoogleGenerativeAI(
            model=self.settings.fallback_model,
            api_key=self.settings.gemini_api_key
        )

        self.max_retries = self.settings.max_retries

        self.state_graph = self._build_state_graph()

    def _build_state_graph(self) -> StateGraph:
        """
        Build the state graph for the agent, defining states and transitions.
        """

        def process_messages(state: AgentState) -> AgentState:
            """
            Process messages in the current state and return the updated state.
            """
            try:
                result = self.main_llm.invoke(state['messages'])
                return {
                    "messages": [result],
                    "error": None,
                    "model_used": self.settings.primary_model,
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count": state['retry_count'] + 1,
                    "model_used": "",
                }

        def try_fallback(state: AgentState) -> AgentState:
            """
            Attempt to use the fallback model if the main model fails.
            """
            try:
                result = self.fallback_llm.invoke(state['messages'])
                return {
                    "messages": [result],
                    "error": None,
                    "model_used": self.settings.fallback_model,
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count": state['retry_count'] + 1,
                    "model_used": "",
                }

        def handle_error(state: AgentState) -> AgentState:
            """
            Return graceful error handling message.
            """
            return {
                "messages": [AIMessage(content="An error occurred. Please try again later.")],
                "model_used": "error_handler",

            }

        def route_after_process(state: AgentState) -> str:
            """
            Determine the next state based on the current state after processing.
            """
            if state['error'] is None:
                return "done"
            elif state['retry_count'] < self.max_retries:
                return "try_fallback"
            else:
                return "handle_error"

        def route_after_fallback(state: AgentState) -> str:
            """
            Determine the next state based on the current state after trying fallback.
            """
            if state['error'] is None:
                return "done"
            else:
                return "handle_error"

        graph = StateGraph(AgentState)

        graph.add_node("process", process_messages)
        graph.add_node("try_fallback", try_fallback)
        graph.add_node("handle_error", handle_error)

        graph.add_edge(START, "process")
        graph.add_conditional_edges("process", route_after_process, {
            "done": END,
            "try_fallback": "try_fallback",
            "handle_error": "handle_error"
        })
        graph.add_conditional_edges("try_fallback", route_after_fallback, {
            "done": END,
            "handle_error": "handle_error"
        })

        return graph.compile()

    @traceable(name="prod_agent_run")
    def invoke(self, message: str) -> dict:
        """
        Invoke the agent with a list of messages and return the response messages.
        """

        result = self.state_graph.invoke({
            "messages": [HumanMessage(content=message)],
            "error": None,
            "retry_count": 0,
            "model_used": ""
        })

        return {
            "response": result['messages'][-1].content,
            "model_used": result.get('model_used', "unknown"),
            "error": result.get('error')
        }
