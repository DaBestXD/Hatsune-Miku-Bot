import re
import requests
import base64
import warnings
from typing import Any, cast
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from botextras.constants import CLIENT_ID, CLIENT_SECRET

YDL_OPTS_R = {
    "format": "bestaudio/best",
    "default_search": "ytsearch1",
    "js_runtimes": {"node": {}},
    "noplaylist": True,
    "no_warnings": True,
}
#Any cast to make the type check shut up cause importing _Params doesnt work😾
YDL_OPTS = cast(Any, YDL_OPTS_R)
YOUTUBE = "youtu"
SOUNDCLOUD = "soundcloud"
SPOTIFY = "spotify"


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


def get_Youtube_Info(url: str) -> tuple[str, str] | None:
    try:
        with YoutubeDL(params=YDL_OPTS) as ydl:
            result = ydl.extract_info(url, download=False)
            title = result.get("title")
            if title:
                return (title, url)
            return None
    except DownloadError:
        return None


def get_Spotify_Info(track_id: str) -> tuple[str, str] | None:
    api_link = "https://api.spotify.com/v1/tracks/" + track_id
    token = get_token()
    info = requests.get(api_link, headers={"Authorization": f"Bearer {token}"})
    if info.status_code == 200:
        song_json = info.json()
        song_info = song_json["artists"][0]["name"] + " - " + song_json["name"]
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(song_info, download=False)
            title = result.get("title")
            song_url = result.get("entries")
            if song_url and title:
                song_url = song_url[0].get("original_url")
                return (title, song_url)
            return None
    print(f"Spotify returned error: {info.reason}:{info.status_code}")
    return None


def get_Soundcloud_Info(url: str) -> tuple[str, str] | None:
    if re.match(r"(.*sets+.*)(?:\?)", url):
        print("Soundcloud playlists are not accepted")
        return None
    with YoutubeDL(params=YDL_OPTS) as ydl:
        pattern = re.compile(
            r"(.*)(?:\?)"
        )  # formats soundclound links to just be domain/artist/track_name
        re_groups = pattern.match(url)
        if re_groups:
            formatted_url = re_groups.group(1)
            result = ydl.extract_info(formatted_url, download=False)
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
                return (title, formatted_url)
        print("Regex bad something something")
        return None


def search_Query(query: str) -> tuple[str, str] | None:
    with YoutubeDL(params=YDL_OPTS) as ydl:
        result = ydl.extract_info(query, download=False)
        if "entries" in result:
            song_url = result["entries"][0].get("original_url")
            song_title = result.get("title")
            if song_title and song_url:
                return (song_title, song_url)
        else:
            return None


async def get_Song_Info(url: str) -> tuple[str, str] | None:
    pattern = re.compile(
        r"(?:https://)([a-z.]+/)(.*)"
    )  # Filters into two parts domain and other
    grouped_url = pattern.match(url)
    if grouped_url is None:
        # no match means it's a serach query
        return search_Query(url)
    url_domain = grouped_url.group(1)
    if SPOTIFY in url_domain:
        track_pattern = re.compile(r"(?:track/)(\w+)")
        track_id = track_pattern.match(grouped_url.group(2))
        if track_id:
            track_id = track_id.group(1)
            return get_Spotify_Info(track_id)
    if YOUTUBE in url_domain:
        return get_Youtube_Info(url)
    if SOUNDCLOUD in url_domain:
        return get_Soundcloud_Info(url)
    return None


# Final function before audio plays should only take in url's as input
async def get_Audio_Source(url: str) -> str | None:
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            result = ydl.extract_info(url, download=False)
            return result.get("url")
    except DownloadError as e:
        print(f"Download error: {e}")
        return None
