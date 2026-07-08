import os
import uuid
import threading
from typing import Dict, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import main

app = FastAPI(title="Dot Studio API")

# Setup directories
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
CLIPS_DIR = os.path.join(os.path.dirname(__file__), "my_clips")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

# Mount static and output folders
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")

# In-memory task store
tasks: Dict[str, Dict] = {}

class GenerateRequest(BaseModel):
    topic: Optional[str] = None
    script: Optional[str] = None
    language: str = "hi"
    gender: str = "female"
    voice: Optional[str] = None
    rate: str = "+0%"
    num_sentences: int = 8

# Mapping from languages to pre-installed system fonts
FONTS_MAP = {
    "hi": "/usr/share/fonts/chromeos/noto/NotoSansDevanagari-Regular.ttf",
    "mr": "/usr/share/fonts/chromeos/noto/NotoSansDevanagari-Regular.ttf",
    "ta": "/usr/share/fonts/chromeos/noto/NotoSansTamil-Regular.ttf",
    "te": "/usr/share/fonts/chromeos/noto/NotoSansTelugu-Regular.ttf",
    "bn": "/usr/share/fonts/chromeos/noto/NotoSansBengali-Regular.ttf",
}

def run_in_background(task_id: str, req: GenerateRequest):
    tasks[task_id]["status"] = "processing"
    
    def update_progress(message: str, percentage: int):
        tasks[task_id]["progress"] = percentage
        tasks[task_id]["message"] = message

    try:
        # Resolve font path
        font_path = FONTS_MAP.get(req.language)
        if font_path and not os.path.exists(font_path):
            font_path = None # Fallback if font is missing
            
        script_file_path = None
        if req.script:
            # Save user script text to a temporary file
            script_file_path = os.path.join(OUTPUT_DIR, f"script_{task_id}.txt")
            with open(script_file_path, "w", encoding="utf-8") as f:
                f.write(req.script)

        # Run pipeline
        main.run_pipeline(
            topic=req.topic,
            script_path=script_file_path,
            language=req.language,
            gender=req.gender,
            voice=req.voice,
            rate=req.rate,
            num_sentences=req.num_sentences,
            clips_dir=CLIPS_DIR,
            out_dir=OUTPUT_DIR,
            font_path=font_path,
            progress_callback=update_progress
        )
        
        # Cleanup temp script
        if script_file_path and os.path.exists(script_file_path):
            os.remove(script_file_path)

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Success! Video ready."
        tasks[task_id]["video_url"] = "/output/final_video.mp4"
        tasks[task_id]["srt_url"] = "/output/final_video.srt"
        
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = f"Error: {str(e)}"
        tasks[task_id]["progress"] = 0

@app.post("/api/generate")
def generate_video(req: GenerateRequest):
    if not req.topic and not req.script:
        raise HTTPException(status_code=400, detail="Either topic or script is required.")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Initializing...",
        "video_url": None,
        "srt_url": None
    }
    
    # Start thread
    thread = threading.Thread(target=run_in_background, args=(task_id, req))
    thread.daemon = True
    thread.start()
    
    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/api/voices")
def get_voices():
    # Return standard list of voice mappings
    import voice_generator
    return voice_generator.INDIAN_VOICES

class PreviewRequest(BaseModel):
    language: str
    gender: str
    voice: Optional[str] = None
    rate: str = "+0%"

PREVIEW_TEXTS = {
    "hi": "नमस्ते, यह आपकी चुनी हुई आवाज़ का पूर्वावलोकन है।",
    "en": "Hello, this is a preview of your selected voice.",
    "mr": "नमस्कार, हा तुमच्या निवडलेल्या आवाजाचा पूर्वदृश्य आहे.",
    "ta": "வணக்கம், இது நீங்கள் தேர்ந்தெடுத்த குரலின் முன்னோட்டம்.",
    "te": "నమస్కారం, ఇది మీరు ఎంచుకున్న వాయిస్ యొక్క ప్రివ్యూ.",
    "bn": "নমস্কার, এটি আপনার নির্বাচিত ভয়েসের একটি পূর্বরূপ।",
}

@app.post("/api/preview-voice")
async def preview_voice(req: PreviewRequest):
    import edge_tts
    import voice_generator
    try:
        voice_name = voice_generator.resolve_voice(req.language, req.gender, req.voice)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    text = PREVIEW_TEXTS.get(req.language, "Hello, this is a preview of your selected voice.")
    
    # Simple cleanup of old preview files
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("preview_") and f.endswith(".mp3"):
            try:
                os.remove(os.path.join(OUTPUT_DIR, f))
            except Exception:
                pass

    preview_filename = f"preview_{uuid.uuid4()}.mp3"
    preview_path = os.path.join(OUTPUT_DIR, preview_filename)
    
    try:
        communicate = edge_tts.Communicate(text, voice_name, rate=req.rate)
        await communicate.save(preview_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice preview failed: {str(e)}")
        
    return {"preview_url": f"/output/{preview_filename}"}

@app.get("/")
def get_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
