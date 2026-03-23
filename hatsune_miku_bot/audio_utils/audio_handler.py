from __future__ import annotations
import logging
import re
import requests
import base64
import warnings
import asyncio
from typing import cast
from audio_utils.audio_class import Song, Playlist
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from hatsune_miku_bot.botextras.constants import (CLIENT_ID, CLIENT_SECRET, EXTRACT_VALS,
    EXTRACT_VALS_PLAYLIST,EXTRACT_VALS_SEARCH, SP_ALBUM_META_PARAMS,
    SP_ALBUM_PARAMS, SP_PLAYLIST_META_PARAMS, SP_PLAYLIST_PARAMS, YDL_OPTS,
    YOUTUBE, SOUNDCLOUD, SPOTIFY, SP_ALBUM_LINK, SP_TRACK_LINK,
    SP_PLAYLIST_LINK,AUDIO_OPTS)

logger = logging.getLogger(__name__)

def yt_json_parser(entries: list[dict[str,str|None]], extract_items: tuple[str,...])->list[Song]|None:
    return_val:list[Song] = []
    for e in entries:
        song_dict:dict[str,str] = {}
        if not isinstance(e, dict):
            continue
        for key in extract_items:
            # This terribleness is to extract thumbnails, as thumbnails are stored as a list of dicts
            # with the key of url holding the thumbnail link and -1 is to get the largest thumbnail
            temp = (tb.get("url") if isinstance(val:=e.get(key), list)
            and val and isinstance(tb:=val[-1], dict) else str(val))
            if not temp or temp == "None":
                continue
            song_dict[key] = temp
        if len(song_dict.values()) == 5:
            return_val.append(Song(*song_dict.values()))
        else:
            continue
    if return_val:
        return return_val
    else:
        return None

def get_token() -> None | str:
    # Silent fail if no provided spotify client id or secret
    if not CLIENT_ID or not CLIENT_SECRET:
        warnings.warn("Spotify client id or client secret not found")
        return None
    auth_string = CLIENT_ID + ":" + CLIENT_SECRET
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = str(base64.b64encode(auth_bytes), "utf-8")
    token_res = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
    )
    if token_res.status_code == 200:
        token = token_res.json()["access_token"]
        return token
    logger.error("[%s]: %d", token_res.reason, token_res.status_code)
    return None

def search_Query(query: str) -> Song | None:
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(f"ytsearch2:{query}", download=False, process=False)
            entries = result.get("entries")
            if entries:
                songs:list[Song] = []
                for n in entries:
                    song_url:str = n.get("url") or "Unknown url"
                    if "channel/" in song_url:
                        continue
                    song = yt_json_parser([n],EXTRACT_VALS_SEARCH)
                    if song:
                        song = song[0]
                        songs.append(song)
                if songs:
                    return Playlist(songs).greatest_view_count()
                logger.error("Search_query failed to get song info(Song list empty)")
                return None
            else:
                logger.error("Search_query failed to return a search result for %s(No entries)",query)
                return None
    except DownloadError as e:
        logger.error("Search query download error: %s", e)
        return None

def get_Youtube_Info(url: str) -> Playlist|Song|None:
    """
    This function is strictly for urls(Playlist or single tracks)
    """
    try:
        cleaned_url = re.match(r"^([^&+]*)",url)
        if cleaned_url:
            cleaned_url = cleaned_url.group(1)
        else:
            logger.error("Regex error for %s", url)
            return None
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(cleaned_url, download=False,process=False)
            entries = result.get("entries")
            result = cast(dict[str,str|None],result)
            if entries:
                songs:list[Song]|None = (yt_json_parser(entries,EXTRACT_VALS_SEARCH))
                if songs:
                    # This extracts playlist thumbnail image I would use the item_extractor function
                    # but I hardcoded it to return list[Song] and I don't want to rewrite the function
                    # Ideally it should just be "playlist_vals = item_extractor(result, EXTRACT_VALS_PLAYLIST)"
                    playlist_vals:list[str] = [lv.get("url") or "None" if
                        isinstance(tmb := result.get(key) or "Unknown",list)
                        and isinstance(lv :=tmb[-1],dict) else tmb for key in
                        EXTRACT_VALS_PLAYLIST]
                    return Playlist(songs,*playlist_vals)
                else:
                    return None
            single_song = yt_json_parser([result],EXTRACT_VALS)
            if single_song:
                return single_song[0]
            return None
    except DownloadError:
        return None


def get_Soundcloud_Info(url: str) -> Song| None:
    if re.match(r"(.*sets+.*)(?:\?)", url):
        logger.info("Soundcloud playlist was entered")
        return None
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(url, download=False)
            restricted = True
            formats = result.get("formats")
            result = cast(dict[str,str|None],result)
            if formats:
                for key in formats:
                    if "http_mp3" in key["format_id"]:
                        restricted = False
                if restricted:
                    logger.info("Unable to retrieve soundcloud http_mp3")
                    return None
                song = yt_json_parser([result],EXTRACT_VALS)
                if song:
                    return song[0]
                else:
                    logger.error("Song information empty: %s",url)
                    return None
            logger.error("Regex failed for soundcloud info, Formats: %s Title: %s", formats, url)
            return None
    except DownloadError as e:
        logger.error("Soundcloud download error: %s", e)
        return None


