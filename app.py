from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import os
import openai
from dotenv import load_dotenv
import asyncio
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

async def get_gpt_response(prompt: str) -> str:
    try:
        add_prompt = "자세하게 답변하라는 요청이 없다면, 최대한 간단하게 핵심내용만 생성하라." # TODO 향후 수정필요
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4",
            messages=[
                {"role": "developer", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"{prompt} {add_prompt}"},
            ],
        )
        return response.choices[0].message.content
    except:
        return "GPT 답변 호출도중 에러가 발생했습니다."

@app.post("/question")
async def handle_question(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    user_id = data["userRequest"]["user"]["id"]
    user_question = data["action"]["params"]["question"].strip()
    response_message = "질문을 받았습니다. AI에게 물어보고 올게요!"
    response = make_kakao_response(response_message)
    async def fetch_and_store_response():
        gpt_response = await get_gpt_response(user_question)
        print(gpt_response)
        user_responses[user_id] = gpt_response

    background_tasks.add_task(fetch_and_store_response)

    return JSONResponse(response)

@app.post("/ans")
async def get_answer(request: Request):
    data = await request.json()
    user_id = data["userRequest"]["user"]["id"]
    gpt_response = user_responses.get(user_id, "질문을 못 받았어요. 다시 물어봐 주세요!")
    response = make_kakao_response(gpt_response)
    return JSONResponse(response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
