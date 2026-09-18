"""Text to Speech route supporting Gemini TTS and Groq Speech APIs."""
import os
import io
import struct
import logging
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    provider: Optional[str] = "gemini"
    voice: Optional[str] = None
    style: Optional[str] = None


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
    """Pack 16-bit linear PCM into a standard RIFF WAV container."""
    byte_rate = sample_rate * channels * 2
    block_align = channels * 2
    data_size = len(pcm_data)
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        16,  # bits per sample
        b"data",
        data_size,
    )
    return header + pcm_data


@router.get("/voices")
async def get_tts_voices():
    """Return available voices and provider availability."""
    return {
        "providers": {
            "gemini": {
                "name": "Gemini Natural TTS",
                "model": "gemini-2.5-flash-preview-tts",
                "available": bool(os.getenv("GEMINI_API_KEY")),
                "defaultVoice": "Kore",
                "voices": [
                    {"id": "Kore", "name": "Kore", "gender": "Female", "description": "Warm, natural & conversational"},
                    {"id": "Puck", "name": "Puck", "gender": "Male", "description": "Clear, balanced neutral tone"},
                    {"id": "Charon", "name": "Charon", "gender": "Male", "description": "Deep, calm authoritative baritone"},
                    {"id": "Fenrir", "name": "Fenrir", "gender": "Male", "description": "Crisp, confident race analyst"},
                    {"id": "Zephyr", "name": "Zephyr", "gender": "Female", "description": "Bright, energetic & upbeat"},
                ],
            },
            "groq": {
                "name": "Groq Orpheus Speech",
                "model": "canopylabs/orpheus-v1-english",
                "available": bool(os.getenv("GROQ_API_KEY")),
                "defaultVoice": "autumn",
                "styles": ["cheerful", "dramatic", "whisper", "calm", "urgent"],
                "voices": [
                    {"id": "autumn", "name": "Autumn", "gender": "Female", "description": "Conversational track narrator"},
                    {"id": "diana", "name": "Diana", "gender": "Female", "description": "Crisp, articulate announcer"},
                    {"id": "hannah", "name": "Hannah", "gender": "Female", "description": "Warm, engaging broadcast host"},
                    {"id": "austin", "name": "Austin", "gender": "Male", "description": "Dynamic, modern trackside radio"},
                    {"id": "daniel", "name": "Daniel", "gender": "Male", "description": "Smooth, polished commentator"},
                    {"id": "troy", "name": "Troy", "gender": "Male", "description": "Authoritative turf analyst"},
                ],
            },
        }
    }


@router.post("")
async def convert_text_to_speech(req: TTSRequest):
    """Convert text to speech using Gemini or Groq TTS."""
    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    provider = (req.provider or "gemini").lower()
    voice = req.voice

    # Handle Groq TTS
    if provider == "groq":
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if not groq_key:
            # Fallback to Gemini if no Groq key
            provider = "gemini"
        else:
            voice_name = voice if voice in ["autumn", "diana", "hannah", "austin", "daniel", "troy"] else "autumn"
            formatted_text = clean_text
            if req.style and not formatted_text.startswith("["):
                formatted_text = f"[{req.style}] {formatted_text}"

            # Truncate / chunk to 190 characters
            input_text = formatted_text[:190]
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/audio/speech",
                        headers={
                            "Authorization": f"Bearer {groq_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "canopylabs/orpheus-v1-english",
                            "input": input_text,
                            "voice": voice_name,
                            "response_format": "wav",
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(f"Groq TTS failed: {resp.status_code} {resp.text}, falling back to Gemini")
                        provider = "gemini"
                    else:
                        return Response(
                            content=resp.content,
                            media_type="audio/wav",
                            headers={
                                "X-TTS-Provider": "groq",
                                "X-TTS-Voice": voice_name,
                            },
                        )
            except Exception as e:
                logger.error(f"Groq TTS exception: {e}, falling back to Gemini")
                provider = "gemini"

    # Gemini TTS
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    voice_name = voice if voice in ["Kore", "Puck", "Charon", "Fenrir", "Zephyr"] else "Kore"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": clean_text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers={"User-Agent": "aistudio-build"})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=f"Gemini TTS error: {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise HTTPException(status_code=500, detail="No candidates returned from Gemini TTS.")

            parts = candidates[0].get("content", {}).get("parts", [])
            b64_audio = None
            for part in parts:
                if "inlineData" in part and "data" in part["inlineData"]:
                    b64_audio = part["inlineData"]["data"]
                    break

            if not b64_audio:
                raise HTTPException(status_code=500, detail="No audio inlineData in Gemini response.")

            import base64
            pcm_bytes = base64.b64decode(b64_audio)
            wav_bytes = pcm_to_wav(pcm_bytes, sample_rate=24000, channels=1)

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-TTS-Provider": "gemini",
                    "X-TTS-Voice": voice_name,
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Gemini TTS synthesis failed")
        raise HTTPException(status_code=500, detail=str(e))
