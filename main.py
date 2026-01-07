from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
import database
import json
import os
import io
from PIL import Image

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

class ChatRequest(BaseModel):
    user_id: str
    message: str

def get_max_eligibility(income, emi, l_type):
    roi = 0.085 if l_type == "HOME" else 0.12
    tenure = 240 if l_type == "HOME" else 60
    budget = (income * 0.5) - emi
    if budget <= 0: return 0
    r = roi / 12
    max_p = budget / (r * ((1+r)**tenure) / ((1+r)**tenure - 1))
    return round(max_p, 2)

def sales_agent_chat(user_data, msg):
    system_instruction = f"""
    ROLE: Alex, Sales Officer. 
    CURRENT USER DATA: {user_data}
    LOGIC:
    1. Ask Home/Personal loan.
    2. Ask Monthly Salary & Monthly EMIs.
    3. Calculate eligibility and ask for desired amount.
    4. If amount < Max Eligible, move to KYC and ask for: 1 Govt ID, 3 Salary Slips, 6mo Bank Statement.
    STRICT JSON OUTPUT: {{"reply": "...", "extracted_data": {{"loan_type": str, "income": float, "existing_emi": float, "loan_amount": float}}}}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[msg],
            config=types.GenerateContentConfig(system_instruction=system_instruction, response_mime_type="application/json")
        )
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except:
        return {"reply": "I'm processing that. Could you clarify your monthly income?", "extracted_data": {}}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    user = database.get_user(request.user_id) or (database.create_user(request.user_id) or database.get_user(request.user_id))
    
    ai_res = sales_agent_chat(user, request.message)
    ext = ai_res.get("extracted_data", {})
    
    updates = {k: v for k, v in ext.items() if v is not None}
    if updates:
        database.update_user_data(request.user_id, **updates)
        user = database.get_user(request.user_id)
        if user['declared_income'] and user['declared_emi'] and not user['max_eligible']:
            limit = get_max_eligibility(user['declared_income'], user['declared_emi'], user['loan_type'])
            database.update_user_data(request.user_id, max_eligible=limit)

    return {"reply": ai_res.get('reply', "How can I help further?")}

# --- KYC & VERIFICATION LOGIC ---
@app.post("/api/kyc/verify")
async def run_verification(user_id: str):
    user = database.get_user(user_id)
    # 5(a) Income Check
    income_err = abs(user['declared_income'] - user['verified_income']) / user['verified_income']
    check_a = "PASSED" if income_err <= 0.10 else "FAILED"
    
    # 5(b) & (c) Mocked for this flow
    check_b = "PASSED" 
    check_c = "PASSED" # In production, this would call a CIBIL API
    
    results = {"check_a": check_a, "check_b": check_b, "check_c": check_c}
    
    if all(v == "PASSED" for v in results.values()):
        letter_prompt = f"Write a sanction letter for {user_id} for {user['loan_amount']}."
        letter = client.models.generate_content(model='gemini-2.0-flash', contents=[letter_prompt])
        database.update_user_data(user_id, status="APPROVED", sanction_letter_text=letter.text, **results)
        return {"status": "APPROVED", "view_link": f"/api/sanction/{user_id}"}
    else:
        database.update_user_data(user_id, status="HUMAN_REVIEW", **results)
        return {"status": "FAILED", "reason": "Divergence detected. Officer will call in 2 hours."}

@app.get("/api/sanction/{user_id}", response_class=HTMLResponse)
async def get_letter(user_id: str):
    user = database.get_user(user_id)
    return f"<div style='padding:40px; border:2px solid blue;'><h1>SANCTION LETTER</h1><p>{user['sanction_letter_text']}</p></div>"