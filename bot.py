import discord
import os
import random
import asyncio
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=OPENAI_KEY)

# bot permission
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.members = True

client = discord.Client(intents=intents)

# keeps track of players and their contestant numbers
player_assignments = {}

# contestant number that belongs to the AI once game starts
ai_contestant_number = None

# tracks who started the game
interrogator_id = None


conversation_log = []

GAME_CHANNEL_ID = 1553515865474076674


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")


@client.event
async def on_message(message):
    # ignore messages sent by the bot
    if message.author == client.user:
        return

    # start the game
    if message.content.startswith("!PlayImitationGame"):
        await start_game(message)
        return

    if message.content.startswith("!Guess"):
        if message.author.id != interrogator_id:
            await message.channel.send("only the interrogator can guess the imposter")
            return

        parts = message.content.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("Usage: `!Guess 3` (guess the Contestant number you think is the AI)")
            return

        guess_number = int(parts[1])
        game_channel = client.get_channel(GAME_CHANNEL_ID)

        if guess_number == ai_contestant_number:
            await game_channel.send(f" Correct!!👏👏 Contestant {guess_number} was AI, therefore the interrogator wins!")
        else:
            await game_channel.send(f" Wrong,womp womp😞. Contestant {guess_number} was human. The AI wins!")

        await end_game(message, reveal=True)
        return

    if message.content.startswith("!EndGame"):
        await end_game(message, reveal=True)
        return

    # send contestan'st dms to the game channel
    if isinstance(message.channel, discord.DMChannel):
        user_id = message.author.id

        if user_id in player_assignments:
            contestant_number = player_assignments[user_id]
            game_channel = client.get_channel(GAME_CHANNEL_ID)

            text = f"**Contestant {contestant_number}:** {message.content}"

            await game_channel.send(text)

            conversation_log.append(
                f"Contestant {contestant_number}: {message.content}"
            )

        else:
            await message.channel.send(
                "You're not currently in a game"
            )

        return

    # check if the interrogator sent something in the game
    if (
        message.channel.id == GAME_CHANNEL_ID
        and message.author.id == interrogator_id
    ):
        conversation_log.append(
            f"Interrogator: {message.content}"
        )

        asyncio.create_task(ai_respond_after_delay())


async def ai_respond_after_delay():
    # delay so the AI doesn't answer instantly common response times 5-8 seconds.Chose 7 seconds
    await asyncio.sleep(7)

    # give the AI the most recent messages
    history_text = "\n".join(conversation_log[-15:])

    prompt = (
        "You are secretly an AI playing a game where you must convincingly pass as a human "
        "texting casually in a discord group chat. "
        f"You are Contestant {ai_contestant_number}. "
        "CRITICAL STYLE RULES:\n"
        "- type like a real person texting fast, dont write essays or be so desscriptive. keep vocabulary terms similar to what other contestants use\n"
        "- most answers should be 1-5 words. Occasionally a short sentence but never more than one\n"
        "- no explanations or reasoning ('because..', 'it reminds me of..') unless directly asked why.\n"
        "- use casual and imperfect language to match other contestant's writing styles, also lowercase is fine. Skip punctuation such as commas and periods NO COMMAS OR PERIODS.\n"
        "- never sound formal and dont be so overly descriptive.\n"
        "- do not say you are an AI, if asked play it off and act like other contestants.\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Reply as Contestant {ai_contestant_number}, matching the writing style of the other contestants above:"
    )

    response = openai_client.chat.completions.create(
        model="gpt-5.6-luna",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    ai_reply = response.choices[0].message.content.strip()

    game_channel = client.get_channel(GAME_CHANNEL_ID)

    await game_channel.send(
        f"**Contestant {ai_contestant_number}:** {ai_reply}"
    )

    conversation_log.append(
        f"Contestant {ai_contestant_number}: {ai_reply}"
    )


async def start_game(message):
    global player_assignments
    global ai_contestant_number
    global interrogator_id
    global conversation_log

    # get the 3 people tagged in the command
    contestants = message.mentions

    if len(contestants) != 3:
        await message.channel.send(
            "You need to tag exactly 3 contestants!If you're the one initiating the game, do not tag yourself. To end the game, type !EndGame "
            "Example: `!PlayImitationGame @Person1 @Person2 @Person3`"
        )
        return

    # randomly assign contestant numbers
    numbers = [1, 2, 3, 4]
    random.shuffle(numbers)

    player_assignments = {}

    for i, person in enumerate(contestants):
        player_assignments[person.id] = numbers[i]

    # last number goes to the AI
    ai_contestant_number = numbers[3]

    interrogator_id = message.author.id
    conversation_log = []

    # tell each player their # privately
    for person in contestants:
        try:
            await person.send(
                f"The game has started! You are **Contestant "
                f"{player_assignments[person.id]}**. "
                f"DM me your responses through here ONLY and I'll post them "
                f"to the game as your contestant number."
            )

        except discord.Forbidden:
            await message.channel.send(
                f"Couldn't DM {person.mention} - they might have DMs disabled."
            )

    game_channel = client.get_channel(GAME_CHANNEL_ID)

    await game_channel.send(
        "**The Imitation Game has begun!**\n"
        "Contestants 1, 2, 3, and 4 are ready. "
        "One of you is pretending to be a human.... "
        f"{message.author.mention} is the interrogator - "
        "have fun finding the imposter!"
    )

async def end_game(message, reveal=True):
    global player_assignments, ai_contestant_number, interrogator_id, conversation_log

    if not player_assignments:
        await message.channel.send("there's no game currently running.")
        return

    game_channel = client.get_channel(GAME_CHANNEL_ID)

    if reveal:
        reveal_lines = []
        for user_id, number in player_assignments.items():
            user = await client.fetch_user(user_id)
            reveal_lines.append(f"Contestant {number} was {user.name} (human)")
        reveal_lines.append(f"Contestant {ai_contestant_number} was the **AI**")
        await game_channel.send("**Game over! here's the reveal:**\n" + "\n".join(reveal_lines))

    player_assignments = {}
    ai_contestant_number = None
    interrogator_id = None
    conversation_log = []

client.run(TOKEN)
