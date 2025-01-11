from . import *
from utils.util import google_search_scrape, extract_content
from modules.db import UserData

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
        self.search_keyword = ''
        self.llm = ChatOpenAI(model="gpt-4o")
        self.config = {"configurable": {"thread_id": "default",
                                        "user_id": "default"}}
        self.user_data = UserData()
        self._build_graph()
        
    async def get_response(self,
                           question: str) -> str:
        question = HumanMessage(content=question)
        return self._call_graph([question])["messages"][-1].content
    
    def set_config(self,
                   user_id:str):
        self.config = {"configurable": {"thread_id": user_id, # 어차피 카톡은 채팅창 여러개를 띄울수없기에, thread 값도 user_id로 고정
                                        "user_id": user_id}}
        
    def _build_graph(self):
        """
            Des:
                그래프 생성함수
        """
        builder = StateGraph(State)
        builder.add_node("_node_initialize", self._node_initialize)
        builder.add_node("_node_decide_personal", self._node_decide_personal)
        builder.add_node("_node_decide_preference", self._node_decide_preference)
        builder.add_node("_node_decide_search", self._node_decide_search)
        builder.add_node("_node_write_memory", self._node_write_memory)
        builder.add_node("_node_answer", self._node_answer)
        builder.add_node("_node_optimize_memory", self._node_optimize_memory)
        builder.add_edge(START, "_node_initialize")
        builder.add_edge("_node_initialize", "_node_decide_personal")
        builder.add_edge("_node_initialize", "_node_decide_preference")
        builder.add_edge("_node_initialize", "_node_decide_search")
        builder.add_edge(["_node_decide_personal", "_node_decide_preference", "_node_decide_search"], "_node_write_memory")
        builder.add_edge("_node_write_memory", "_node_answer")
        builder.add_edge("_node_answer", "_node_optimize_memory")
        builder.add_edge("_node_optimize_memory", END)
        ShortTermMemory = MemorySaver()
        LongTermMemory = InMemoryStore()
        self.graph = builder.compile(checkpointer=ShortTermMemory,
                                     store=LongTermMemory)
        print(f"{GREEN}[agent.py] 그래프 빌드 완료{RESET}")
        
    @trace_function(enable_print=False, only_func_name=True)
    def _node_initialize(self, 
                         state: State,
                         config: RunnableConfig, 
                         store: BaseStore):
        """
            Des:
                초기화 함수
                    - 메모리 초기화
                        - 케이스 1) 사용자가 채팅 처음 시작 -> set_config -> DB에 정보없으니까 else로 가서 종료
                        - 케이스 2) 사용자가 채팅을 '새로운 대화'로 시작함 -> 그래프 새로 빌드 -> 롱텀 초기화 -> set_config -> 사용자 정보가 있으니까 데이터 삽입
                        - 케이스 3) 사용자가 채팅을 했었는데 내가 서버 다시킴 -> 그래프 새로 빌드 -> 롱텀 초기화 -> set_config -> 사용자 정보가 있으니까 데이터 삽입
                    - 사용자 정보 초기화
                    - 사용자 요청메시지 취합
        """
        user_id = config["configurable"]["user_id"]
        namespace = ("memories", user_id)
        user_info = self.user_data.process_request(user_id)
        if user_info:
            print(f"{YELLOW}[agent.py] 데이터베이스에 이전 사용자 정보가 있습니다. 그래프내에 데이터를 삽입합니다.{RESET}")
            store.put(namespace=namespace, 
                      key="personal_info", 
                      value={"memory":user_info[1]})
            store.put(namespace=namespace,  
                      key="personal_preference", 
                      value={"memory":user_info[2]})
        else:
            print(f"{YELLOW}[agent.py] 데이터베이스에 이전 사용자 정보가 없습니다.{RESET}")
            
        # 사용자 요청메시지만 취합해서 정리 (라우팅 등에서 사용)
        self.previous_human_messages = [i.content for i in state["messages"] if isinstance(i, HumanMessage)]
        self.previous_human_messages_query = ''
        for idx, message in enumerate(self.previous_human_messages, start=1):
            if idx != len(self.previous_human_messages):
                self.previous_human_messages_query += f"{idx}번째 요청 메시지 : {message}\n"
            else:
                self.previous_human_messages_query += f"[현재 요청 메시지] : {message}\n"
        print(f"{RED}요청 메시지 취합한거 메시지 : {self.previous_human_messages_query}{RESET}")
        
    @trace_function(enable_print=False, only_func_name=True)
    def _node_decide_personal(self, 
                              state: State):
        """
            Des:
                사용자 요청에 개인정보 여부가 있는지 판단하는 노드
        """
        prompt = [SystemMessage(content=prompt_config.decide_personal_prompt)] + [HumanMessage(content=self.previous_human_messages_query)]
        return {"is_personal":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _node_decide_preference(self, 
                                state: State):
        """
            Des:
                사용자 요청에 답변 선호도 여부가 있는지 판단하는 노드
        """
        prompt = [SystemMessage(content=prompt_config.decide_preference_prompt)] + [HumanMessage(content=self.previous_human_messages_query)]
        return {"is_preference":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _node_decide_search(self, 
                            state: State):
        """
            Des:
                사용자 요청에 검색 여부를 결정하는 노드
        """
        prompt = [SystemMessage(content=prompt_config.decide_search_prompt)] + [HumanMessage(content=self.previous_human_messages_query)]
        return {"is_search":[self.llm.invoke(prompt)][0].content.upper()}

    @trace_function(enable_print=False, only_func_name=True)
    def _node_write_memory(self, 
                           state: State, 
                           config: RunnableConfig, 
                           store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 개인정보/선호도/검색결과 등을 저장하는 노드
        """
        user_id = config["configurable"]["user_id"]
        namespace = ("memories", user_id)
        if state.get("is_personal") == "YES":
            personal_memory = self._get_memory(namespace=namespace, 
                                               key="personal_info", 
                                               store=store)
            system_message = prompt_config.create_memory_prompt.format(memory=personal_memory)
            memory_prompt = [SystemMessage(content=system_message)] + [HumanMessage(content=self.previous_human_messages_query)]
            result = self.llm.invoke(memory_prompt).content
            store.put(namespace=namespace, 
                      key="personal_info", 
                      value={"memory":result})    
            self.user_data.update_user_info(user_id, "personal_info", result)
        if state.get("is_preference") == "YES":
            preference_memory = self._get_memory(namespace=namespace, 
                                                 key="personal_preference", 
                                                 store=store)
            system_message = prompt_config.create_preference_prompt.format(preference=preference_memory)
            preference_prompt = [SystemMessage(content=system_message)] + [HumanMessage(content=self.previous_human_messages_query)]
            result = self.llm.invoke(preference_prompt).content
            store.put(namespace=namespace, 
                      key="personal_preference", 
                      value={"memory":result})
            self.user_data.update_user_info(user_id, "personal_preference", result)

        if state.get("is_search") == "YES":
            main_context, suffix_context = self._web_search()
            store.put(namespace=namespace, 
                      key="main_context", 
                      value={"memory":main_context})
            store.put(namespace=namespace, 
                      key="suffix_context", 
                      value={"memory":suffix_context})
        
    @trace_function(enable_print=False, only_func_name=True)
    def _node_answer(self, 
                     state: State, 
                    config: RunnableConfig,
                    store: BaseStore):
        """
            Des:
                사용자 메시지를 인식하고, 답변을 생성하는 노드
        """
        user_id = config["configurable"]["user_id"]
        namespace = ("memories", user_id)
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
            response = self.llm.invoke(prompt).content
            return {"messages": AIMessage(content=self._postprocess(response) + "\n" + suffix_context)}
        else:    
            system_message = prompt_config.answer_prompt.format(memory=personal_memory,
                                                                preference=personal_preference)
            prompt = [SystemMessage(content=self.system_prompt+system_message)] + state["messages"]
            print(f"{BLUE}Answer prompt : {prompt[0].content}{RESET}")
            response = self.llm.invoke(prompt).content
            return {"messages": AIMessage(content=self._postprocess(response))}

    @trace_function(enable_print=False, only_func_name=True)
    def _node_optimize_memory(self, 
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

    @trace_function(enable_print=False, only_func_name=False)
    def _web_search(self):
        prompt = prompt_config.generate_search_keyword.format(query=self.previous_human_messages_query,
                                                              previous_search_keyword=self.search_keyword)
        self.search_keyword = self.llm.invoke(prompt).content
        for _ in range(self.SEARCH_RETRY_COUNT):
            results = google_search_scrape(self.search_keyword, num_results=self.SEARCH_RESULT_COUNT)
            if len(results) >= self.SEARCH_MINIMUM_RESULT:
                break
        print(f"{RED}검색어 : {self.search_keyword}\n검색결과 : {len(results)}\n{RESET}")
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