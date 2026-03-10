# How bot audio is generated and played

## Song lifetime

<details>
<summary>Text explantation</summary>

1. Play command used
1. Check if query is link or search (Regex)
1. Search &rarr; `yt-dlp search2:{query}` &rarr; return highest viewed video metadata
1. Link &rarr; Separate by domain<br>
a. Spotify &rarr; Spotify API to get song metadata<br>
b. YT/Soundcloud(non-playlist) &rarr; YT-dlp to get song metadata (non-process for faster extraction)<br>
1. Check Guildplayback state VC<br>
a. VC playing? &rarr; Add to queue &rarr; Exit early<br>
b. VC not playing? &rarr; Extract audio &rarr; Play song
1. Song ends &rarr; Song callback function called<br>
a. Removed finished song from queue<br>
b. Queue empty? Yes &rarr; display Queue empty to users<br>
c. Queue empty? No &rarr; Extract audio from next song<br>
1. Repeat step 6 until queue empty

</details>

```mermaid
flowchart TD
    A[Play command used] --> B{Query is link?}

    B -- No, search query --> C[Run yt-dlp search2:query]
    C --> D[Return highest viewed video metadata]

    B -- Yes, direct link --> E{Domain type}
    E -- Spotify --> F[Use Spotify API to get song metadata]
    E -- YouTube/SoundCloud non-playlist --> G[Use yt-dlp metadata extraction non-process]

    D --> H{Voice client playing?}
    F --> H
    G --> H

    H -- Yes --> I[Add song to queue]
    I --> J[Exit early]

    H -- No --> K[Extract audio and play song]
    K --> L[Song ends callback]

    L --> M[Remove finished song from queue]
    M --> N{Queue empty?}

    N -- Yes --> O[Display Queue empty]
    N -- No --> P[Extract audio for next song and play]
    P --> L

```