# Messy but it works
# TODO set up extractor similar to item_extractor
def sp_multi_helper_func(api_link: str, headers: dict[str,str], params: dict[str,str] | None, path_type: str, alb_thumb_url: str = "None")-> list[Song] | None:
    songs: list[Song] = []
    while api_link:
        r = requests.get(url=api_link, headers=headers, params=params)
        if r.status_code != 200:
            logger.error("Sp_multi_helpfunc http error: [%d]", r.status_code)
            return None
        song_json = r.json()
        items = song_json.get("items")
        if not items:
            logger.error("Sp_multi_helpfunc Error trying to get items for: %s", api_link)
            return None
        if path_type == "album":
            for track in items:
                try:
                    track_name = track["name"]
                    duration = track["duration_ms"] // 1000
                    artist = track["artists"][0]["name"]
                    spotify_url = track["external_urls"]["spotify"]
                    title = track_name + " - " + artist
                    songs.append(Song(title,spotify_url,alb_thumb_url,duration,"0"))
                except IndexError:
                    continue
                except KeyError:
                    continue
                except AttributeError:
                    continue
                except TypeError:
                    continue
        if path_type == "playlist":
            for song in items:
                if track:=song.get("track"):
                    try:
                        track_name = track["name"]
                        spotify_url = track["external_urls"]["spotify"]
                        artist= track["artists"][0]["name"]
                        thumbnail_url = track["album"]["images"][0]["url"]
                        duration = track["duration_ms"] // 1000
                        title = track_name + " - " + artist
                        songs.append(Song(title,spotify_url,thumbnail_url,duration,"0"))
                    except IndexError:
                        continue
                    except KeyError:
                        continue
                    except AttributeError:
                        continue
                    except TypeError:
                        continue
        api_link = song_json.get("next")
        params = None
    return songs
# TODO oh my god... Fix this
def get_spotify_info(path_type: str, id: str) -> Playlist|Song|None:
    token = get_token()
    headers = {"Authorization" : f"Bearer {token}"}
    songs:list[Song]|None = []
    if "/album/" in path_type:
        api_link = SP_ALBUM_LINK + id + "/tracks"
        album_name: str = "Unknown"
        album_thumbnail: str = "None"
        r = requests.get(url=(SP_ALBUM_LINK+id),headers=headers,params=SP_ALBUM_META_PARAMS)
        if r.status_code == 200:
            try:
                album_json = r.json()
                album_name = album_json["name"]
                album_thumbnail = album_json["images"][0]["url"]
            except AttributeError:
                return None
            songs = sp_multi_helper_func(api_link,headers,params=SP_ALBUM_PARAMS,path_type="album",alb_thumb_url=album_thumbnail)
        if not songs:
            return None
        return Playlist(songs,album_name,path_type,album_thumbnail)
    elif "/playlist/" in path_type:
        api_link = SP_PLAYLIST_LINK + id + "/tracks"
        playlist_name = "Unknown"
        params = SP_PLAYLIST_PARAMS
        songs = sp_multi_helper_func(api_link,headers,params,path_type="playlist")
        if not songs:
            return None
        r = requests.get(url=(SP_PLAYLIST_LINK+id), headers=headers, params=SP_PLAYLIST_META_PARAMS)
        if r.status_code == 200:
            playlist_json = r.json()
            playlist_thumbnail = playlist_json["images"][0]["url"]
            playlist_name = playlist_json["name"]
            return Playlist(songs,playlist_name,path_type,playlist_thumbnail)
    elif "/track/" in path_type:
        api_link = SP_TRACK_LINK + id
        params = {"market": "US"}
        r = requests.get(url=api_link, headers=headers, params=params)
        if r.status_code != 200:
            logger.error("Spotify http error [%d]", r.status_code)
            return None
        song_json = r.json()
        try:
            thumbnail = song_json["album"]["images"][0]["url"]
            duration = song_json["duration_ms"] // 1000
            song_name = song_json["name"]
            song_artist = song_json["artists"][0]["name"]
            song_title: str = song_name + " - " + song_artist
            return Song(song_title,path_type,thumbnail,duration,"0")
        except AttributeError:
            return None
        except TypeError:
            return None
    return None

def _get_Song_Info(url: str) -> Playlist|Song|None:
    # Filters into two parts domain and other
    grouped_url = re.match(r"(?:https://)([a-z.]+/)(.*)", url)
    if grouped_url is None:
        return search_Query(url)
    url_domain = grouped_url.group(1)
    url_path = grouped_url.group(2)
    if SPOTIFY in url_domain:
        re_groups = re.match(r"(track/|playlist/|album/)(\w+)(?:\?|$)", url_path)
        if re_groups:
            id = re_groups.group(2)
            return get_spotify_info(url, id)
    if YOUTUBE in url_domain:
        return get_Youtube_Info(url)
    if SOUNDCLOUD in url_domain:
        return get_Soundcloud_Info(url)
    return None

async def get_Song_Info(url: str):
    return await asyncio.to_thread(_get_Song_Info, url)

def _get_Audio_Source(query: tuple[str,str]) -> str | None:
    try:
        with YoutubeDL(AUDIO_OPTS) as ydl:
            title, og_url = query
            if "spotify" in og_url:
                result = ydl.extract_info(f"ytsearch2:{title}", download=False)
                entries = result.get("entries")
                songs = []
                if not entries:
                    logger.info("Unable to find entries for %s, link: %s", title, og_url)
                    return None
                for n in entries:
                    url = n.get("url")
                    view_count:int|None = n.get("view_count")
                    songs.append((view_count, url))
                _, url = max(songs)
                logger.info("Loaded audio for spotify link: %s, %s", title , og_url)
                return url
            else:
                result = ydl.extract_info(url=og_url,download=False)
                logger.info("Loaded audio for non-spotify link: %s, %s", title ,og_url.replace("https://", ""))
                return result.get("url")
    except DownloadError as e:
        logger.error("Audio source download error: %s", e)
        return None
    except Exception as e:
        logger.critical("Audio failed in unexpected way: %s", e)
        return None

async def get_Audio_Source(query: tuple[str,str]):
    return await asyncio.to_thread(_get_Audio_Source, query)
