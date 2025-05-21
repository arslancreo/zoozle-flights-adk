import queue
from dataclasses import dataclass
from typing import Optional, Generator

from google.cloud import speech

@dataclass
class GoogleTranscriberConfig:
    sampling_rate: int = 16000
    language_code: str = "en-US"
    audio_encoding: str = "MULAW"  # or "MULAW"
    model: Optional[str] = None

@dataclass
class Transcription:
    message: str
    confidence: float
    is_final: bool

class GoogleTranscriber:
    def __init__(self, config: GoogleTranscriberConfig):
        self.config = config
        self.client = speech.SpeechClient()
        self.streaming_config = speech.StreamingRecognitionConfig(
            config=speech.RecognitionConfig(
                encoding=getattr(speech.RecognitionConfig.AudioEncoding, config.audio_encoding),
                sample_rate_hertz=config.sampling_rate,
                language_code=config.language_code,
                model=config.model if config.model else None,
                use_enhanced=True if config.model else False,
            ),
            interim_results=True,
        )

    def stream_transcribe(self, audio_generator: Generator[bytes, None, None]):

        client = speech.SpeechClient()

        requests = (
            speech.StreamingRecognizeRequest(audio_content=chunk) for chunk in audio_generator
        )

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-IN",
        )

        streaming_config = speech.StreamingRecognitionConfig(config=config)

        # streaming_recognize returns a generator.
        responses = client.streaming_recognize(
            config=streaming_config,
            requests=requests,
        )

        for response in responses:
            # Once the transcription has settled, the first result will contain the
            # is_final result. The other results will be for subsequent portions of
            # the audio.
            for result in response.results:
                print(f"Finished: {result.is_final}")
                print(f"Stability: {result.stability}")
                alternatives = result.alternatives
                # The alternatives are ordered from most likely to least.
                for alternative in alternatives:
                    print(f"Confidence: {alternative.confidence}")
                    print(f"Transcript: {alternative.transcript}")
                    yield Transcription(
                        message=alternative.transcript,
                        confidence=alternative.confidence,
                        is_final=result.is_final,
                    )
        # print("Streaming transcribe")
        # requests = (speech.StreamingRecognizeRequest(audio_content=chunk) for chunk in audio_generator)
        # try:
        #     responses = self.client.streaming_recognize(self.streaming_config, requests)
        #     for response in responses:
        #         print(f"[RESPONSE]: {response}")
        #         if not response.results:
        #             continue
        #         result = response.results[0]
        #         if not result.alternatives:
        #             continue
        #         top_choice = result.alternatives[0]
        #         yield Transcription(
        #             message=top_choice.transcript,
        #             confidence=top_choice.confidence,
        #             is_final=result.is_final,
        #         )
        # except Exception as e:
        #     print("Streaming transcribe error", str(e))
        #     raise e


