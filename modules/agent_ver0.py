
# 단순 채팅 기능 O
# 멀티턴 기능 O
# 메모리 처리 기능 O

from . import *

class ChatbotAgent:
    def __init__(self):
        self.LIMIT_LENGTH = 10
        self.system_prompt = "당신의 이름은 '미네르바'이고 카카오톡에서 활동하는 챗봇입니다. 'ccw'님이 관리하고 있는 챗봇입니다. 당신은 사용자의 질문과 요청에 친절하게 응답합니다. 가능한 핵심적인 내용만을 전달하세요.\n"
        self.llm = ChatOpenAI(model="gpt-4o")
        self.config = {"configurable": {"thread_id": "default",
                                        "user_id": "default"}}
        self._build_graph()
        
    async def get_gpt_response(self,
                               question: str) -> str:
        if question == "새로운 대화":
            self._build_graph()
            question = "안녕하세요~"
        question = HumanMessage(content=question)
        return self._call_graph([question])["messages"][-1].content
    
    def set_config(self,
                   user_id:str):
        self.config = {"configurable": {"thread_id": user_id,
                                        "user_id": user_id}}
        
    def _build_graph(self):
        """
            Des:
                그래프 생성함수
        """
        builder = StateGraph(MessagesState)
        builder.add_node("_Node_answer", self._Node_answer)
        builder.add_node("_Node_write_memory", self._Node_write_memory)
        builder.add_node("_Node_optimize_memory", self._Node_optimize_memory)
        builder.add_edge(START, "_Node_answer")
        builder.add_edge("_Node_answer", "_Node_write_memory")
        builder.add_conditional_edges("_Node_write_memory", self._check_memory_length)
        builder.add_edge("_Node_optimize_memory", END)
        self.graph = builder.compile(checkpointer=ShortTermMemory,
                                      store=LongTermMemory)

    @trace_function(enable_print=False, only_node=True)
    def _Node_answer(self, 
                    state: MessagesState, 
                    config: RunnableConfig,
                    store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 답변을 생성하는 노드
        """
        summary = state.get("summary", "")
        namespace = ("memories", config["configurable"]["user_id"])
        key = "chat_user_memory"
        memory = self._get_memory(namespace=namespace, 
                            key=key, 
                            store=store)
        system_message = prompt_config.answer_prompt.format(memory=memory, summary=summary)
        prompt = [SystemMessage(content=self.system_prompt+system_message)] + state["messages"]
        # print(f"{PINK}\n{prompt[0].content}\n{RESET}")
        response = self.llm.invoke(prompt)
        return {"messages": response}

    @trace_function(enable_print=False, only_node=True)
    def _Node_write_memory(self,
                          state: MessagesState, 
                          config: RunnableConfig, 
                          store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 개인정보로 저장하는 노드
        """
        namespace = ("memories", config["configurable"]["user_id"])
        key = "chat_user_memory"
        memory = self._get_memory(namespace=namespace, 
                                  key=key, 
                                  store=store)
        system_message = prompt_config.create_memory_prompt.format(memory=memory)
        prompt = [SystemMessage(content=system_message)]+state["messages"]
        response = self.llm.invoke(prompt)
        store.put(namespace=namespace, 
                key=key, 
                value={"memory":response.content})
        # print(f"{RED}\n현재 STATE 개수: {len(state['messages'])}\n{RESET}")
    
    @trace_function(enable_print=False, only_node=True)
    def _Node_optimize_memory(self,
                              state: MessagesState):
        """
            Des:
                메모리 최적화 함수
        """
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-self.LIMIT_LENGTH]]
        return {"messages": delete_messages}
    
    def _check_memory_length(self,
                             state: MessagesState):
        if len(state["messages"]) > self.LIMIT_LENGTH:
            return "_Node_optimize_memory"
        else:
            return END
    
    def _get_memory(self,
                    namespace, 
                    key,
                    store:BaseStore):
        """
            Des:
                현재 저장된 사용자 정보를 가져오는 함수
        """
        existing_memory = store.get(namespace=namespace,
                                    key=key)
        return existing_memory.value.get('memory') if existing_memory else ""

    def _call_graph(self, messages):
        return self.graph.invoke({"messages": messages}, 
                                 config=self.config)
