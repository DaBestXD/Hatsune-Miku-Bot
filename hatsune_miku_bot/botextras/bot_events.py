import asyncio
from dataclasses import dataclass, field
from audio_utils.audio_class import Song, Playlist
from discord import PCMVolumeTransformer, TextChannel, VoiceClient, Interaction
from typing import Optional

class Event:
    pass

@dataclass()
class GuildPlaybackState():
    songs: list[Song] = field(default_factory=list)
    song_cache: dict[str,str] = field(default_factory=dict)
    source: PCMVolumeTransformer|None = None
    song_loop: bool = False
    start_time: float|None = None
    seek_time: float|None = None
    song_bass: str = ""
    song_speed: str = ""
    song_pitch: str = ""
    volume: float = 1.0
    text_channel: TextChannel|None = None
    vc: VoiceClient|None = None
    active_song: Song|None = None
    nightcore: bool = False
    mod_song: bool = False

@dataclass()
class Skip(Event):
    interaction: Interaction

@dataclass()
class Shuffle(Event):
    interaction: Interaction
    done: asyncio.Future[None]|None = None

@dataclass()
class QueueSongs(Event):
    songs: list[Song]
    vc: VoiceClient
    text_channel: TextChannel
    interaction: Interaction
    playlist: Optional[Playlist] = None

@dataclass()
class DisplayQueue(Event):
    interaction: Interaction

@dataclass()
class StopPlayblack(Event):
    interaction: Interaction

@dataclass()
class Nightcore(Event):
    interaction: Interaction
    vc: VoiceClient
    done: asyncio.Future[None]|None = None

@dataclass()
class SetBass(Event):
    interaction: Interaction
    vc: VoiceClient
    effect_strength: float

@dataclass()
class SetSpeed(Event):
    interaction: Interaction
    vc: VoiceClient
    effect_strength: float

@dataclass()
class VolumeControl(Event):
    volume: float

@dataclass()
class UpdateVoiceStatus(Event):
    vc: VoiceClient|None

@dataclass()
class RemoveFromQueue(Event):
    interaction: Interaction
    idx: int

@dataclass()
class LoopSong(Event):
    interaction: Interaction
    loop: bool

@dataclass()
class ClearQueue(Event):
    interaction: Interaction

@dataclass()
class FinishedPlayback(Event):
    ffmpeg_error: str = ""

