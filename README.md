# HatsuneMiku Discord Bot

A locally hosted Discord Bot for playing music with your friends.<br>

## Bot Commands

`/play` &rarr; Play accepts: Youtube, Soundcloud, Spotify links, or a general search e.g. "Monkey"<br>
`/stop` &rarr; Stops all music playback and leaves the call<br>
`/skip` &rarr; Skips the current song in the queue and disables song loop<br>
`/loop` &rarr; Loops current song. Call the command again to toggle loop off <br>
`/queue` &rarr; Get a list of all queued songs<br>
`/remove [song number]` &rarr; Remove a song from the queue<br>
`/clear` &rarr; Stops current song and clears the music queue<br>
`/die` &rarr; Shuts down the bot<br>

## Installation Guide


### Discord API setup

On the discord developer [homepage](https://discord.com/developers/applications) click on new application and set a name for the bot<br>
![Create a new Discord application](githubpictures/dis_newapp.png "New application")<br>
Once the new application is created click on bot under settings, then reset token and copy this down(IMPORTANT DO NOT SHARE THIS!!)<br>
![Copy bot token](githubpictures/dis_botapi.png "Bot API")<br>
Under the same page scroll down and enable message content intent and for bot permissions select administrator(Don't forget to save settings)
![Set message content intent and bot permissions](githubpictures/dis_botsettings.png "Bot perms")<br>
Then under settings click on OAuth2 and select bot under Scopes<br>
![OAuth2 bot scope](githubpictures/dis_oauth.png "Oauth perms")<br>
Under the same page scroll down to bot permissions then select Administrator<br>
![OAuth2 bot permissions](githubpictures/dis_oauth2.png "Oauth perms")<br>
Finally at the bottom of the page select guild install for integration type and open the link under generated URL and select the server you want to add the bot(Must have manage server perms)<br>
![Generated guild install URL](githubpictures/dis_oauth3.png "Oauth perms")

### Getting User ID and Server ID

Enable developer mode in the Discord user settings
![Enable developer mode](githubpictures/developer_mode.png)
Then right click on your profile to copy user id, and right click on desired server and click on copy server id.

### Windows setup

Run `.\'Hatsune-Miku-Bot'\scripts\windows_botsetup.ps1`, <br>
then to start the bot run `.\'Hatsune-Miku-Bot'\scripts\winrun_bot.ps1`.<br>

### Linux/Mac setup

Install `ffmpeg`.<br>
Install `deno` or `node` (Dependency for yt-dlp) <br>
Run `scripts/bash_botsetup.sh`,<br>
then to start the bot run `scripts/bashrun_bot.sh`.<br>

### First Bot startup

On first bot startup you will be prompted to enter Discord Bot API key and Server ID.<br>
These values must be valid for functioning bot.<br>
Optional values will be asked next: Spotify Client ID, Spotify Client Secret, and User ID.<br>
If the bot fails to start, ensure that `.env` values match Discord Bot API key and Server ID.<br> `.env` file is found in project root<br>
