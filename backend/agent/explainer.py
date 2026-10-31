"""Multilingual Plain-Language Explainer Agent for Jan Aawaz.

Generates accessible, empathetic explanations for citizens in 8 Indian languages:
English, Hindi, Tamil, Malayalam, Telugu, Kannada, Bengali, and Marathi.
Covers:
1. What was found / logged
2. What happens next (department dispatch and inspection)
3. Deadline / SLA (and target resolution timeframe)
4. Safety advice for citizens in the vicinity
5. How to escalate if delayed or unsatisfied
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

logger = logging.getLogger("janaawaz.agent.explainer")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "ml": "Malayalam (മലയാളം)",
    "te": "Telugu (తెలుగు)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "bn": "Bengali (বাংলা)",
    "mr": "Marathi (मराठी)",
}


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Explainer agent could not init Gemini: {e}")
        return None


def _get_models() -> List[str]:
    raw = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_fallback_explanation(report_data: Dict[str, Any], lang: str) -> str:
    """Deterministic fallback explanation when Gemini is unavailable."""
    title = report_data.get("title", "Reported Incident")
    dept = report_data.get("routed_to") or report_data.get("suggested_department") or "Public Works Department"
    sla = report_data.get("sla_hours", 72)
    safety = report_data.get("safety_precautions") or "Please maintain a safe distance and alert pedestrians."
    docket = f"JA-2026-{str(report_data.get('id', ''))[:8].upper()}"

    if lang == "hi":
        return (
            f"नमस्ते। आपके द्वारा दर्ज की गई समस्या '{title}' (डॉकेट: {docket}) की समीक्षा कर ली गई है। "
            f"1. स्थिति: इस समस्या को {dept} को अग्रेषित कर दिया गया है। "
            f"2. आगामी कदम: संबंधित नगर निगम टीम द्वारा स्थल निरीक्षण और तकनीकी कार्य आदेश जारी किया जा रहा है। "
            f"3. समाधान समय-सीमा: आधिकारिक नागरिक सेवा मानक (SLA) के अनुसार इसे {sla} घंटों के भीतर ठीक करने का लक्ष्य है। "
            f"4. सुरक्षा परामर्श: {safety} "
            f"5. समाधान में देरी होने पर: यदि समय-सीमा के भीतर कार्य पूरा नहीं होता है, तो सिस्टम स्वतः इसे उच्च अधिकारियों (विभागाध्यक्ष एवं नगर आयुक्त) को एस्केलेट करता है।"
        )
    elif lang == "ta":
        return (
            f"வணக்கம். நீங்கள் பதிவு செய்த புகார் '{title}' (டாக்கெட்: {docket}) பரிசீலிக்கப்பட்டது. "
            f"1. நிலைமை: இப்பிரச்சினை {dept} துறைக்கு அனுப்பப்பட்டுள்ளது. "
            f"2. அடுத்த கட்ட நடவடிக்கை: களப்பணியாளர்கள் ஆய்வு செய்து பழுதுபார்க்கும் பணியை மேற்கொள்வர். "
            f"3. கால வரம்பு: நகராட்சி விதிமுறைப்படி {sla} மணி நேரத்திற்குள் தீர்க்க திட்டமிடப்பட்டுள்ளது. "
            f"4. பாதுகாப்பு அறிவுரை: {safety} "
            f"5. தீர்வு கிடைக்கவில்லை என்றால்: காலக்கெடுவுக்குள் பணி முடியவில்லை எனில் துறைத் தலைமை அதிகாரிகளுக்கு தானாகவே எஸ்கலேட் செய்யப்படும்."
        )
    elif lang == "te":
        return (
            f"నమస్కారం. మీరు నమోదు చేసిన సమస్య '{title}' (డాకెట్: {docket}) పరిశీలించబడింది. "
            f"1. స్థితి: ఈ సమస్య {dept} విభాగానికి బదిలీ చేయబడింది. "
            f"2. తదుపరి చర్య: మున్సిపల్ బృందం స్థలాన్ని పరిశీలించి మరమ్మతు పనులను ప్రారంభిస్తుంది. "
            f"3. గడువు: అధికారిక సేవా నిబంధనల ప్రకారం {sla} గంటలలోపు పరిష్కరించబడుతుంది. "
            f"4. భద్రతా సూచన: {safety} "
            f"5. ఆలస్యమైతే: గడువు ముగిసినా పని పూర్తి కాకపోతే, వ్యవస్థ స్వయంచాలకంగా ఉన్నతాధికారులకు ఎస్కలేట్ చేస్తుంది."
        )
    elif lang == "bn":
        return (
            f"নমস্কার। আপনার দায়ের করা অভিযোগ '{title}' (ডকেট: {docket}) গ্রহণ করা হয়েছে। "
            f"1. বর্তমান স্থিতি: এটি সংশ্লিষ্ট {dept} দপ্তরে প্রেরণ করা হয়েছে। "
            f"2. পরবর্তী পদক্ষেপ: ইঞ্জিনিয়ারিং টিম ঘটনাস্থল পরিদর্শন করে মেরামতের কাজ শুরু করবে। "
            f"3. সময়সীমা: পৌরসেবা নিয়ম অনুসারে আগামী {sla} ঘণ্টার মধ্যে সমাধানের লক্ষ্য নির্ধারণ করা হয়েছে। "
            f"4. নিরাপত্তা পরামর্শ: {safety} "
            f"5. কাজ বিলম্বিত হলে: নির্ধারিত সময়সীমার মধ্যে সমাধান না হলে সিস্টেম স্বয়ংক্রিয়ভাবে বিভাগীয় প্রধানদের কাছে এটি এস্কেলেট করবে।"
        )
    elif lang == "mr":
        return (
            f"नमस्कार. आपण नोंदवलेली तक्रार '{title}' (डॉकेट: {docket}) तपासली गेली आहे. "
            f"1. स्थिती: ही तक्रार {dept} विभागाकडे सोपवण्यात आली आहे. "
            f"2. पुढील पाऊल: संबंधित पथक प्रत्यक्ष जागेची पाहणी करून दुरुस्तीचे काम हाती घेईल. "
            f"3. मुदत: महापालिकेच्या नागरिक सनदेनुसार {sla} तासांच्या आत काम पूर्ण करण्याचे उद्दिष्ट आहे. "
            f"4. सुरक्षिततेची खबरदारी: {safety} "
            f"5. तक्रार निवारणात विलंब झाल्यास: मुदतीनंतर काम न झाल्यास प्रणाली स्वतःहून विभागप्रमुख आणि आयुक्तांकडे तक्रार वर्ग करते."
        )
    elif lang == "kn":
        return (
            f"ನಮಸ್ಕಾರ. ನೀವು ದಾಖಲಿಸಿದ ಸಮಸ್ಯೆ '{title}' (ಡಾಕೆಟ್: {docket}) ಪರಿಶೀಲಿಸಲಾಗಿದೆ. "
            f"1. ಸ್ಥಿತಿ: ಇದನ್ನು {dept} ಇಲಾಖೆಗೆ ವರ್ಗಾಯಿಸಲಾಗಿದೆ. "
            f"2. ಮುಂದಿನ ಕ್ರಮ: ಅಧಿಕಾರಿಗಳ ತಂಡವು ಸ್ಥಳ ಪರಿಶೀಲನೆ ನಡೆಸಿ ದುರಸ್ತಿ ಕಾರ್ಯ ಕೈಗೊಳ್ಳಲಿದೆ. "
            f"3. ಕಾಲಮಿತಿ: ನಿಯಮಾನುಸಾರ {sla} ಗಂಟೆಗಳ ಒಳಗೆ ಪರಿಹರಿಸುವ ಗುರಿ ಹೊಂದಲಾಗಿದೆ. "
            f"4. ಸುರಕ್ಷತಾ ಸಲಹೆ: {safety} "
            f"5. ವಿಳಂಬವಾದರೆ: ಗಡುವಿನೊಳಗೆ ಪರಿಹಾರ ದೊರೆಯದಿದ್ದರೆ ವ್ಯವಸ್ಥೆಯು ಸ್ವಯಂಚಾಲಿತವಾಗಿ ಮೇಲಧಿಕಾರಿಗಳಿಗೆ ದೂರು ರವಾನಿಸುತ್ತದೆ."
        )
    elif lang == "ml":
        return (
            f"നമസ്കാരം. താങ്കൾ രജിസ്റ്റർ ചെയ്ത പരാതി '{title}' (ഡോക്കറ്റ്: {docket}) പരിശോധിച്ചു. "
            f"1. സ്ഥിതി: ഇത് {dept} വകുപ്പിലേക്ക് കൈമാറിയിട്ടുണ്ട്. "
            f"2. അടുത്ത നടപടി: ഉദ്യോഗസ്ഥർ സ്ഥലം സന്ദർശിച്ച് പരിഹാര നടപടികൾ സ്വീകരിക്കും. "
            f"3. സമയപരിധി: നഗരസഭാ ചട്ടപ്രകാരം {sla} മണിക്കൂറിനുള്ളിൽ പരിഹരിക്കാൻ ലക്ഷ്യമിടുന്നു. "
            f"4. സുരക്ഷാ നിർദ്ദേശം: {safety} "
            f"5. നടപടി വൈകിയാൽ: സമയപരിധിക്കുള്ളിൽ പൂർത്തിയായില്ലെങ്കിൽ സിസ്റ്റം തനിയെ ഉന്നത ഉദ്യോഗസ്ഥർക്ക് കൈമാറും."
        )
    else:
        # Default English
        return (
            f"Hello. Your grievance regarding '{title}' (Docket: {docket}) has been logged and triaged. "
            f"1. What was found: A civic infrastructure issue categorized under '{report_data.get('category', 'civic fault')}' was identified with severity '{report_data.get('severity', 'medium')}'. "
            f"2. What happens next: The incident has been dispatched to {dept}. An engineering inspection team will be assigned to execute on-site remediation. "
            f"3. Target Deadline: Under standard civic resolution SLA guidelines, the resolution turnaround is {sla} hours. "
            f"4. Safety Advice: {safety} "
            f"5. Escalation: If unresolved by the target deadline, our autonomous watchdog will automatically escalate this docket to the Department Head and Municipal Commissioner."
        )


async def generate_plain_language_explanation(report_data: Dict[str, Any], lang: str) -> str:
    """Generate an accessible citizen explanation in the target language using Gemini."""
    lang_name = SUPPORTED_LANGUAGES.get(lang, "English")
    client = _get_client()

    if not client:
        return _build_fallback_explanation(report_data, lang)

    docket = f"JA-2026-{str(report_data.get('id', ''))[:8].upper()}"
    title = report_data.get("title", "Civic Incident")
    description = report_data.get("description", "")
    category = report_data.get("category", "General")
    severity = report_data.get("severity", "medium")
    sla = report_data.get("sla_hours", 72)
    dept = report_data.get("routed_to") or report_data.get("suggested_department") or "Public Works Department"
    locality = report_data.get("locality") or report_data.get("location") or "Reported Location"
    safety = report_data.get("safety_precautions") or "Exercise caution around the area."
    action = report_data.get("action_plan") or "Departmental inspection and repair order."
    status = report_data.get("status", "open")

    system_instruction = (
        "You are an empathetic, clear, citizen-first civic communication assistant for Jan Aawaz. "
        "Your task is to write a plain-language explanation of a civic grievance for ordinary residents. "
        "Write completely and naturally in the requested language. Do NOT use confusing legalistic jargon. "
        "Clearly cover these 5 core questions in friendly, numbered or cleanly structured paragraphs:\n"
        "1. What was found / logged (plain explanation of the problem, severity, and location)\n"
        "2. What happens next (which department was notified, how repairs proceed)\n"
        "3. Target deadline / SLA (the target hours to resolve)\n"
        "4. Safety advice (practical precautions for residents and commuters right now)\n"
        "5. How to escalate (how the autonomous SLA watchdog escalates if the deadline is breached, and how residents can track/dispute)."
    )

    prompt = f"""Target Language: {lang_name} ({lang})
Docket Number: {docket}
Issue Title: {title}
Category: {category}
Current Status: {status}
Assessed Severity: {severity}
Assigned Department: {dept}
Location / Locality: {locality}
Target SLA Window: {sla} hours
Identified Safety Advice: {safety}
Department Action Plan: {action}
Resident Description: {description}

Write the citizen explanation in natural, fluent {lang_name}. Keep it reassuring, direct, and actionable."""

    models = _get_models()
    for model_name in models:
        try:
            # External call timeout <= 5.8s
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.3,
                        max_output_tokens=700,
                    ),
                ),
                timeout=5.8,
            )
            if response and response.text and len(response.text.strip()) > 40:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini explainer model {model_name} failed: {e}")
            continue

    return _build_fallback_explanation(report_data, lang)
