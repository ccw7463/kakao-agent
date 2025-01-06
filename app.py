from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import openai
from dotenv import load_dotenv
import asyncio
import httpx
from openai import OpenAI
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI()
app = FastAPI()
user_responses = {}

def make_kakao_response(text: str) -> dict:
    return {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": text}}]},
    }
    
async def get_gpt_response(question: str) -> str:
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신의 이름은 '미네르바'이고 카카오톡에서 활동하는 챗봇입니다. 당신은 사용자의 질문과 요청에 친절하게 응답합니다. 가능한 핵심적인 내용만을 전달하세요. 적절한 이모티콘을 사용해도 좋습니다."},
                {"role": "user", "content": f"{question}"},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GPT 답변 호출 도중 에러가 발생했습니다: {e}"

async def send_to_callback(callback_url: str, response_data: dict):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(callback_url, json=response_data)
    except Exception as e:
        print(f"Callback URL 전송 중 에러 발생: {e}")

@app.post("/question")
async def handle_question(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    user_request = data.get("userRequest")
    callback_url = user_request.get("callbackUrl")
    question = user_request.get("utterance").strip()
    gpt_response = await get_gpt_response(question=question)
    kakao_response = make_kakao_response(gpt_response)
    if callback_url:
        background_tasks.add_task(send_to_callback, callback_url, kakao_response)
    return JSONResponse({
        "version": "2.0",
        "useCallback": True,
    })


# @app.post("/question")
# async def handle_question_without_callback(request: Request, background_tasks: BackgroundTasks):
#     data = await request.json()
#     user_id = data["userRequest"]["user"]["id"]
#     user_question = data["action"]["params"]["question"].strip()
#     response_message = "질문을 받았습니다. AI에게 물어보고 올게요!"
#     response = make_kakao_response(response_message)
#     async def fetch_and_store_response():
#         gpt_response = await get_gpt_response(user_question)
#         print(gpt_response)
#         user_responses[user_id] = gpt_response
#     background_tasks.add_task(fetch_and_store_response)
#     return JSONResponse(response)

# @app.post("/ans")
# async def get_answer(request: Request):
#     data = await request.json()
#     user_id = data["userRequest"]["user"]["id"]
#     gpt_response = user_responses.get(user_id, "질문을 못 받았어요. 다시 물어봐 주세요!")
#     response = make_kakao_response(gpt_response)
#     return JSONResponse(response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
