import base64
from anthropic import Anthropic
from dotenv import load_dotenv

# Load the API key from .env
load_dotenv()

# Point at the test image
IMAGE_PATH = "test_images/vitabiotics_ultrairon.jpg"

# Read the image file and encode it as base64 (how the API expects images)
with open(IMAGE_PATH, "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")

# Create the client (it picks up ANTHROPIC_API_KEY from the environment)
client = Anthropic()

# Ask Claude to read the label
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "Read this supplement label. List exactly what is printed: the product name, each active ingredient with its dose, the form (tablet, capsule, sachet, etc.), and the directions for use. Record only what is visible. Do not add advice, warnings, or commentary.",
                },
            ],
        }
    ],
)

# Print what Claude read back
print(message.content[0].text)
