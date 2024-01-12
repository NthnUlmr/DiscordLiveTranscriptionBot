# DiscordLiveTranscriptionBot


### A simple Discord bot which transcribes your Discord conversations in real time.
# - - -
# How It Works
 Using py-cord, the bot can gain access to the voice channel you invite it to to listen
        to your conversation and then poll a speech-to-text API service to transcribe the conversation
        in real time. The transcription is separated by user and printed to the output channel in Discord.

 When you send the bot the shutdown command, it sends a request to ChatGPT to summarize the transcription
           of the conversation. This is then posted to the discord channel.
