# HatsuneMiku discord bot
A locally hosted discord bot for playing music with your friends.<br>

## Installation Guide 
You will need a discord bot API key and server id.<br>
Ensure any version of python 3.10+ is installed.<br>
A spotify API key is necessary to play spotify related links. <br>
Bot will still function without a spotify API key.<br>
### Getting userid and server id
Enable developer mode in the discord user settings
![Enable developer mode](githubpictures/developer_mode.png)
Then right click on your profile to copy user id, and right click on desired server and click on copy server id.
### Discord API setup
<details>
<summary>Click to expand</summary>

On the discord developer [homepage](https://discord.com/developers/applications) click on new application and set a name for the bot
![Create a new Discord application](githubpictures/dis_newapp.png "New application")
Once the new application is created click on bot under settings, then reset token and copy this down(IMPORTANT DO NOT SHARE THIS!!)
![Copy bot token](githubpictures/dis_botapi.png "Bot api")
Under the same page scroll down and enable message content intent, and for bot permissions select administrator(Don't forget to save settings)
![Set message content intent and bot permissions](githubpictures/dis_botsettings.png "Bot perms")
Then under settings click on OAuth2 and select bot under Scopes
![OAuth2 bot scope](githubpictures/dis_oauth.png "Oauth perms")
Under the same page scroll down to bot permissions then select Administrator
![OAuth2 bot permissions](githubpictures/dis_oauth2.png "Oauth perms")
Finally at the bottom of the page select guild install for integration type and open the link under generated URL and select the server you want to add the bot(Must have manage server perms)
![Generated guild install URL](githubpictures/dis_oauth3.png "Oauth perms")
</details>

### Windows setup
Run `scripts/windows_botsetup.ps1`, <br>
then to start the bot run `scripts/winrun_bot.ps1`.<br>

### Linux/Mac setup
Install `ffmpeg`.<br>
Install `deno` or any other javascript runtime/engine(Dependency for yt-dlp) <br>
Run `scripts/bash_botsetup.sh`,<br>
then to start the bot run `scripts/bashrun_bot.sh`.<br>
