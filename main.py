import logging
import sys
import os
from fastapi.logger import logger

from flights.custom_session import CustomSession, CustomSessionService
from google_transcriber import GoogleTranscriber, GoogleTranscriberConfig

# Force stdout to be unbuffered
sys.stdout.reconfigure(line_buffering=True)

# Configure logging with more explicit settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ],
    force=True
)

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Test print statements
print("=== Application Starting (Print) ===")
logger.info("=== Application Starting (Logger) ===")

# FastAPI web app entry point
from datetime import datetime
import json
import asyncio
import base64
from pathlib import Path
import traceback
import uuid

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
from google.genai.types import (
    Part,
    Content,
)

from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, Response
from dotenv import load_dotenv
from flights.agent import root_agent

# Load environment variables
load_dotenv()

from google_synthesizer import GoogleSynthesizer, GoogleSynthesizerConfig


APP_NAME = "Flights Booking Agent"
session_service = CustomSessionService()

load_dotenv(dotenv_path='.env', override=True)

google_transcriber = GoogleTranscriber(GoogleTranscriberConfig(sampling_rate=16000, audio_encoding="LINEAR16", language_code="en-US"))
google_synthesizer = GoogleSynthesizer(GoogleSynthesizerConfig(language_code="en-IN", voice_name="en-IN-Chirp-HD-F", sample_rate_hertz=24000))

class TextHistory:
    def __init__(self, websocket):
        self.text_history = ""
        self.websocket = websocket
        print("TextHistory initialized")  # Debug print

    def add_text(self, text, prefix="", suffix="", is_complete=False, next_text=None):
        print(f"[ADDING TEXT]: {text}, is_complete: {is_complete}")  # Debug print
        logger.info(f"[ADDING TEXT]: {text}, is_complete: {is_complete}")
        if is_complete:
            text = self.get_text() + prefix + text + suffix
            self.text_history = next_text if next_text else ""
            asyncio.create_task(self.synthesize_audio(text))
        else:
            self.text_history += prefix
            self.text_history += text
            self.text_history += suffix

    def add_final_text(self, text):
        print(f"[ADDING FINAL TEXT]: {text}")  # Debug print
        logger.info(f"[ADDING FINAL TEXT]: {text}")
        self.text_history += text
        text = self.get_text()
        self.text_history = ""
        asyncio.create_task(self.synthesize_audio(text))

    def get_text(self):
        return self.text_history
    
    async def synthesize_audio(self, text):
        print(f"[SYNTHESIZING AUDIO]: {text}")  # Debug print
        logger.info(f"[SYNTHESIZING AUDIO]: {text}")
        print(f"[SYNTHESIZING AUDIO]: {datetime.now().isoformat()}")  # Debug print
        audio_content = google_synthesizer.synthesize(text)
        audio_base64 = base64.b64encode(audio_content).decode("utf-8")
        await self.websocket.send_text(json.dumps({
            "audio": audio_base64, 
            "audio_text": text
        }))
        print(f"[SYNTHESIZING AUDIO]: {text} {datetime.now().isoformat()}")  # Debug print

def start_agent_session(session_id: str, user_id: str):
    """Starts an agent session"""

    # Create a Session
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )

    # Create a Runner
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )

    # Set response modality = TEXT
    run_config = RunConfig(response_modalities=["TEXT"], streaming_mode=StreamingMode.SSE)

    # Create a LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    # Start agent session
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    return live_events, live_request_queue, session


text_history = []

def handle_text_and_audio(text, event, websocket):
    """Handles text output, text_history, and audio synthesis, and sends audio to client."""
    global text_history
    text_output = ""
    text_output += "".join(text_history)
    text_history.clear()
    if event.turn_complete:
        text_output += text
    elif text.strip().startswith(","):
        text_output += text.strip()[1:]
    else:
        delimiter = "." if "." in text else ","
        text_output += text.split(delimiter)[0]
        text_output += delimiter
    try:
        delimiter = "." if "." in text else ","
        text_history.append(text.split(delimiter)[1])
    except Exception:
        pass
    audio_content = google_synthesizer.synthesize(text_output)
    audio_base64 = base64.b64encode(audio_content).decode("utf-8")
    return audio_base64

