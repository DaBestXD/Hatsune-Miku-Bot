import logging
import asyncio
import time
import io
from discord.ext import commands
from audio_utils.audio_class import Song
from audio_utils.bot_audio_functions import build_audio
from audio_utils.audio_handler import get_Audio_Source
from botextras.bot_funcs_ext import txt_only_embed
from discord import PCMVolumeTransformer, VoiceClient, TextChannel
from botextras.constants import GP_DEBUG_VALUES

class GuildPlaybackState():
    def __init__(self, guild_id: int):
        self.logger = logging.getLogger(__class__.__name__)
        self.guild_id: int = guild_id
        self.song_cache: dict[str,str] = {}
        self.songs_list: list[Song] = []
        self.song_loop: bool = False
        self.source: PCMVolumeTransformer|None = None
        self.vc: VoiceClient|None = None
        self.volume: float = 1.00
        self.text_channel: TextChannel|None = None
        self.cache_task: asyncio.Task|None = None
        self.start_time: float|None = None
        self.seek_time: float|None = None
        self.song_mods: str = ""
        self.mod_mid_song: bool = False
        self.nightcore: bool = False

    def class_info(self)->list[str]:
        body_text: list[str] = ["```"]
        for k,v in self.__dict__.items():
            if k in GP_DEBUG_VALUES:
                if isinstance(v, list) or isinstance(v, dict):
                    v = f"Length: {len(v)}"
                body_text.append(f"{k} : {v}")
        body_text.append("```")
        return body_text
    def start_timer(self):
        self.start_time = time.monotonic() if not self.start_time else self.start_time
    def end_timer(self):
        self.start_time = None

    async def cleanup_cache(self, song: Song) -> None:
        # sleep for song duration * 1.5
        await asyncio.sleep(song.duration * 1.5)
        if song.webpage_url in self.song_cache:
            self.logger.info("Removed %s from cache", song.webpage_url)
            self.song_cache.pop(song.webpage_url)
        return None

    async def cache_songs(self, song: Song|None = None, audio_source: str|None = None, cache_limit: int = 5) -> None:
        try:
            if song and audio_source:
                self.song_cache[song.webpage_url] = audio_source
            if len(self.songs_list) > 1:
                for idx, _ in enumerate(self.songs_list[:cache_limit]):
                    if not await self.cache_index(idx):
                        continue
                    await asyncio.sleep(self.songs_list[idx].duration)
            elif len(self.songs_list) == 1:
                await self.cache_index(0)
            return None
        except asyncio.CancelledError:
            return None

    async def cache_index(self, idx: int = 1) -> bool:
        if not self.songs_list:
            return False
        if len(self.songs_list) < idx + 1 and idx != 0:
            return False
        song = self.songs_list[idx]
        if song.webpage_url not in self.song_cache:
            audio_source = await get_Audio_Source((song.title, song.webpage_url))
            if audio_source:
                self.song_cache[song.webpage_url] = audio_source
                self.logger.info("Caching %s for %d minutes", song.title, song.duration*1.5)
                asyncio.create_task(self.cleanup_cache(song))
                return True
            else:
                self.logger.error("")
        else:
            self.logger.info("%s already in cache", song.title)
        return False


    def play_audio(self, source: PCMVolumeTransformer, stderr_buf: io.BytesIO, bot: commands.Bot, song_url: str):
        if self.vc and not self.vc.is_playing():
            self.source = source
            self.vc.play(source, after=lambda error, stderr_buf=stderr_buf:self.playback_callback_func(
                            error,
                            stderr_buf,
                            self.guild_id,
                            bot,
                            song_url))
            self.start_timer()

    def playback_callback_func(self, error: Exception | None, stderr_buf: io.BytesIO, g_id: int, bot: commands.Bot, song_url: str) -> None:
        if not self.mod_mid_song:
            self.end_timer()
        ffmpeg_error = stderr_buf.getvalue().decode("utf-8", errors="ignore")
        failed = False
        if "403 Forbidden" in ffmpeg_error and song_url in self.song_cache:
            self.logger.info("Stale audio source for %s removing from cache", song_url)
            self.song_cache.pop(song_url)
            failed = True
        if error:
            self.logger.error("Error occured %s", error)
        asyncio.run_coroutine_threadsafe(self.helper_play_next(g_id, bot, failed), bot.loop)
        return None

    async def helper_play_next(self, g_id: int, bot: commands.Bot, failed: bool = False):
        if self.songs_list:
            if not self.song_loop:
                self.songs_list.pop(0)
        if self.songs_list:
            song = self.songs_list[0]
            if song.webpage_url in self.song_cache and not failed:
                ffmpeg_source = self.song_cache[song.webpage_url]
            else:
                ffmpeg_source = await get_Audio_Source((song.title,song.webpage_url))
            if not ffmpeg_source:
                if self.text_channel:
                    await self.text_channel.send(embed=song.return_err_embed())
                self.logger.error("Bad source for %s, %s", song.title, song.webpage_url)
                self.songs_list.pop(0)
                return await self.helper_play_next(g_id, bot)
            stderr_buf = io.BytesIO()
            music_start = self.seek_time if self.seek_time else 0
            source: PCMVolumeTransformer = await asyncio.to_thread(build_audio, self.volume, ffmpeg_source, stderr_buf, seek_time=music_start,opts=self.song_mods)
            self.play_audio(source,stderr_buf,bot,song.webpage_url)
            if self.text_channel:
                next_song = self.songs_list[1] if len(self.songs_list) >= 2 else None
                if not self.mod_mid_song:
                    await self.text_channel.send(embed=song.return_embed(next_song))
                else:
                    self.mod_mid_song = False
                    self.seek_time = None
        if self.text_channel and not self.songs_list:
            await self.text_channel.send(embed=txt_only_embed("Queue empty"))
            self.source = None
        return None

    async def voice_cleanup(self, leave_vc: bool = False) -> None:
        self.songs_list = []
        self.song_loop = False
        if self.source:
            self.source.cleanup()
        if self.vc:
            if self.vc.is_playing():
                self.vc.stop()
            if leave_vc:
                await self.vc.disconnect()
        self.source = None
        self.volume = 1.00
        self.vc = None
        self.seek_time = None

    async def override_task(self) -> None:
        if self.cache_task:
            self.cache_task.cancel()
            await self.cache_task
        self.cache_task = asyncio.create_task(self.cache_songs())
        return None
