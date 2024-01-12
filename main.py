
# <GPLv3_Header>
## - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# \copyright
#                    Copyright (c) 2024 Nathan Ulmer.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

# <\GPLv3_Header>

##
# \mainpage Discord Transcription Bot
#
# \copydoc main.py

##
# \file main.py
#
# \author Nathan Ulmer
#
# \date \showdate "%A %d-%m-%Y"
#
# \brief This project is a simple Discord bot which transcribes your Discord conversations in
#        real time.
# - - -
# \section desc How It Works
# \p Using py-cord, the bot can gain access to the voice channel you invite it to to listen
#        to your conversation and then poll a speech-to-text API service to transcribe the conversation
#        in real time. The transcription is separated by user and printed to the output channel in Discord.
#
# \p When you send the bot the shutdown command, it sends a request to ChatGPT to summarize the transcription
#           of the conversation. This is then posted to the discord channel.
#


## \todo Read in secrets from files and get rid of TODO strings. Move those file paths to the top so end user can set,
#        or better yet, add the paths to a config file or command-line input so this can be deployed with the env.
## \todo Move outputs to an output directory
## \todo Add better documentation
## \todo Debug issues with networking eventually hanging and then breaking the transcription for long sessions.




## \section Dependencies
import os
import discord
from dotenv import load_dotenv
import os
import sys
import openai
from google.cloud import speech
import google.cloud.texttospeech as tts
import wave
import pyaudio
import time
import io
from pydub import AudioSegment

from discord.sinks.core import Filters, Sink, default_filters
from pydub import AudioSegment
from queue import Queue


##
# \brief The
#
class StreamBuffer:
    def __init__(self) -> None:

        with open('transcript.txt', 'w+') as transFile:
            transFile.write("")
        # holds byte-form audio data as it builds
        self.byte_buffer = {} # bytes
        self.startTimes = {}
        self.segment_buffer = Queue()  # pydub.AudioSegments

        # audio data specifications
        self.sample_width = 2
        self.channels = 2
        self.sample_rate = 48000
        self.bytes_ps = 192000  # bytes added to buffer per second
        self.block_len = 5  # how long you want each audio block to be in seconds
        # min len to pull bytes from buffer
        self.buff_lim = self.bytes_ps * self.block_len

        # temp var for outputting audio
        self.ct = 1

        self.transcribedText = []

    def write(self, data, user,wtime):

        if not user in self.byte_buffer.keys():
            self.byte_buffer[user] = bytearray()
            self.startTimes[user] = -1

        if self.startTimes[user] == -1:
            self.startTimes[user] = wtime

        self.byte_buffer[user] += data  # data is a bytearray object
        # checking amount of data in the buffer
        if len(self.byte_buffer[user]) > self.buff_lim:

            # grabbing slice from the buffer to work with
            byte_slice = self.byte_buffer[user][:self.buff_lim]

            # creating AudioSegment object with the slice
            audio_segment = AudioSegment(data=byte_slice,
                                         sample_width=self.sample_width,
                                         frame_rate=self.sample_rate,
                                         channels=self.channels,
                                         )
            self.byte_buffer[user] = self.byte_buffer[user][self.buff_lim:]


            # adding AudioSegment to the queue
            self.segment_buffer.put(audio_segment)

            # temporary for validating process
            audio_segment.export(f"output{self.ct}.wav", format="wav")

            audio_file = open(f"output{self.ct}.wav", 'rb')
            openai.api_key = "todo API key"
            response = openai.Audio.transcribe("whisper-1", audio_file)
            if not response.text.lower().strip() == 'you':
                self.transcribedText.append((str(user),str(response.text),str(self.startTimes[user])))
                with open('transcript.txt','a+', encoding="utf-8") as transFile:
                    transFile.write(str(user) + '|' +  response.text + '|' + str(self.startTimes[user]) + '\n')
                print(user,response.text,self.startTimes[user])
            self.startTimes[user] = -1
            self.ct += 1





global_stream_buffer = StreamBuffer()

class StreamSink(Sink):
    def __init__(self, *, filters=None):
        if filters is None:
            filters = default_filters
        self.filters = filters
        Filters.__init__(self, **self.filters)
        self.vc = None
        self.audio_data = {}

        # user id for parsing their specific audio data
        self.user_id = None

    def write(self, data, user):
        global global_stream_buffer
        global_stream_buffer.write(data=data, user=user,wtime=time.time())

    def cleanup(self):
        self.finished = True

    def get_all_audio(self):
        # not applicable for streaming but may cause errors if not overloaded
        pass

    def get_user_audio(self, user):
        # not applicable for streaming but will def cause errors if not overloaded called
        pass

    def set_user(self, user_id: int):
        self.user_id = user_id
        print(f"Set user ID: {user_id}")

load_dotenv()
TOKEN = "TODO Discord bot token"

intents = discord.Intents.all()

