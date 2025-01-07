from . import *
from utils.util import google_search_scrape, extract_content

class State(MessagesState):
    is_search: str
    main_context : str
    suffix_context : str
    
class ChatbotAgent:
    def __init__(self):
        self.LIMIT_LENGTH = 10
        self.system_prompt = "당신의 이름은 '미네르바'이고 카카오톡에서 활동하는 챗봇입니다. 'ccw'님이 관리하고 있는 챗봇입니다. 당신은 사용자의 질문과 요청에 친절하게 응답합니다. 가능한 핵심적인 내용만을 전달하세요. 웃는 이모지를 사용하여 친절하게 답변하세요.\n"
        self.llm = ChatOpenAI(model="gpt-4o")
        self.config = {"configurable": {"thread_id": "default",
                                        "user_id": "default"}}
        self._build_graph()
        
    async def get_gpt_response(self,
                               question: str) -> str:
        if question == "새로운 대화":
            self._build_graph()
        question = HumanMessage(content="안녕하세요~")
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
        builder = StateGraph(State)
        builder.add_node("_Node_answer", self._Node_answer)
        builder.add_node("_Node_write_memory", self._Node_write_memory)
        builder.add_node("_Node_optimize_memory", self._Node_optimize_memory)
        builder.add_node("_Node_decide_search", self._Node_decide_search)
        builder.add_node("_Node_search", self._Node_search)
        
        builder.add_edge(START, "_Node_decide_search")
        builder.add_conditional_edges("_Node_decide_search", self._decide_search)
        builder.add_edge("_Node_search", "_Node_answer")
        builder.add_edge("_Node_answer", "_Node_write_memory")
        builder.add_conditional_edges("_Node_write_memory", self._check_memory_length)
        builder.add_edge("_Node_optimize_memory", END)
        self.graph = builder.compile(checkpointer=ShortTermMemory,
                                      store=LongTermMemory)

    @trace_function(enable_print=False, only_node=True)
    def _Node_answer(self, 
                    state: State, 
                    config: RunnableConfig,
                    store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 답변을 생성하는 노드
        """
        # 시스템 메시지 지정
        namespace = ("memories", config["configurable"]["user_id"])
        key = "chat_user_memory"
        memory = self._get_memory(namespace=namespace, 
                            key=key, 
                            store=store)
        system_message = prompt_config.answer_prompt.format(memory=memory)
        
        # context 확인 및 답변 생성
        if state.get("is_search") == "YES":
            prompt = prompt_config.answer_with_context.format(context=state["main_context"],
                                                              query=state['messages'][-1].content)
            answer = self.llm.invoke(prompt).content + "\n" + state.get("suffix_context")
            return {"messages": [AIMessage(content=answer)]}
        else:    
            prompt = [SystemMessage(content=self.system_prompt+system_message)] + state["messages"]
            # print(f"{PINK}\n{prompt[0].content}\n{RESET}")
            response = self.llm.invoke(prompt)
            return {"messages": response}

    @trace_function(enable_print=False, only_node=True)
    def _Node_write_memory(self,
                          state: State, 
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
                              state: State):
        """
            Des:
                메모리 최적화 함수
        """
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-self.LIMIT_LENGTH]]
        return {"messages": delete_messages}

    @trace_function(enable_print=False, only_node=True)
    def _Node_decide_search(self,
                           state: State):
        system_message = "현재 사용자 요청문이 뉴스 검색이 필요한지 판단하세요. 답변은 무조건 YES 또는 NO로 출력하세요."
        return {"is_search": [self.llm.invoke([SystemMessage(content=system_message)] + state["messages"])][0].content.upper()}

    @trace_function(enable_print=False, only_node=True)
    def _Node_search(self,
                    state: State):
        query = state['messages'][-1].content # TODO humanmessage 인지 체크필요
        prompt = prompt_config.generate_search_info.format(query=query)
        search_info = self.llm.invoke(prompt).content
        results = google_search_scrape(search_info, num_results=3)
        print(f"{RED}검색어 : {search_info}{RESET}")
        print(f"{RED}검색결과 : {len(results)}{RESET}")
        # TODO 결과없을때 처리필요
        main_context = ''
        suffix_context = ''
        for idx, result in enumerate(results):
            link = result.get("link")
            desc, detailed_content = extract_content(link)
            main_context += f"제목 : {result.get('title')}\n링크 : {link}\n설명 : {desc}\n내용 : {detailed_content}\n\n"    
            suffix_context += f"""
📌 참고내용 [{idx+1}]
제목 : {result.get('title')}
링크 : {link}
설명 : {desc}
"""
        return {"main_context": main_context, "suffix_context": suffix_context}


    def _check_memory_length(self,
                             state: State):
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

    def _call_graph(self, 
                    messages):
        return self.graph.invoke({"messages": messages}, 
                                 config=self.config)

    
    def _decide_search(self,
                       state: State):
        if "YES" in state["is_search"]:
            return "_Node_search"
        else:
            return "_Node_answer"