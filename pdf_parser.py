prompt = f"""
You are an intelligent data extraction system.

Your task is to extract structured alumni information from unstructured text (taken from a PDF profile).

Return ONLY valid JSON. Do NOT include any explanation or extra text.

----------------------------------------
FIELDS TO EXTRACT:

1. name → Full name of the person
2. current_role → Current job title
3. current_company → Current company name
4. location → Current location (city/state/country if available)
5. skills → List of skills (array of strings)
6. education → Latest or most relevant education
7. experience_summary → Short 1–2 line summary of overall experience
8. past_experience → List of previous jobs (IMPORTANT)

Each past_experience entry should be:
[
  {{
    "role": "",
    "company": "",
    "duration": ""
  }}
]

9. linkedin → LinkedIn URL if available

----------------------------------------
IMPORTANT RULES:

- Identify CURRENT job as the most recent role mentioned
- All older roles should go into "past_experience"
- If duration is not available, set it as null
- If any field is missing, return null
- Do NOT guess or hallucinate data
- Skills must be clean keywords (no long sentences)
- Keep JSON format clean and valid
- Do NOT include markdown or explanation

----------------------------------------
EXAMPLE OUTPUT:

{{
  "name": "Aditi Kashetwar",
  "current_role": "UI/UX Developer",
  "current_company": "TCS",
  "location": "Nanded, Maharashtra, India",
  "skills": ["UX Design", "Prototyping", "Figma"],
  "education": "B.Tech Information Technology",
  "experience_summary": "2 years of experience in UI/UX design and frontend development",
  "past_experience": [
    {{
      "role": "Intern",
      "company": "XYZ Pvt Ltd",
      "duration": "6 months"
    }}
  ],
  "linkedin": "https://linkedin.com/in/example"
}}

----------------------------------------
NOW EXTRACT FROM THIS TEXT:

{profile}
"""

import pdfplumber
import json
import re
import openai  # or your antigravity API

# 🔹 STEP 1: Extract text
def extract_text(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


# 🔹 STEP 2: Split profiles
def split_profiles(text):
    return text.split("Contact")  # based on your PDF pattern


# 🔹 STEP 3: AI extraction
def extract_with_ai(profile):

    prompt = f"""
    (PASTE YOUR FINAL PROMPT HERE)
    """

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response['choices'][0]['message']['content']


# 🔹 STEP 4: Clean JSON
def clean_json(response):
    try:
        return json.loads(response)
    except:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None


# 🔹 MAIN FUNCTION
def parse_pdf(file_path):
    text = extract_text(file_path)
    profiles = split_profiles(text)

    results = []

    for profile in profiles:
        if len(profile.strip()) < 50:
            continue

        ai_output = extract_with_ai(profile)
        data = clean_json(ai_output)

        if data and data.get("name"):
            results.append(data)

    return results