# 2
print(discord.__dict__)
bot = discord.Bot(intents=intents)
connections = {}
stream_sink = StreamSink()



@bot.event
async def on_ready():
    guild = discord.utils.get(bot.guilds)
    print(
        f'{bot.user} is connected to the following guild:\n'
        f'{guild.name}(id: {guild.id})'
    )

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):  # Our voice client already passes these in.
    try:
        recorded_users = [  # A list of recorded users
            f"<@{user_id}>"
            for user_id, audio in sink.audio_data.items()
        ]

        await sink.vc.disconnect()  # Disconnect from the voice channel.
        client = speech.SpeechClient.from_service_account_json('googleApiKey2.json')
        RATE = 48000

        transLines = []

        usrcount = 0
        for user_id, audio in sink.audio_data.items():
            count = 0
            wavFile = b''


        concatFile = []
        with open("transcript.txt",'r') as transFile:
            prevUser = 0
            prevTime = 0
            tmpStr = ''
            for line in transFile.readlines():
                splitLine = line.split('|')
                if len(splitLine) < 3:
                    continue
                curUsr = splitLine[0]
                curTxt = str(splitLine[1])
                curTime = splitLine[2]
                if prevUser == 0:
                    prevUser = curUsr
                    prevTime = curTime

                if prevUser == curUsr:
                    tmpStr = tmpStr + " " + curTxt
                else:
                    user = await bot.fetch_user(prevUser)
                    concatFile.append([prevTime,str(user.name) + '|' + str(tmpStr) + '|' + str(prevTime) + '\n'])
                    prevUser = curUsr
                    prevTime = curTime
                    tmpStr = curTxt
            user = await bot.fetch_user(prevUser)
            concatFile.append([prevTime,str(user.name) + '|' + str(tmpStr) + '|' + str(prevTime) + '\n'])

        print(concatFile)
        concatFile = sorted(concatFile, key=lambda x: x[0])
        with open("transcriptName.txt",'w', encoding="utf-8")as transFile:
            for line in concatFile:
                transFile.write(line[1])

        with open("transcriptName.txt", 'rb') as transFile:
            await channel.send("Your Transcript is:", file=discord.File(transFile, 'transcriptName.txt'))

        for file in os.listdir('./'):
            if 'wav' in file:
                os.system("del " + file)

        openai.api_key = "TODO API key"
        query = ''
        with open("transcriptName.txt", 'r') as transFile:
            for line in transFile.readlines():
                try:
                    splitline = line.split("|")
                    query = query + splitline[0] + ": " + splitline[1] + "\n"
                except:
                    pass
        myMessages = [{"role": "user", "content": 'Concisely summarize the following transcript in a bulleted format:\n' + query}]
        validResponseReceived = False
        retryAttempts = 0
        gptResponse = ''

        while not validResponseReceived and retryAttempts < 5:
            retryAttempts = retryAttempts + 1
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=myMessages
            )
            validResponseReceived = True
            gptResponse = completion.choices[0].message.content

        await channel.send(f"ChatGPT Summary of Audio Recording:\n" + str(gptResponse))  # Send a message with the accumulated files.
        usrcount = usrcount + 1
    except:
        print("FAILED TO POST PROCESS TRANSCRIPT")
        with open("transcript.txt", 'rb') as transFile:
            await channel.send("Failed while post-processing. Your Transcript is:", file=discord.File(transFile, 'transcript.txt'))


@bot.event
async def on_error(event, *args, **kwargs):
    # Add custom error handling here
    pass

@bot.event
async def on_command_error(ctx, error):
    # Handle command errors here
    pass

@bot.command()
async def join(ctx):
    print("Join")
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("You aren't in a voice channel!")
        return
    stream_sink.set_user(ctx.author.id)

    vc = await voice.channel.connect()  # Connect to the voice channel the author is in.

    connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.

    vc.start_recording(
        stream_sink,  # The sink type to use.
        once_done,  # What to do once done.
        ctx.channel  # The channel to disconnect from.
    )
    print("Start Recording")

    await ctx.respond("Started recording!")

@bot.command()
async def stop_recording(ctx):
    print("Stop Recording")
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        await ctx.guild.change_voice_state(channel=ctx.author.voice.channel, self_mute=False, self_deaf=True)
        print("Deafened")
        vc = connections[ctx.guild.id]
        vc.toggle_pause()
        vc.stop_recording()  # Stop recording, and call the callback (once_done).
        del connections[ctx.guild.id]  # Remove the guild from the cache.
        await ctx.delete()  # And delete.
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

@bot.command()
async def leave(ctx):
    print("Leave")
    await ctx.voice_client.disconnect()

bot.run(TOKEN)



# <GPLv3_Footer>
################################################################################
#                      Copyright (c) 2024 Nathan Ulmer.
################################################################################
# <\GPLv3_Footer>
