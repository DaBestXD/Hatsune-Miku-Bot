import asyncio
import io
import logging
import time
import random
from discord import Interaction
from discord.ext import commands
from audio_utils.audio_handler import get_Audio_Source
from audio_utils.bot_audio_functions import build_audio, mod_song
from botextras.bot_funcs_ext import reply, text_only_embed
from botextras.bot_events import (FinishedPlayback, ClearQueue, LoopSong,
    Nightcore, QueueSongs, RemoveFromQueue, Shuffle, Skip, GuildPlaybackState,
    Event, StopPlayblack, UpdateVoiceStatus, VolumeControl)
from botextras.constants import CACHE_TIMER_S

class GuildStateController():
    def __init__(self, bot: commands.Bot, id: int) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = id
        self.bot = bot
        self.queue:asyncio.Queue[Event] = asyncio.Queue()
        self.state = GuildPlaybackState()
        self.task: asyncio.Task|None = None

    async def run(self):
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self.main_loop())

    async def stop(self):
        if not self.task:
            return None
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None

    async def add_event(self, event: Event):
        await self.queue.put(event)

    async def main_loop(self):
        while True:
            event = await self.queue.get()
            try:
                # switch statement maybe ?
                if isinstance(event, QueueSongs):
                    await self._queue_helper(event)
                    if not event.vc.is_playing():
                        await self._play()

                elif isinstance(event, Skip):
                    await self._skip(event)

                elif isinstance(event, Shuffle):
                    await self._shuffle(event)

                elif isinstance(event, Nightcore):
                    await self._nightcore(event)

                elif isinstance(event, StopPlayblack):
                    await self._stop_playback(event.interaction)

                elif isinstance(event, VolumeControl):
                    await self._change_volume(event)

                elif isinstance(event, UpdateVoiceStatus):
                    self.state.vc = event.vc

                elif isinstance(event, RemoveFromQueue):
                    await self._remove_from_queue(event)

                elif isinstance(event, LoopSong):
                    await self._loop_song(event)

                elif isinstance(event, ClearQueue):
                    await self._clear_queue(event)

                elif isinstance(event, FinishedPlayback):
                    await self._finished_playback(event.ffmpeg_error)

            finally:
                self.queue.task_done()

    # TODO fix later
    async def remove_from_cache(self, song_url: str):
        await asyncio.sleep(CACHE_TIMER_S)
        if song_url in self.state.song_cache:
            self.state.song_cache.pop(song_url)

    async def bad_cache(self):
        for s in self.state.songs[:3]:
            song = self.state.song_cache.get(s.webpage_url)
            if song: continue
            source = await get_Audio_Source((s.title,s.webpage_url))
            if not source: continue
            self.state.song_cache[s.webpage_url] = source
            asyncio.create_task(self.remove_from_cache(s.webpage_url))

    async def _change_volume(self, event: VolumeControl) -> None:
        self.state.volume = event.volume
        if self.state.source:
            self.state.source.volume = event.volume
        return None

    async def _clear_queue(self, event: ClearQueue) -> None:
        self.state.songs = []
        if self.state.active_song:
            self.state.songs.append(self.state.active_song)
        await reply(event.interaction,embed=text_only_embed("Queue cleared!"))
        return None

    async def _loop_song(self,event: LoopSong):
        self.state.song_loop = not event.loop
        text = "🔁Now looping current song!🔁" if self.state.song_loop else "No longer looping current song!"
        await reply(event.interaction,embed=text_only_embed(text))

    async def _remove_from_queue(self, event: RemoveFromQueue) -> None:
        try:
            if event.idx == 0:
                raise IndexError
            await reply(event.interaction, embed=text_only_embed(f"Removing {self.state.songs[event.idx].title} from the queue!"))
            self.state.songs.pop(event.idx)
        except IndexError:
            await reply(event.interaction, embed=text_only_embed("Value must be within queue"))
        return None

    async def _queue_helper(self, event: QueueSongs) -> None:
        self.state.songs.extend(event.songs)
        self.state.vc = event.vc
        self.state.active_song = self.state.songs[0]
        self.state.text_channel = event.text_channel
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if event.playlist:
            await reply(event.interaction,embed=event.playlist.return_embed())
        else:
            await reply(event.interaction,embed=event.songs[0].return_embed(next_song,queued=True))


    async def _play(self) -> None:
        song = self.state.active_song
        if song and self.state.vc:
            source = self.state.song_cache.get(song.webpage_url)
            if not source:
                source = await get_Audio_Source((song.title,song.webpage_url))
            if not source:
                if self.state.text_channel:
                    await self.state.text_channel.send(embed=self.state.songs[0].return_err_embed())
                self.state.songs.pop(0)
                self.state.active_song = self.state.songs[0] if self.state.songs else None
                return await self._play()
            stderr_buff = io.BytesIO()
            seek_time = self.state.seek_time if self.state.seek_time else 0
            built_source = await asyncio.to_thread(build_audio,self.state.volume,source,stderr_buff,seek_time,self.state.song_mods)
            self.state.source = built_source
            self.state.vc.play(built_source, after= lambda error, stderr_buff=stderr_buff: self._callback_queue(error,stderr_buff))
            if not self.state.mod_song:
                self.state.start_time = time.monotonic()
                if self.state.text_channel:
                    next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
                    await self.state.text_channel.send(embed=song.return_embed(next_song))
            else:
                self.state.mod_song = False
                self.state.seek_time = None
            self.state.song_cache[song.webpage_url] = source
            await self.bad_cache()
        else:
            if self.state.text_channel:
                await self.state.text_channel.send(embed=text_only_embed("Queue empty🐱"))
        return None

    def _callback_queue( self, error: Exception | None, stderr_buff: io.BytesIO,) -> None:
        if error: ...
        ffmpeg_error = stderr_buff.getvalue().decode("utf-8", errors="ignore")
        asyncio.run_coroutine_threadsafe(self.add_event(FinishedPlayback(ffmpeg_error)),self.bot.loop)
        return None

    async def _finished_playback(self, ffmpeg_error: str) -> None:
        if "403 Forbidden" in ffmpeg_error:
            if self.state.active_song:
                try:
                    self.state.song_cache.pop(self.state.active_song.webpage_url)
                except: ...
        if self.state.songs:
            if not self.state.song_loop:
                self.state.songs.pop(0)
        self.state.active_song = self.state.songs[0] if self.state.songs else None
        await self._play()
        return None

    async def _skip(self, event: Skip) -> None:
        next_song = self.state.songs[1] if len(self.state.songs) >= 2 else None
        if self.state.active_song:
            await reply(event.interaction,embed=self.state.active_song.return_skip_embed(next_song))
        self.state.song_loop = False
        if self.state.vc:
            self.state.vc.stop()
        await self.bad_cache()
        return None

    async def _shuffle(self, event: Shuffle) -> None:
        await reply(event.interaction,embed=text_only_embed("🔀Queue shuffled🔀"))
        if self.state.songs and len(self.state.songs) > 2:
            head = [self.state.songs[0]]
            body = self.state.songs[1:] if len(self.state.songs) > 1 else []
            random.shuffle(body)
            self.state.songs = head + body
        if event.done and not event.done.done():
                event.done.set_result(None)
        await self.bad_cache()
        return None

    async def _nightcore(self, event: Nightcore) -> None:
        self.state.song_mods = await mod_song("pitch",1.25) if not self.state.song_mods else await mod_song("off")
        self.state.mod_song = True
        self.state.nightcore = not self.state.nightcore
        text = "Nightcore on!🙀" if self.state.song_mods != "" else "Nightcore off!😿"
        if self.state.vc and self.state.active_song:
            self.state.songs.insert(1,self.state.active_song)
            self.state.vc.stop()
            if self.state.start_time:
                self.state.seek_time = time.monotonic() - self.state.start_time
            await reply(event.interaction,embed=text_only_embed(text))
        if event.done and not event.done.done():
            event.done.set_result(None)
        return None

    async def _stop_playback(self, interaction: Interaction) -> None:
        self.state.active_song = None
        self.state.seek_time = None
        self.state.text_channel = None
        self.state.start_time = None
        self.state.source = None
        self.state.nightcore = False
        self.state.song_loop = False
        self.state.mod_song = False
        self.state.song_mods = ""
        self.state.songs = []
        if self.state.vc:
            if self.state.vc.is_playing():
                self.state.vc.stop()
            await self.state.vc.disconnect()
        self.state.vc = None
        await reply(interaction, embed=text_only_embed("Stopping playback..."))

    async def hard_reset(self) -> None:
        await self.stop()
        if self.state.vc:
            try:
                if self.state.vc.is_playing():
                    self.state.vc.stop()
            except Exception: pass
            try:
                await self.state.vc.disconnect()
            except Exception: pass
        self.state = GuildPlaybackState()
        self.queue = asyncio.Queue()
        await self.run()
