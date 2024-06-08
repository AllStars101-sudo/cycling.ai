# from openai import OpenAI
# client = OpenAI(api_key="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")

# response = client.images.generate(
#   model="dall-e-2",
#   prompt="Sydney Opera House",
#   size="512x512",
#   n=1,
# )

# image_url = response.data[0].url
# print(image_url)

"""
Install the Google AI Python SDK

$ pip install google-generativeai

See the getting started guide for more information:
https://ai.google.dev/gemini-api/docs/get-started/python
"""

from os import environ as env

import google.generativeai as genai

genai.configure(api_key=env.get("GEMINI_API_KEY"))

# Create the model
# See https://ai.google.dev/api/python/google/generativeai/GenerativeModel
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
  # safety_settings = Adjust safety settings
  # See https://ai.google.dev/gemini-api/docs/safety-settings
)
response_text = model.generate_content("hi")
print(response_text)