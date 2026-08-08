from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import os
import json
import google.generativeai as genai

router = APIRouter()

_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def _get_model():
    """Return a configured Gemini model, or raise a clear error if no key is set."""
    if not _GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Report decoder is not configured. Set GEMINI_API_KEY in the backend environment.",
        )
    genai.configure(api_key=_GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-1.5-flash")


@router.post("/decode-report")
async def decode_report(
    file: UploadFile = File(...),
    language: str = Form("English"),
):
    model = _get_model()
    contents = await file.read()

    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    prompt = f"""
You are a multilingual health literacy assistant.
Analyse this medical report image or document.
Extract all key metrics and lab values, and explain each one in plain language without alarmist phrasing.
Then provide a brief overall summary translated into {language}.

Respond ONLY with valid JSON that exactly matches this schema:
{{
  "findings": [
    {{
      "metric": "...",
      "observed_value": "...",
      "reference_range": "...",
      "status": "Normal|High|Low",
      "plain_meaning": "..."
    }}
  ],
  "translated_summary": "Overall summary in {language}",
  "disclaimer": "This is an AI-generated summary. Please consult your physician for clinical advice."
}}
"""

    image_part = {
        "mime_type": file.content_type or "image/jpeg",
        "data": contents,
    }

    try:
        response = model.generate_content([prompt, image_part])
        text = response.text.strip()

        # Strip markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Model returned invalid JSON: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini analysis failed: {str(e)}")
