from dataclasses import dataclass
from typing import Optional
from google.cloud import texttospeech

@dataclass
class GoogleSynthesizerConfig:
    language_code: str = "en-US"
    voice_name: str = "en-US-Neural2-I"
    pitch: float = 0.0
    speaking_rate: float = 0.8
    sample_rate_hertz: int = 24000

class GoogleSynthesizer:
    def __init__(self, config: GoogleSynthesizerConfig):
        self.config = config
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code=config.language_code,
            name=config.voice_name,
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=config.sample_rate_hertz,
            speaking_rate=config.speaking_rate,
            pitch=config.pitch,
            effects_profile_id=["telephony-class-application"],
        )

    def synthesize(self, text: str) -> bytes:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=self.voice,
            audio_config=self.audio_config,
        )
        return response.audio_content 