async def agent_to_client_messaging(websocket, live_events):
    """Agent to client communication"""
    text_history = TextHistory(websocket)
    while True:
        async for event in live_events:
            if event.turn_complete:
                await websocket.send_text(json.dumps({"turn_complete": True}))
                logger.info("[TURN COMPLETE]")
            if event.interrupted:
                await websocket.send_text(json.dumps({"interrupted": True}))
                logger.info("[INTERRUPTED]")
            part: Part = (
                event.content and event.content.parts and event.content.parts[0]
            )
            if not part or not event.partial:
                continue
            text = event.content and event.content.parts and event.content.parts[0].text
            if not text:
                continue
            
            await websocket.send_text(json.dumps({"message": text}))
            logger.info(f"[AGENT TO CLIENT]: {text} {datetime.now().isoformat()}")
            if event.turn_complete:
                text_history.add_final_text(text)
            else:
                delimiters = [',', '.', '?']
                last_delimiter = None
                last_delimiter_pos = -1
                
                # Find last occurring delimiter
                for d in delimiters:
                    pos = text.rfind(d)
                    if pos > last_delimiter_pos:
                        last_delimiter_pos = pos
                        last_delimiter = d

                if last_delimiter_pos == -1:
                    # No delimiter found
                    text_history.add_text(text, is_complete=False)
                else:
                    if last_delimiter_pos == 0:
                        # String starts with delimiter
                        text_history.add_text(last_delimiter, is_complete=True, next_text=text[1:])
                    else:
                        # Split at last delimiter
                        current_text = text[:last_delimiter_pos + 1]
                        next_text = text[last_delimiter_pos + 1:]
                        text_history.add_text(current_text, is_complete=True, next_text=next_text)
            # Synthesize audio for the text using ElevenLabsSynthesizer
            # handle_text_and_audio(text, event, websocket)
            


async def client_to_agent_messaging(websocket, live_request_queue, session):
    """Client to agent communication"""
    while True:

        logger.info("Waiting for client to send message")

        data = await websocket.receive_text()
            
        try:
            data_json = json.loads(data)
        except Exception:
            data_json = None
        if data_json and "audio" in data_json.keys():
            logger.info("Received audio from client")
            # Received audio from client, decode and transcribe
            audio_bytes = base64.b64decode(data_json["audio"])
            def audio_gen():
                logger.info("Sending audio to transcriber")
                yield audio_bytes
            # google_transcriber.stream_transcribe(audio_gen())
            for transcription in google_transcriber.stream_transcribe(audio_gen()):
                logger.info(f"[TRANSCRIPTION]: {transcription}")
                if transcription.is_final:
                    text = transcription.message
                    logger.info(f"[TRANSCRIPTION]: {text}")
                    break
            else:
                text = ""
        else:
            if data_json and "passenger_details" in data_json.keys():
                logger.info(f"[PASSENGER DETAILS]: {data_json['passenger_details']}")
                session.state["passenger_details"] = data_json["passenger_details"]
                print("--------------------------passenger details-------------------", session.state["passenger_details"])
                if isinstance(session, CustomSession):
                    session.update_state()
            
            # Fallback: treat as plain text
            text = data if isinstance(data, str) else ""
        if text:
            logger.info(f"[CLIENT TO AGENT]: {text} {datetime.now().isoformat()}")
            content = Content(role="user", parts=[Part.from_text(text=text)])
            live_request_queue.send_content(content=content)
            logger.info(f"[CLIENT TO AGENT]: {text} {datetime.now().isoformat()}")
        await asyncio.sleep(0)


async def disconnect_agent(websocket, session, session_id, user_id):
    """Disconnect agent"""
    try:
        # Wait for end call signal
        await session.wait_for_end_call()
        await websocket.send_text(json.dumps({"end_call": True}))
        session_service.delete_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        await websocket.close()
        logger.info("---------------------Agent disconnected----------------------")
    except Exception as e:
        logger.error(f"Error in disconnect_agent: {e}")
        return

async def show_user_preffered_details(websocket, session):
    """Show user preffered details"""
    try:
        while True:
            # Wait for preference changes
            preferences = await session.wait_for_preference_change()
            print(f"---------------------------------Preferences: {preferences}---------------------------------")
            await websocket.send_text(json.dumps(preferences))
    except Exception as e:
        logger.error(f"Error in show_user_preffered_details: {e}")
        return

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return FileResponse('index.html')

@app.get("/config.js")
async def get_config():
    config = {
        "HOST_URL": os.getenv("HOST_URL", "http://127.0.0.1:8000/")
    }
    return Response(
        content=f"const config = {json.dumps(config, indent=2)};",
        media_type="application/javascript"
    )

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Client websocket endpoint"""
    # Wait for client connection
    await websocket.accept()
    logger.info(f"Client #{session_id} connected")

    # Start agent session
    session_id = str(session_id)
    live_events, live_request_queue, session = start_agent_session(session_id=session_id, user_id=session_id)

    session.state["token"] = session_id
    session.update_state()

    # Start tasks
    agent_to_client_task = asyncio.create_task(agent_to_client_messaging(websocket, live_events))
    
    client_to_agent_task = asyncio.create_task(client_to_agent_messaging(websocket, live_request_queue, session))

    disconnect_agent_task = asyncio.create_task(disconnect_agent(websocket, session, session_id, session_id))

    show_user_preffered_details_task = asyncio.create_task(show_user_preffered_details(websocket, session))


    await asyncio.gather(agent_to_client_task, client_to_agent_task, disconnect_agent_task, show_user_preffered_details_task)

    # Disconnected
    logger.info(f"Client #{session_id} disconnected")
