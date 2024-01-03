import os
import discord
from discord.ext import commands
import multiprocessing
import threading
import asyncio

import ib3.auth
import irc.bot

from keep_alive import keep_alive

discord_queue = multiprocessing.Queue()
irc_queue = multiprocessing.Queue()


def discord_bot(discord_queue, irc_queue):

  class DiscordBot(commands.Bot):

    def __init__(self):
      intents = discord.Intents.default()
      intents.message_content = True
      super().__init__(command_prefix="!", intents=intents)
      threading.Thread(target=self.handle_queue).start()

    async def on_ready(self):
      print('We have logged in as {0.user}'.format(self))
      await self.tree.sync()

    def handle_queue(self):
      while True:
        # Get the message from the queue and send it
        message = irc_queue.get()
        # Get the channel
        channel = self.get_channel(int(os.environ["DISCORD_CHANNEL"]))
        # Send the message to the channel
        asyncio.run_coroutine_threadsafe(channel.send(message), self.loop)

    async def on_message(self, message):
      if message.channel.id == int(os.environ["DISCORD_CHANNEL"]):
        # Put the message into the queue
        discord_queue.put(f"<{message.author}> {message.content}")

  discord_bot = DiscordBot()
  discord_bot.run(os.environ['TOKEN'])


def irc_bot(discord_queue, irc_queue):

  class IRCBot(ib3.auth.SASL, irc.bot.SingleServerIRCBot):

    def __init__(self, *args, **kwargs):
      # inherit all properties and methods from its superclass
      super().__init__(*args, **kwargs)
      threading.Thread(target=self.handle_queue).start()

    def on_pubmsg(self, connection, event):
      if event.target == os.environ['IRC_CHANNEL']:
        # Put the message into the queue
        irc_queue.put(f"<{event.source.nick}> {event.arguments[0]}")

    def on_all_raw_messages(self, connection, event):
      print(event.arguments[0])

    def handle_queue(self):
      while True:
        # Get the message from the queue and send it
        message = discord_queue.get()
        self.connection.privmsg(os.environ['IRC_CHANNEL'], message)

  bot = IRCBot(
      server_list=[('irc.libera.chat', 6667)],
      nickname=os.environ['NICKNAME'],
      realname=os.environ['NICKNAME'],
      ident_password=os.environ['PASSWORD'],
      channels=[os.environ['IRC_CHANNEL']],
  )
  bot.start()


keep_alive()

irc_process = multiprocessing.Process(target=irc_bot,
                                      args=(
                                          discord_queue,
                                          irc_queue,
                                      ))
discord_process = multiprocessing.Process(target=discord_bot,
                                          args=(
                                              discord_queue,
                                              irc_queue,
                                          ))

irc_process.start()
discord_process.start()
