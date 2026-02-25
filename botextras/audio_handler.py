import re
import requests
import base64
import warnings
import asyncio
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from botextras.constants import (CLIENT_ID,
    CLIENT_SECRET, SP_ALBUM_META_PARAMS, SP_ALBUM_PARAMS,
    SP_PLAYLIST_META_PARAMS, SP_PLAYLIST_PARAMS, YDL_OPTS,
    YOUTUBE, SOUNDCLOUD, SPOTIFY, SP_ALBUM_LINK,
    SP_TRACK_LINK, SP_PLAYLIST_LINK,AUDIO_OPTS)

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
    print(f"Token collection returned: {token_res.reason}:{token_res.status_code}")
    return None


def get_Youtube_Info(url: str) -> list[tuple[str,...]] | None:
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(url, download=False)
            entries = result.get("entries")
            if entries:
                songs:list[tuple[str,...]] = []
                for n in entries:
                    song_title = n.get("title")
                    song_url = n.get("url")
                    if song_title and song_url:
                        songs.append((song_title,song_url))
                playlist_title = result.get("title") or "Unknown title"
                playlist_count = result.get("playlist_count") or "Unknown playlist count"
                songs.append((playlist_title, url, playlist_count))
                return songs
            title = result.get("title")
            if title:
                return [(title, url)]
            return None
    except DownloadError:
        return None

def sp_multi_helper_func(api_link: str, headers: dict[str,str], params: dict[str,str] | None, path_type: str)-> list[tuple[str,...]] | None:
    songs: list[tuple[str,str]] = []
    while api_link:
        r = requests.get(url=api_link, headers=headers, params=params)
        if r.status_code != 200:
            print(f"Spotify error: {r.status_code}")
            return None
        song_json = r.json()
        items = song_json.get("items")
        if not items:
            print(f"Something bad happen trying to get the items of {api_link}")
            return None
        if path_type == "album":
            songs.extend([(item["name"] + " - " +
                item["artists"][0]["name"],item["external_urls"]["spotify"])
                for item in items if item.get("external_urls")])
        if path_type == "playlist":
            songs.extend([(item["track"]["name"] + " - " +
                item["track"]["artists"][0]["name"],item["track"]["external_urls"]["spotify"])
                for item in items if item["track"].get("external_urls")])
        api_link = song_json.get("next")
        params = None
    return songs


# TODO clean this up later
def get_Spotify_Info(path_type: str, id: str) -> list[tuple[str,...]] | None:
    token = get_token()
    headers = {"Authorization" : f"Bearer {token}"}
    if "/album/" in path_type:
        api_link = SP_ALBUM_LINK + id + "/tracks"
        album_name: str = "Unknown"
        album_count: str = "-1"
        params = SP_ALBUM_PARAMS
        songs = sp_multi_helper_func(api_link,headers,params,path_type="album")
        if not songs:
            return None
        r = requests.get(url=(SP_ALBUM_LINK+id),headers=headers,params=SP_ALBUM_META_PARAMS)
        if r.status_code == 200:
            album_json = r.json()
            album_name = album_json["name"]
            album_count = album_json["total_tracks"]
        songs.append((album_name,path_type,album_count))
        return songs
    elif "/playlist/" in path_type:
        api_link = SP_PLAYLIST_LINK + id + "/tracks"
        playlist_name, playlist_count = "Unknown", "-1"
        params = SP_PLAYLIST_PARAMS
        songs = sp_multi_helper_func(api_link,headers,params,path_type="playlist")
        if not songs:
            return None
        r = requests.get(url=(SP_PLAYLIST_LINK+id), headers=headers, params=SP_PLAYLIST_META_PARAMS)
        if r.status_code == 200:
            playlist_json = r.json()
            playlist_name = playlist_json["name"]
            playlist_count = playlist_json["tracks"]["total"]
        songs.append((playlist_name, path_type, playlist_count))
        return songs
    elif "/track/" in path_type:
        api_link = SP_TRACK_LINK + id
        params = {"market": "US"}
        r = requests.get(url=api_link, headers=headers, params=params)
        if r.status_code != 200:
            print(f"Spotify error: {r.status_code}")
            return None
        song_json = r.json()
        song_url = song_json["external_urls"]["spotify"]
        song_name = song_json["name"]
        song_artist = song_json["artists"][0]["name"]
        song_info: str = song_name + " - " + song_artist
        return [(song_info, song_url)]
    return None


def get_Soundcloud_Info(url: str) -> list[tuple[str, ...]] | None:
    if re.match(r"(.*sets+.*)(?:\?)", url):
        print("Soundcloud playlists are not accepted")
        return None
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            # formats soundclound links to just be domain/artist/track_name
            result = ydl.extract_info(url, download=False)
            restricted = True
            formats = result.get("formats")
            title = result.get("title")
            if formats and title:
                for key in formats:
                    if "http_mp3" in key["format_id"]:
                        restricted = False
                if restricted:
                    print("Unable to retrieve soundcloud http_mp3")
                    return None
                return [(title, url)]
            print("Regex bad something something")
            return None
    except DownloadError as e:
        print(f"DownloadError: {e}")


def search_Query(query: str) -> list[tuple[str, str]] | None:
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(query, download=False)
            entries = result.get("entries")
            if entries:
                songs = []
                for n in entries:
                    song_url = n.get("url") or "Unknown url"
                    if "channel/" in song_url:
                        continue
                    song_title = n.get("title") or "Unknown title"
                    view_count = n.get("view_count") or 1
                    songs.append((view_count, song_url, song_title))
                if songs:
                    max_vc = 0
                    _, song_title, song_url = songs[0]
                    for vc, url, song_title in songs:
                        if max_vc < vc:
                            song_url = url
                            max_vc = vc
                            song_title = song_title
                    return [(song_title, song_url)]
            else:
                return None
    except DownloadError as e:
        print(f"DownloadError: {e}")
        return None

def _get_Song_Info(url: str) -> list[tuple[str,...]] | None:
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
            return get_Spotify_Info(url, id)
    if YOUTUBE in url_domain:
        return get_Youtube_Info(url)
    if SOUNDCLOUD in url_domain:
        return get_Soundcloud_Info(url)
    return None
async def get_Song_Info(url: str):
    return await asyncio.to_thread(_get_Song_Info, url)

# Final function before audio plays should only take in url's as input
def _get_Audio_Source(query: tuple[str|None, ...]) -> str | None:
    try:
        with YoutubeDL(AUDIO_OPTS) as ydl:
            title, url = query
            if title and url:
                if "spotify" in url:
                    result = ydl.extract_info(title, download=False)
                    entries = result.get("entries")
                    songs = []
                    if entries:
                        for n in entries:
                            view_count = n.get("view_count") or 1
                            url = n.get("url")
                            songs.append((view_count, url))
                    max_vc = 0
                    return_url = None
                    for vc, url in songs:
                        if max_vc < vc:
                            return_url = url
                            max_vc = vc
                    print(f"Loaded audio for: {title}")
                    return return_url
                else:
                    result = ydl.extract_info(url=url,download=False)
                    print(f"Loaded audio for: {title}")
                    return result.get("url")
            return None
    except DownloadError as e:
        print(f"Download error: {e}")
        return None
async def get_Audio_Source(query: tuple[str|None, ...]):
    return await asyncio.to_thread(_get_Audio_Source, query)
