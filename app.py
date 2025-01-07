from modules.agent import ChatbotAgent
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
    gpt_response = await agent.get_gpt_response(question=question)
    END_TIME = time.time()
    logger.info(f"Length : {len(gpt_response)}")
    logger.info(f"Generation Time : {END_TIME - START_TIME}")
    await send_to_webhook(
        webhook_url="https://changwoo.ngrok.dev/webhook",
        response_data={"gpt_response": gpt_response, 
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
                - gpt_response: AI 답변
                - kakao_callback_url: 카카오 콜백 URL
    """
    request_data = await request.json()
    call_back = requests.post(
        request_data['kakao_callback_url'],
        json={"version": "2.0", 
              "template": 
                  {"outputs": [{"simpleText": {"text": request_data['gpt_response']}}]}})
    logger.info(f"call_back: {call_back.status_code}, {call_back.json()}")
    return 'OK'

@app.on_event("startup")
async def startup_event():
    app.state.agent = ChatbotAgent()

@app.post("/question")
async def handle_question(request: Request, 
                          background_tasks: BackgroundTasks):
    request_data = await request.json()
    user_request = request_data.get("userRequest")
    agent = app.state.agent
    agent.set_config(user_id=user_request.get("user").get("id"))
    
    # 실제 작업은 백그라운드에서 비동기로 실행
    background_tasks.add_task(get_answer, 
                              agent=agent, 
                              question=user_request.get("utterance").strip(), 
                              kakao_callback_url=user_request.get("callbackUrl"))

    # useCallback True를 먼저 리턴해줘야 CallBack 사용 가능
    return JSONResponse({
        "version": "2.0",
        "useCallback": True
    })

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
