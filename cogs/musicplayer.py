import sqlite3
import discord
import asyncio
import os
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from youtube_downloader import downloadYt, getYtTitle
load_dotenv()
ID = os.getenv('SERVER_ID')
GUILD_ID = discord.Object(id=ID)
SONG_NAME = 1
SONG_FILE_PATH = 0
class MikuMusicCommands(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        #TODO change to be server specific
        self.song_sources_queue = []
        self.song_names_list = []
        self.loop = False
        super().__init__()
    def searchSong(self,*,song_name:str = '') -> tuple|None:
        song_name = song_name
        db = sqlite3.connect('BotAudioFiles.db')
        cur = db.cursor()
        table_name = 'AudioFilePaths'
        song_name = '%'+ song_name + '%'
        query = f'SELECT file_path, file_name FROM {table_name} WHERE file_name LIKE :title'
        args = {
                'title' : song_name
                }
        cur.execute(query,args)
        result = cur.fetchall()
        result = None if result == [] else result
        db.close() 
        if result == None:
            return result
        return result[0] 
    #will return only information for one song, cannot return index[0] of None
    def insertSong(self, url: str) -> None:
        db = sqlite3.connect('BotAudioFiles.db')
        cur = db.cursor()
        query = "INSERT INTO AudioFilePaths VALUES(?,?)"
        song_title,song_path = downloadYt(url)
        cur.execute(query, (song_title,song_path))
        db.commit()
        db.close()

    async def join(self,interaction:discord.Interaction)->discord.VoiceProtocol|None:
        if interaction.guild.voice_client!=None:
            return interaction.guild.voice_client
        if interaction.user.voice != None:
            vc = interaction.user.voice.channel
            await vc.connect()
            #await interaction.response.send_message(f"Joining {vc}") for debugging
            return interaction.guild.voice_client
        else:
            await interaction.response.send_message("Not in a voice chat")
            return 
    async def playNext(self,bot_vc:discord.VoiceProtocol)->None:
        print(self.loop)
        if self.song_sources_queue:
            if self.loop is False:
                self.song_sources_queue.pop(0)
                self.song_names_list.pop(0)
        if self.song_sources_queue:
            print(self.song_sources_queue[0],self.song_names_list[0])
            source = discord.FFmpegPCMAudio(source=self.song_sources_queue[0])
            cur_song = self.song_names_list[0]
            bot_vc.play(source,after=self.after)
            return await self.text_channel.send(f'```Now playing {cur_song}```')
        return  await self.text_channel.send(f'```Queue empty```')
    def after(self,error)->None|str:
        try:
            asyncio.run_coroutine_threadsafe(self.playNext(self.bot_vc), self.bot.loop)
            return 
        except TypeError:
            print(error)
    
    @app_commands.command(name='add-url',description='add an youtube link')
    @app_commands.guilds(GUILD_ID)
    async def addURL(self, interaction:discord.Interaction, url:str)->discord.InteractionCallbackResponse:
        title = getYtTitle(url).rstrip() 
        if title == None:
            return await interaction.response.send_message('```Invalid input (must be a youtube link)!```')
        fetched_song = self.searchSong(song_name=title)
        if fetched_song != None:
            if fetched_song[SONG_NAME] == title:
                return await interaction.response.send_message('```Song already added!```')
        self.insertSong(url)
        return await interaction.response.send_message(f'```Added {title}!```')
    @app_commands.command(name='play',description='Enter song name')
    @app_commands.guilds(GUILD_ID)
    async def play(self, interaction:discord.Interaction,song_name:str)->None:
        self.bot_vc = await self.join(interaction)
        self.text_channel = interaction.channel
        if self.bot_vc is None:
            return 
        song_info = self.searchSong(song_name=song_name)
        if song_info is None:
            await interaction.response.send_message(f"```Unable to find {song_name}```")
            return 
        self.song_sources_queue.append(song_info[SONG_FILE_PATH])
        self.song_names_list.append(song_info[SONG_NAME])
        source = discord.FFmpegPCMAudio(source=song_info[SONG_FILE_PATH])
        if self.bot_vc.is_playing():
            await interaction.response.send_message(f'```Added {song_info[SONG_NAME]} to the queue```')
            return 
        self.bot_vc.play(source,after=self.after)
        await interaction.response.send_message(f'```Now playing {song_info[SONG_NAME]}```')
        return
    @app_commands.command(name='stop',description='Disconnects bot from voice channel')
    @app_commands.guilds(GUILD_ID)
    async def stop(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        voice_chat_status = interaction.guild.me.voice
        if voice_chat_status is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        else:
            await interaction.guild.voice_client.disconnect()
            return await interaction.response.send_message("```Stopping playback...```") 
    @app_commands.command(name='skip',description='Skips current song')
    @app_commands.guilds(GUILD_ID)
    async def skip(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        voice_chat_status = interaction.guild.me.voice
        self.loop = False
        if voice_chat_status is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        interaction.guild.voice_client.stop()
        return await interaction.response.send_message(f"```Skipping {self.song_names_list[0]}```")
    @app_commands.command(name='queue',description='Gets song queue')
    @app_commands.guilds(GUILD_ID)
    async def queue(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        queue_str = '```'
        for idx,song in enumerate(self.song_names_list):
            queue_str += str(idx)+'. ' + song +'\n'
        queue_str += '```'
        return await interaction.response.send_message(queue_str)
    @app_commands.command(name='song-db',description='Lists out all the songs added to the local db')
    @app_commands.guilds(GUILD_ID)
    async def getDB(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        db = sqlite3.connect('BotAudioFiles.db')
        cur = db.cursor()
        cur.execute('SELECT * FROM AudioFilePaths')
        files = cur.fetchall()
        files.sort()
        songDB = '```Songs added to db\n'
        for song in files:
            songDB += song[0]+'\n'
        songDB +='```'
        db.close()
        return await interaction.response.send_message(songDB)
    #TODO add another function to check vc status
    @app_commands.command(name='clear',description='Clears music queue')
    @app_commands.guilds(GUILD_ID)
    async def clear(self,interaction:discord.Interaction)->discord.InteractionCallbackResponse:
        self.song_names_list=[]
        self.song_sources_queue=[]
        voice_chat_status = interaction.guild.me.voice
        if voice_chat_status is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        interaction.guild.voice_client.stop()
        return await interaction.response.send_message('```Clearing queue...```')
    @app_commands.command(name='play-next',description='Insert song to be played next')
    @app_commands.guilds(GUILD_ID)
    async def queueNext(self,interaction:discord.Interaction,song_name:str)->discord.InteractionCallbackResponse:
        voice_chat_status = interaction.guild.me.voice
        if voice_chat_status is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        song_info = self.searchSong(song_name=song_name)
        if song_info is None:
            return await interaction.response.send_message(f"```Unable to find {song_name}```")
        self.song_sources_queue.insert(1,song_info[SONG_FILE_PATH])
        self.song_names_list.insert(1,song_info[SONG_NAME])
        return await interaction.response.send_message(f'```Playing {song_info[SONG_NAME]} next```')
    @app_commands.command(name='loop',description='Loop current song')
    @app_commands.guilds(GUILD_ID)
    async def loopSong(self,interaction:discord.Interaction):
        if interaction.guild.me.voice is None:
            return await interaction.response.send_message("```Not in a voice channel```")
        if not self.loop: 
            self.loop = True
            return await interaction.response.send_message("```Looping current song```")
        self.loop = False
        return await interaction.response.send_message("```No longer looping current song```")

async def setup(bot:commands.Bot):
    await bot.add_cog(MikuMusicCommands(bot))

        