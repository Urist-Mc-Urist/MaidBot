#load API key and set intents
import discord, os, io, asyncio
from discord import app_commands
import imagehash
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

import utility.logic as logic
import utility.gpt as gpt

load_dotenv()
api_key = os.getenv('DISCORD_API_KEY')
intents = discord.Intents.default()
intents.message_content = True
permissions_integer = 34816 #from Discord Dev portal

#initialize bot
bot = discord.Client(intents=intents, permissions=discord.Permissions(permissions_integer))
tree = app_commands.CommandTree(bot)

#Declare dictionary with every server ID and number of requests made in the last minute
server_request_counts = {}

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Bot is ready. Connected to {len(bot.guilds)} guild(s).")
    validate_server_post_history_files()

    #initialize server request counts
    for guild in bot.guilds:
      server_request_counts[guild.id] = 0

    bot.loop.create_task(check_for_new_posts())
    bot.loop.create_task(reset_server_request_counts())

#guild join event
@bot.event
async def on_guild_join(guild):
  print(f"INFO: Joined guild {guild.name} with ID {guild.id}, sending introduction message")
  validate_server_post_history_files()
  introduction_message = await bot.loop.run_in_executor(ThreadPoolExecutor(), gpt.introduce_self, guild.name)
  for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            if 'general' in channel.name.lower():
                async with channel.typing():
                  await channel.send(introduction_message)
                  return
            
  #if no general channel, send to first channel
  await guild.channels[0].send(introduction_message)
  print("INFO: Introduction message sent to new server")

#reset server request counts every minute
@bot.event
async def reset_server_request_counts():
  await bot.wait_until_ready()
  while not bot.is_closed():
    print("INFO: Resetting server request counts")
    for server in server_request_counts:
      server_request_counts[server] = 0
    await asyncio.sleep(60)


#check for new posts every 5 minutes
@bot.event
async def check_for_new_posts():

  await bot.wait_until_ready()
  while not bot.is_closed():
    print("INFO: Checking for new posts...")

    try:
      images_and_commentary = await bot.loop.run_in_executor(ThreadPoolExecutor(), logic.generate_messages_from_new_links)
      if images_and_commentary:
        for img, text in images_and_commentary:
          #convert image to bytes to send
          with io.BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            print("INFO: Posting maid")
            for guild in bot.guilds:
              for channel in guild.text_channels:
                if 'maid' in channel.name.lower():
                  await channel.send(content=text, file=discord.File(fp=image_binary, filename='maido.png'))
                  image_binary.seek(0)
                  print("INFO: Posted maid to " + guild.name + " in channel " + channel.name)

          #save image hash to posted_images.txt
          with open("global_posted_images.txt", "a") as f:
            f.write(str(imagehash.average_hash(img)) + "\n")

    except Exception as e:
      print("An exception occured somewhere in check_for_new_posts")
      print(e)
      print("\n")
    await asyncio.sleep(300)

@bot.event
async def on_message(message):

  # Ignore messages sent by the bot itself
  if message.author == bot.user:
    return
  
  # increment request count for the server the message was sent in
  guild_id = message.guild.id
  if bot.user in message.mentions or message.reference:
    if(server_request_counts[guild_id] >= 1 and guild_id != 629539338278928397):
      await message.channel.send("I'm sorry, My master is broke and doesn't want to pay for more API calls. Please wait 60 seconds before trying again.")
      return
    else:
      server_request_counts[guild_id] += 1

  # Check if the bot was mentioned in the message
  if bot.user in message.mentions and not message.reference:
    print(f"Bot was mentioned in message")
    #get text from message
    prompt = message.content
    print(prompt)
    async with message.channel.typing():
      with ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        try:
          response_text = await loop.run_in_executor(executor, gpt.respond_to_message, prompt)
          try:
            await message.channel.send(response_text)
          except Exception as e:
            await message.channel.send("An exception while trying to send the reply. Please tell Master to fix me.\n\n" + str(e))
            return
        except Exception as e:
          await message.channel.send("An exception occured somwhere while generating the reply. Please tell Master to fix me (This may be intermitent).\n\n" + str(e))
          return

  if message.reference:
    print("Bot was replied to")
    # Fetch the original message from the reference
    original_message_obj = await message.channel.fetch_message(message.reference.message_id)
    original_message = str(original_message_obj.content)
    prompt = str(message.content)
    
    # Check if the original message was sent by the bot
    if original_message_obj.author == bot.user:
      async with message.channel.typing():
        with ThreadPoolExecutor() as executor:
          loop = asyncio.get_event_loop()
          try:
            response_text = await loop.run_in_executor(executor, gpt.respond_to_reply, original_message, prompt)
          except Exception as e:
            print(e)
            await message.channel.send("An exception occured somwhere in the code. Please tell Master to fix me (This may be intermittent).\n\n" + str(e))
            return
        await message.channel.send(response_text)

@tree.command(name="post_maid", description="Have Maidbot post a maid with commentary.")
async def post_maid(interaction: discord.Interaction):
    print("INFO: Received post_maid command")
    guild_id = interaction.guild_id
    await interaction.response.defer()

    if(server_request_counts[guild_id] >= 1 and guild_id != 629539338278928397):
      await interaction.edit_original_response(content="I'm sorry, My master is broke and doesn't want to pay for more API calls. Please wait 60 seconds before trying again.")
      return
    else:
      server_request_counts[guild_id] += 1

    try:
      with ThreadPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        img, text = await loop.run_in_executor(executor, logic.post_maid_with_commentary, guild_id)
    except Exception as e:
      print(e)
      await interaction.edit_original_response(content="An exception occured somwhere in the code. Please tell Master to fix me.\n\n" + str(e))
      return
    
    if img == None:
      await interaction.edit_original_response(content=text)
      return
    
    #convert image to bytes to send
    with io.BytesIO() as image_binary:
      img.save(image_binary, 'PNG')  # Save the PIL image to the binary stream
      image_binary.seek(0)  # Reset stream position
      await interaction.edit_original_response(content=text, attachments=[discord.File(fp=image_binary, filename='maido.png')])
      
      #save image hash to this guild's posted_images.txt
      with open(os.path.join("server_post_history", str(guild_id), "posted_images.txt"), "a") as f:
        f.write(str(imagehash.average_hash(img)) + "\n")

def validate_server_post_history_files():
  #check if guild folders exist
  guilds = bot.guilds
  for guild in guilds:
    #check if posted_images.txt exists for the current guild, if not, create it
    if not os.path.isdir(os.path.join("server_post_history", str(guild.id))):
      os.makedirs(os.path.join("server_post_history", str(guild.id)))

    if not os.path.isfile(os.path.join("server_post_history", str(guild.id), "posted_images.txt")):
      with open(os.path.join("server_post_history", str(guild.id), "posted_images.txt"), "w") as f:
        pass
    
    if not os.path.isfile("global_posted_images.txt"):
      with open("global_posted_images.txt", "w") as f:
        pass

    if not os.path.isfile("global_seen_links.txt"):
      with open("global_seen_links.txt", "w") as f:
        pass


bot.run(api_key)