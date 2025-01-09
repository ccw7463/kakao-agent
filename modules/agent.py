from . import *
from utils.util import google_search_scrape, extract_content

class State(MessagesState):
    is_search: str
    is_personal: str
    is_preference: str
    
class ChatbotAgent:
    def __init__(self):
        self.LIMIT_LENGTH = 12
        self.SEARCH_RETRY_COUNT = 5
        self.SEARCH_RESULT_COUNT = 4
        self.SEARCH_MINIMUM_RESULT = 1
        self.system_prompt = prompt_config.system_message
        self.llm = ChatOpenAI(model="gpt-4o")
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
        builder.add_node("_Node_decide_personal", self._Node_decide_personal)
        builder.add_node("_Node_decide_preference", self._Node_decide_preference)
        builder.add_node("_Node_decide_search", self._Node_decide_search)
        builder.add_node("_Node_write_memory", self._Node_write_memory)
        builder.add_node("_Node_answer", self._Node_answer)
        builder.add_node("_Node_optimize_memory", self._Node_optimize_memory)
        builder.add_edge(START, "_Node_decide_personal")
        builder.add_edge(START, "_Node_decide_preference")
        builder.add_edge(START, "_Node_decide_search")
        builder.add_edge(["_Node_decide_personal", "_Node_decide_preference", "_Node_decide_search"], "_Node_write_memory")
        builder.add_edge("_Node_write_memory", "_Node_answer")
        builder.add_edge("_Node_answer", "_Node_optimize_memory")
        builder.add_edge("_Node_optimize_memory", END)
        ShortTermMemory = MemorySaver()
        LongTermMemory = InMemoryStore()
        self.graph = builder.compile(checkpointer=ShortTermMemory,
                                     store=LongTermMemory)

    @trace_function(enable_print=False, only_func_name=True)
    def _Node_decide_personal(self, state: State):
        """
            Des:
                개인정보 여부가 있는지 판단하는 노드
        """
        query = state["messages"][-1].content
        prompt = [SystemMessage(content=prompt_config.decide_personal_prompt)] + [HumanMessage(content=query)]
        return {"is_personal":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _Node_decide_preference(self, state: State):
        """
            Des:
                답변 선호도 여부가 있는지 판단하는 노드
        """
        query = state["messages"][-1].content
        prompt = [SystemMessage(content=prompt_config.decide_preference_prompt)] + [HumanMessage(content=query)]
        return {"is_preference":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _Node_decide_search(self, state: State):
        """
            Des:
                검색 여부를 결정하는 노드
        """
        query = state["messages"][-1].content
        prompt = [SystemMessage(content=prompt_config.decide_search_prompt)] + [HumanMessage(content=query)]
        return {"is_search":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _Node_write_memory(self, state: State, 
                            config: RunnableConfig, 
                            store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 개인정보/선호도/검색결과 등을 저장하는 노드
        """
        query = state["messages"][-1].content
        namespace = ("memories", config["configurable"]["user_id"])
        
        # 개인정보 판단 및 저장
        if state.get("is_personal") == "YES":
            personal_memory = self._get_memory(namespace=namespace, 
                                                key="personal_info", 
                                                store=store)
            system_message = prompt_config.create_memory_prompt.format(memory=personal_memory)
            # print(f"{RED}Write Memory system_message : {system_message}{RESET}")
            memory_prompt = [SystemMessage(content=system_message)] + [HumanMessage(content=query)]
            store.put(namespace=namespace, 
                        key="personal_info", 
                        value={"memory":self.llm.invoke(memory_prompt).content})    
        if state.get("is_preference") == "YES":
            preference_memory = self._get_memory(namespace=namespace, 
                                                 key="personal_preference", 
                                                 store=store)
            system_message = prompt_config.create_preference_prompt.format(preference=preference_memory)
            # print(f"{RED}Create Preference system_message : {system_message}{RESET}")
            preference_prompt = [SystemMessage(content=system_message)] + [HumanMessage(content=query)]
            store.put(namespace=namespace, 
                      key="personal_preference", 
                      value={"memory":self.llm.invoke(preference_prompt).content})

        if state.get("is_search") == "YES":
            main_context, suffix_context = self.web_search(query)
            store.put(namespace=namespace, 
                      key="main_context", 
                      value={"memory":main_context})
            store.put(namespace=namespace, 
                      key="suffix_context", 
                      value={"memory":suffix_context})
            
            
    @trace_function(enable_print=False, only_func_name=True)
    def web_search(self, query):
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
            try:
                desc, detailed_content = extract_content(link)
            except:
                pass
            try:
                if "Enable JavaScript and cookies" in detailed_content: # TODO 동적페이지 처리방식 필요
                    continue
            except:
                continue
            main_context += f"제목 : {result.get('title')}\n링크 : {link}\n설명 : {desc}\n내용 : {detailed_content}\n\n"    
            suffix_context += f"""
📌 참고내용 [{idx+1}]
제목 : {result.get('title')}
링크 : {link}
설명 : {desc}
"""
        return main_context, suffix_context
        
    @trace_function(enable_print=False, only_func_name=True)
    def _Node_answer(self, state: State, 
                    config: RunnableConfig,
                    store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 답변을 생성하는 노드
        """
        namespace = ("memories", config["configurable"]["user_id"])
        personal_memory = self._get_memory(namespace=namespace, 
                                           key="personal_info", 
                                           store=store)
        personal_preference = self._get_memory(namespace=namespace, 
                                               key="personal_preference", 
                                               store=store)

        if state.get("is_search") == "YES":
            main_context = self._get_memory(namespace=namespace, 
                                            key="main_context", 
                                            store=store)
            suffix_context = self._get_memory(namespace=namespace, 
                                              key="suffix_context", 
                                              store=store)
            system_message = prompt_config.answer_prompt.format(memory=personal_memory,
                                                                preference=personal_preference)
            user_prompt = prompt_config.answer_with_context.format(context=main_context,
                                                                   query=state['messages'][-1].content)
            prompt = [SystemMessage(content=self.system_prompt+system_message)] + [HumanMessage(content=user_prompt)]
            print(f"{BLUE}Answer with Search prompt : {prompt[0].content}{RESET}")
            return {"messages": self._postprocess(self.llm.invoke(prompt).content) + "\n" + suffix_context}
        else:    
            system_message = prompt_config.answer_prompt.format(memory=personal_memory,
                                                                preference=personal_preference)
            prompt = [SystemMessage(content=self.system_prompt+system_message)] + state["messages"]
            print(f"{BLUE}Answer prompt : {prompt[0].content}{RESET}")
            return {"messages": self._postprocess(self.llm.invoke(prompt).content)}

    @trace_function(enable_print=False, only_func_name=True)
    def _Node_optimize_memory(self, 
                              state: State):
        """
            Des:
                메모리 최적화 함수
        """
        if len(state["messages"]) > self.LIMIT_LENGTH:
            delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:self.LIMIT_LENGTH//2]]
            return {"messages": delete_messages}
        else:
            return {"messages": state["messages"]}
    
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
        return self.graph.invoke({"messages": messages}, config=self.config)

    def _postprocess(self,
                     result:str):
        result = result.replace("**", "").replace("*", "").replace("_", "")
        return result