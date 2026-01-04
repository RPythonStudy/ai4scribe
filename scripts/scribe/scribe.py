from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel
import os
import json
import shutil
from summarizer import Summarizer
from auth_calendar import CalendarService
from dotenv import load_dotenv
import sys



load_dotenv()

app = FastAPI()
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Initialize Summarizer once
try:
    gemini_summarizer = Summarizer()
except Exception as e:
    print(f"Warning: Failed to init Summarizer (Check API Key): {e}")
    gemini_summarizer = None

# Initialize Calendar Service
calendar_service = CalendarService(
    credentials_path=os.path.join(os.getcwd(), "credentials.json"),
    token_path=os.path.join(os.getcwd(), "token.json")
)

class SummarizeRequest(BaseModel):
    text: str
    meeting_title: str | None = None
    user_notes: list[str] = []

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    transcription_language = os.getenv("TRANSCRIPTION_LANGUAGE", "ko-KR")
    auto_summarize_interval = os.getenv("AUTO_SUMMARIZE_INTERVAL", "0")
    audio_chunk_seconds = os.getenv("AUDIO_CHUNK_SECONDS", "0")
    import json
    presets = {}
    if os.path.exists("attendee_presets.json"):
        try:
            with open("attendee_presets.json", "r", encoding="utf-8") as f:
                presets = json.load(f)
        except Exception as e:
            print(f"Error loading presets: {e}")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "transcription_language": transcription_language,
        "auto_summarize_interval": auto_summarize_interval,
        "audio_chunk_seconds": audio_chunk_seconds,
        "attendee_presets": json.dumps(presets)
    })

@app.post("/reset")
async def reset_endpoint():
    if gemini_summarizer:
        gemini_summarizer.reset()
        return {"status": "Summary context reset"}
    return {"error": "Summarizer not initialized"}

@app.post("/summarize")
async def summarize_endpoint(req: SummarizeRequest):
    if not gemini_summarizer:
        return {"error": "Summarizer not initialized (Check server logs/API Key)"}
    
    try:
        # Pass user_notes to the summarizer
        result = gemini_summarizer.summarize(req.text, meeting_title=req.meeting_title, user_notes=req.user_notes)
        if isinstance(result, dict):
            return result
        return {"summary": result}
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze_audio")
async def analyze_audio_endpoint(
    file: UploadFile = File(...), 
    meeting_title: str = Form(None),
    user_notes: str = Form(None)  # Received as JSON string
):
    if not gemini_summarizer:
        return {"error": "Summarizer not initialized"}
    
    # Save UploadFile to a temporary file
    temp_filename = f"temp_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse user_notes if present
        import json
        notes_list = []
        if user_notes:
            try:
                notes_list = json.loads(user_notes)
            except:
                print("Failed to parse user_notes JSON")

        print(f"Processing audio file: {temp_filename}, Title: {meeting_title}, Notes: {len(notes_list)}")
        result = gemini_summarizer.analyze_audio(temp_filename, meeting_title=meeting_title, user_notes=notes_list)
        
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        # Cleanup temp file
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.get("/calendar/events")
async def get_calendar_events():
    """Fetch upcoming calendar events."""
    result = calendar_service.get_upcoming_events(max_results=10)
    return result

class SaveMinutesRequest(BaseModel):
    text: str
    meeting_title: str
    event_id: str | None = None

@app.post("/save_minutes")
async def save_minutes_endpoint(req: SaveMinutesRequest):
    """Save minutes to Drive and optionally attach to Calendar event."""
    
    # 1. Create filename with timestamp to avoid duplicates
    import datetime
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M")
    filename = f"[회의록] {date_str} {req.meeting_title} ({time_str})"
    
    # 2. Upload to Drive
    file_id, web_link = calendar_service.upload_to_drive(filename, req.text)
    
    if not file_id:
        return {"error": "Google Drive 업로드 실패"}
    
    result_msg = f"회의록이 저장되었습니다. (Drive)\n링크: {web_link}"
    
    # 3. Attach to Calendar if event_id is present
    if req.event_id:
        success, msg = calendar_service.attach_to_calendar_event(
            req.event_id, file_id, web_link, filename
        )
        if success:
            result_msg += "\n\n캘린더 일정에도 첨부되었습니다! 📅"
        else:
            result_msg += f"\n\n캘린더 첨부 실패: {msg}"
            
    return {"status": "success", "message": result_msg, "link": web_link}

@app.post("/presets")
async def save_pset_endpoint(data: dict):
    preset_name = data.get("name")
    participants = data.get("participants", [])
    
    if not preset_name or not participants:
        return {"status": "error", "message": "Invalid data"}
    
    presets = {}
    if os.path.exists("attendee_presets.json"):
        try:
            with open("attendee_presets.json", "r", encoding="utf-8") as f:
                presets = json.load(f)
        except: pass
        
    presets[preset_name] = participants
    
    with open("attendee_presets.json", "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=4)
        
    return {"status": "success", "presets": presets}

@app.get("/contacts/search")
async def search_contacts_endpoint(q: str):
    if not calendar_service.service:
        calendar_service.authenticate()
    
    results = calendar_service.search_contacts(q)
    return {"results": results}

def run_server():
    host = os.getenv("SCRIBE_HOST", "127.0.0.1")
    port = int(os.getenv("SCRIBE_PORT", "8000"))
    
    print("Starting Web Bridge Server...")
    print(f"Open http://{host}:{port} in Chrome to start transcription.")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_server()
