from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx
import uvicorn
from utils.util import set_env
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, START, StateGraph, END
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

class ChatbotAgent:
    def __init__(self):
        self.system_prompt = "당신의 이름은 '미네르바'이고 카카오톡에서 활동하는 챗봇입니다. 'ccw'님이 관리하고 있는 챗봇입니다. 당신은 사용자의 질문과 요청에 친절하게 응답합니다. 가능한 핵심적인 내용만을 전달하세요. 친절하게 대답하세요. 이모티콘을 사용해도 좋습니다."
        self.llm = ChatOpenAI(model="gpt-4o")
        self.config = {"configurable": {"thread_id": "default",
                                        "user_id": "default"}}
        self._build_graph()
        
    def make_kakao_response(self,
                            text: str) -> dict:
        return {
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": text}}]},
        }
    
    async def get_gpt_response(self,
                               question: str) -> str:
        if question == "새로운 대화":
            self._build_graph()
            question = "안녕하세요~"
        question = HumanMessage(content=question)
        return self._call_graph([question])["messages"][-1].content

    async def send_to_callback(self,
                               callback_url: str,
                               response_data: dict):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(callback_url, json=response_data)
        except Exception as e:
            print(f"Callback URL 전송 중 에러 발생: {e}")
    
    def set_config(self,
                   user_id:str):
        self.config = {"configurable": {"thread_id": user_id,
                                        "user_id": user_id}}
        
    def _build_graph(self):
        ShortTermMemory = MemorySaver()
        builder = StateGraph(MessagesState)
        builder.add_node("Node__answer", self._Node__answer)
        builder.add_edge(START, "Node__answer")
        builder.add_edge("Node__answer", END)
        self.graph = builder.compile(checkpointer=ShortTermMemory)

    def _Node__answer(self,
                     state: MessagesState):
        return {"messages": [self.llm.invoke([SystemMessage(content=self.system_prompt)] + state["messages"][-10:])]}

    def _call_graph(self, messages):
        return self.graph.invoke({"messages": messages}, 
                                 config=self.config,
                                 stream_mode="values")

set_env()
app = FastAPI()
@app.on_event("startup")
async def startup_event():
    app.state.agent = ChatbotAgent()

@app.post("/question")
async def handle_question(request: Request, 
                          background_tasks: BackgroundTasks):
    data = await request.json()
    user_request = data.get("userRequest")
    callback_url = user_request.get("callbackUrl")
    question = user_request.get("utterance").strip()
    agent = app.state.agent
    agent.set_config(user_id=user_request.get("user").get("id"))
    gpt_response = await agent.get_gpt_response(question=question)
    kakao_response = agent.make_kakao_response(gpt_response)
    if callback_url:
        background_tasks.add_task(agent.send_to_callback, 
                                  callback_url, 
                                  kakao_response)
    return JSONResponse({
        "version": "2.0",
        "useCallback": True,
    })
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
