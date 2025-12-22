import sqlite3
import discord
import asyncio
import os
import sys
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from youtube_downloader_dlp import get_Song_Info, get_Audio_Source
load_dotenv()
ID = os.getenv('SERVER_ID')
GUILD_ID = discord.Object(id=ID)
FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
class MikuMusicCommands(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        #TODO change to be server specific
        self.song_sources_queue = []
        self.song_names_list = []
        self.loop = False
        super().__init__()
    async def join(self,interaction:discord.Interaction)->None:
        if interaction.guild.voice_client!=None:
            return interaction.guild.voice_client
        if interaction.user.voice != None:
            vc = interaction.user.voice.channel
            await vc.connect()
            return
        else:
            await interaction.followup.send("```Not in a voice chat```")
            return
    async def playNext(self,bot_vc:discord.VoiceProtocol)->discord.InteractionCallbackResponse:
        if self.song_sources_queue:
            if self.loop is False:
                self.song_sources_queue.pop(0)
                self.song_names_list.pop(0)
        if self.song_sources_queue:
            raw = await get_Audio_Source(self.song_sources_queue[0])
            source = discord.FFmpegPCMAudio(source=raw,**FFMPEG_OPTS)
            cur_song = self.song_names_list[0]
            bot_vc.play(source,after=self.after)
            return await self.text_channel.send(f'```Now playing {cur_song}!```')
        return await self.text_channel.send(f'```Queue empty```')
    def after(self,error)->None|str:
        try:
            asyncio.run_coroutine_threadsafe(self.playNext(self.bot_vc), self.bot.loop)
            return 
        except error as e:
            return print(e)
    
    @app_commands.command(name='play',description='Enter song name')
    @app_commands.guilds(GUILD_ID)
    async def play(self, interaction:discord.Interaction,song_name:str)->None:
        await interaction.response.defer(thinking=True)
        await self.join(interaction)
        if interaction.guild.me.voice is None:
            return
        self.bot_vc = interaction.guild.voice_client
        self.text_channel = interaction.channel
        song_title,url = await get_Song_Info(song_name)
        if song_title is None:
            return await interaction.followup.send(f'```Invalid link```')
        self.song_sources_queue.append(url)
        self.song_names_list.append(song_title)
        if self.bot_vc.is_playing():
            await interaction.followup.send(f'Added [{song_title}]({url}) to the queue')
            return 
        if not self.bot_vc.is_playing():
            source = discord.FFmpegOpusAudio(source=await get_Audio_Source(url),**FFMPEG_OPTS)
        try:
            if source == None:
                raise Exception
            self.bot_vc.play(source,after=self.after)
        except Exception as e:
            print(e)
            await interaction.followup.send(f'``Something went wrong try again```')
            return 
        await interaction.followup.send(f'Now playing [{song_title}]({url})!')
        return
    @app_commands.command(name='stop',description='Disconnects bot from voice channel')
    @app_commands.guilds(GUILD_ID)
    async def stop(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        if interaction.guild.me.voice is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        await interaction.guild.voice_client.disconnect()
        self.loop = False
        self.song_names_list = []
        self.song_sources_queue = []
        return await interaction.response.send_message("```Stopping playback...```") 
    @app_commands.command(name='skip',description='Skips current song')
    @app_commands.guilds(GUILD_ID)
    async def skip(self,interaction:discord.Interaction)->None:
        if interaction.guild.me.voice is None:
            await interaction.response.send_message("```Not in a voice channel```")
            return
        self.loop = False
        await interaction.response.send_message(f"```Skipping {self.song_names_list[0]}```")
        interaction.guild.voice_client.stop()
        return 
    @app_commands.command(name='queue',description='Gets song queue')
    @app_commands.guilds(GUILD_ID)
    async def queue(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        if len(self.song_names_list) == 0:
            return await interaction.response.send_message("```Queue empty```")
        queue_str = '```'
        for idx,song in enumerate(self.song_names_list):
            if idx == 0:
                queue_str += '--> ' + song +' <-- Currently playing'+'\n'
            else:
                queue_str += str(idx)+'. ' + song +'\n'
        queue_str += '```'
        return await interaction.response.send_message(queue_str)
    @app_commands.command(name='clear',description='Clears music queue')
    @app_commands.guilds(GUILD_ID)
    async def clear(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        if not interaction.guild.me.voice :
            self.song_names_list=[]
            self.song_sources_queue=[]
            interaction.guild.voice_client.stop()
            return await interaction.response.send_message('```Clearing queue...```')
        else:
            return await interaction.response.send_message("```Not in a voice channel```")    
        
    @app_commands.command(name='play-next',description='Insert song to be played next')
    @app_commands.guilds(GUILD_ID)
    async def queueNext(self,interaction:discord.Interaction,song_name:str)->discord.InteractionCallbackResponse:
        if interaction.guild.me.voice is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        await interaction.response.defer(thinking=True)
        song_title,song_source = await get_Song_Info(song_name)
        if song_title is None:
            return await interaction.followup.send(f"```Unable to find {song_name}```")
        self.song_sources_queue.insert(1,song_source)
        self.song_names_list.insert(1,song_title)
        return await interaction.followup.send(f'Playing [{song_title}]({self.song_sources_queue[1]}) next')
    @app_commands.command(name='loop',description='Loop current song')
    @app_commands.guilds(GUILD_ID)
    async def loopSong(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        if interaction.guild.me.voice is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        if not self.loop: 
            self.loop = True
            return await interaction.response.send_message("```Looping current song```")
        self.loop = False
        return await interaction.response.send_message("```No longer looping current song```")
    @app_commands.command(name='remove',description='Remove song from queue')
    @app_commands.guilds(GUILD_ID)
    async def removeFromQueue(self,interaction:discord.Interaction,index:int)->None:
        try:
            if index == 0:
                raise IndexError
            await interaction.response.send_message(f"```Removing {self.song_names_list[index]} from queue```")
            self.song_names_list.pop(index)
            self.song_sources_queue.pop(index)
        except IndexError:
            await interaction.response.send_message(f'```Not a valid number!```')
        return
    @app_commands.command(name='die',description='Shuts down bot')
    @app_commands.guilds(GUILD_ID)
    async def die(self,interaction:discord.Interaction)->None|discord.InteractionCallbackResponse:
        if interaction.user.id == 325767307114840074:
            await interaction.response.send_message('```Dying....```')
            await self.bot.close()
            sys.exit()
            return
        return await interaction.response.send_message('```Not allowed```')
async def setup(bot:commands.Bot)->None:
    await bot.add_cog(MikuMusicCommands(bot))