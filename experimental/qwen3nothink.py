from ollama import chat, generate
from pydantic import BaseModel

class Answer(BaseModel):
    summary: str
    details: str

response = chat(
    model="qwen3:8b",
    messages=[{"role": "user", "content": "Summarize the theory of evolution."}],
    format=Answer.model_json_schema(),
    options={"enable_thinking": False}
)

response2=generate(model="qwen3:8b", 
                          prompt="Summarize the theory of evolution.", 
                          format=Answer.model_json_schema(),
                          options={"enable_thinking": False})

answer = Answer.model_validate_json(response["message"]["content"])
print(answer)
print()
print('_'*80)
print()
answer2 = Answer.model_validate_json(response2["response"])
print(answer2)