from modules.agent import ChatbotAgent
from modules.db import UserData
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
import httpx
import requests
import time
from loguru import logger
app = FastAPI()

async def get_answer(agent: ChatbotAgent, 
                     question: str, 
                     kakao_callback_url: str):
    """
        Des:
            GPT 응답 생성 및 Webhook 호출
        Args:
            agent: ChatbotAgent 인스턴스
            question: 사용자 질문
            kakao_callback_url: 카카오 콜백 URL
    """
    START_TIME = time.time()
    if "새로운 대화 시작할래요!" in question:
        agent._build_graph()
        response = "안녕하세요🤗 무엇을 도와드릴까요?"    
    elif ("사용법" == question) or ("사용법 안내" in question):
        response = """사용법에 대해 간략히 알려드릴게요!

궁금하거나 도움이 필요한 내용을 저한테 말씀주시면 돼요 😊

예를 들어서, '삼성전자에 대해 알려줘'라고 물어보시면 삼성전자에 대한 최신 정보를 기반으로 답변해드릴 수 있어요. 그리고 번역하거나 요약하는 요청도 가능해요!

만약 리스트 메뉴에서 '💬 새로운 대화 시작할래요!'를 선택하면, 이전 대화를 초기화하고 새롭게 시작할 수 있으니 참고해주세요.

그럼 이제 무엇을 도와드릴까요? 🤗"""
    else:
        response = await agent.get_response(question=question)
        END_TIME = time.time()
        logger.info(f"Length : {len(response)}")
        logger.info(f"Generation Time : {END_TIME - START_TIME}")
    await send_to_webhook(
        webhook_url="https://changwoo.ngrok.dev/webhook",
        response_data={"response": response, 
                       "kakao_callback_url": kakao_callback_url}
    )

async def send_to_webhook(webhook_url: str, 
                          response_data: dict):
    """
        Des:
            Webhook 호출 함수
                - AI 답변 생성완료 후 호출
        Args:
            webhook_url: Webhook URL
            response_data: Webhook 호출 시 전달할 데이터
    """
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=response_data)
    except Exception as e:
        logger.error(f"Webhook 호출 중 에러 발생: {e}")
        
@app.post("/webhook")
async def webhook_handler(request: Request):
    """
        Des:
            카카오 서버로 콜백
        Args:
            request: Webhook 호출 시 전달된 데이터
                - response: AI 답변
                - kakao_callback_url: 카카오 콜백 URL
    """
    request_data = await request.json()
    call_back = requests.post(
        request_data['kakao_callback_url'],
        json={"version": "2.0", 
              "template": {"outputs": [{"simpleText": {"text": request_data['response']}}]}})
    logger.info(f"call_back: {call_back.status_code}, {call_back.json()}")
    return 'OK'

@app.on_event("startup")
async def startup_event():
    app.state.agent = ChatbotAgent()

@app.post("/question")
async def handle_question(request: Request, 
                          background_tasks: BackgroundTasks):
    """
        Des:
            실제 사용자 요청 처리 함수
        Args:
            request: 사용자 요청
            background_tasks: 백그라운드 작업 태스크
        Returns:
            JSONResponse: 카카오 서버에 응답 반환 
                - version: 2.0 필수
                - useCallback: True 필수 -> 콜백함수 사용할것을 의미
    """
    request_data = await request.json()
    user_request = request_data.get("userRequest")
    user_id = user_request.get("user").get("id")
    agent = app.state.agent
    agent.set_config(user_id=user_id)
    agent._build_graph()
    background_tasks.add_task(get_answer, 
                              agent=agent, 
                              question=user_request.get("utterance").strip(), 
                              kakao_callback_url=user_request.get("callbackUrl"))
    return JSONResponse({
        "version": "2.0",
        "useCallback": True
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
