import os


# Characterization tests must never need production credentials or make
# real Discord/OpenAI requests. These values are set before test modules
# import config.py.
os.environ.setdefault("DISCORD_TOKEN", "test-discord-token")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
