from . import *
from utils.util import google_search_scrape, extract_content

class State(MessagesState):
    is_search: str
    main_context : str
    suffix_context : str
    
class ChatbotAgent:
    def __init__(self):
        self.LIMIT_LENGTH = 10
        self.SEARCH_RETRY_COUNT = 5
        self.SEARCH_RESULT_COUNT = 4
        self.SEARCH_MINIMUM_RESULT = 1
        self.system_prompt = prompt_config.system_message
        self.llm = ChatOpenAI(model="gpt-4o") # TODO api key 입력받는 형태로 변경필요
        self.config = {"configurable": {"thread_id": "default",
                                        "user_id": "default"}}
        self._build_graph()
        
    async def get_gpt_response(self,
                               question: str) -> str:
        if "새로운 대화 시작할래요!" in question:
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
        """
            Des:
                검색 여부를 결정하는 노드
        """
        return {"is_search": [self.llm.invoke([SystemMessage(content=prompt_config.decide_search_prompt)] + state["messages"])][0].content.upper()}

    @trace_function(enable_print=False, only_node=True)
    def _Node_search(self,
                    state: State):
        """
            Des:
                검색 정보 생성 노드
        """
        query = state['messages'][-1].content # TODO humanmessage 인지 체크필요
        prompt = prompt_config.generate_search_info.format(query=query)
        search_info = self.llm.invoke(prompt).content
        for _ in range(self.SEARCH_RETRY_COUNT):
            results = google_search_scrape(search_info, num_results=self.SEARCH_RESULT_COUNT)
            if len(results) >= self.SEARCH_MINIMUM_RESULT:
                break
        print(f"{RED}검색어 : {search_info}\n검색결과 : {len(results)}\n{RESET}")
        main_context = ''
        suffix_context = ''
        for idx, result in enumerate(results):
            link = result.get("link")
            desc, detailed_content = extract_content(link)
            if "Enable JavaScript and cookies" in detailed_content:
                continue # TODO 처리필요
            main_context += f"제목 : {result.get('title')}\n링크 : {link}\n설명 : {desc}\n내용 : {detailed_content}\n\n"    
            suffix_context += f"""
📌 참고내용 [{idx+1}]
제목 : {result.get('title')}
링크 : {link}
설명 : {desc}
"""
        return {"main_context": main_context, "suffix_context": suffix_context}

    def _decide_search(self,
                       state: State):
        """
            Des:
                검색 여부를 결정하는 함수
        """
        if "YES" in state["is_search"]:
            return "_Node_search"
        else:
            return "_Node_answer"
        
    def _check_memory_length(self,
                             state: State):
        """
            Des:
                메모리 길이 체크 함수
        """
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
        """
            Des:
                그래프 호출 함수
        """
        return self.graph.invoke({"messages": messages}, 
                                 config=self.config)

    
