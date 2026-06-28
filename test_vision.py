import base64
import json
from anthropic import Anthropic
from dotenv import load_dotenv

# Load the API key from .env
load_dotenv()

# Point at the test image
IMAGE_PATH = "test_images/sisterly_theelevator.jpg"

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
                    "text": """Read this supplement label and return ONLY a JSON object, with no other text, no markdown, and no code fences. Use exactly this structure: {"product_name": string, "form": string, "directions": string, "ingredients": [{"name": string, "amount": string, "unit": string}]}. Record only what is visible on the label. If a field is not present, use an empty string. Do not add advice, warnings, or commentary.""",
                },
            ],
        }
    ],
)

# Get the raw text Claude returned
raw_text = message.content[0].text

# Parse the JSON text into a real Python dictionary
data = json.loads(raw_text)

# Now Python understands it as data — let's prove it by reaching into the pieces
print("PRODUCT:", data["product_name"])
print("FORM:", data["form"])
print("DIRECTIONS:", data["directions"])
print()
print("INGREDIENTS:")
for item in data["ingredients"]:
    print("  -", item["name"], "|", item["amount"], item["unit"])

# --- Save this entry to a log file so it persists ---

LOG_FILE = "log.json"

# Try to load any existing log; if there's none yet, start an empty list
try:
    with open(LOG_FILE, "r") as f:
        log = json.load(f)
except FileNotFoundError:
    log = []

# Add this supplement to the log
log.append(data)

# Write the whole log back to the file
with open(LOG_FILE, "w") as f:
    json.dump(log, f, indent=2)

print()
print(f"Saved! The log now contains {len(log)} entry/entries.")
