from dotenv import load_dotenv
import anthropic

# Read .env and make ANTHROPIC_API_KEY available to this script
load_dotenv()

# The client automatically picks up the key from ANTHROPIC_API_KEY
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-haiku-5-5",
    max_tokens=200,
    messages=[
        {"role": "user", "content": "In two sentences: what is the AEX index?"}
    ],
)

print(response.content[0].text)
print(f"Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
cost = response.usage.input_tokens * 0.10 / 1e6 + response.usage.output_tokens * 0.50 / 1e6
print(f"Cost: ${cost:.6f}")