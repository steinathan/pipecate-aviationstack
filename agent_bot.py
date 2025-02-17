import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frameworks.rtvi import (
    RTVIBotTranscriptionProcessor,
    RTVIConfig,
    RTVIMetricsProcessor,
    RTVIProcessor,
    RTVISpeakingProcessor,
    RTVIUserTranscriptionProcessor,
)
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport
from openai.types.chat import ChatCompletionToolParam
from pipecat.audio.mixers.soundfile_mixer import SoundfileMixer, MixerEnableFrame

from tools import make_flight_request

load_dotenv(override=True)
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


async def get_flight_details(
    function_name, tool_call_id, args, llm, context, result_callback
):
    logger.debug(f"Fetching data: {function_name}: {args}")
    data = await make_flight_request(args["flight_iata"])
    await result_callback(data)


tools = [
    ChatCompletionToolParam(
        type="function",
        function={
            "name": "get_flight_details",
            "description": "Use this tool when you want to get the flight details of a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_iata": {
                        "type": "string",
                        "description": "The IATA flight code (e.g., 'BA100' for British Airways Flight 100).",
                    },
                },
                "required": ["flight_iata"],
            },
        },
    )
]


async def load_ambient_sounds(filepath: str) -> dict[str, str]:
    files_mapping: dict[str, str] = {}
    for file in os.listdir(filepath):
        if os.path.isfile(os.path.join(filepath, file)):
            if file.endswith(".wav"):
                name = file.split(".")[0].replace(" ", "-")
                files_mapping[name] = os.path.join(filepath, file)
    return files_mapping


async def run_bot(room_url: str, token: str, loop: asyncio.AbstractEventLoop = None):
    ambient_sounds = await load_ambient_sounds(
        os.path.join(os.getcwd(), "ambient_sounds")
    )
    logger.info(f"Found Ambient Sounds: {ambient_sounds}")
    mixer = SoundfileMixer(
        sound_files=ambient_sounds,
        default_sound="airport-walk-through-zurich-international",  # list(ambient_sounds.keys())[0],
        volume=1.0,
    )

    transport = DailyTransport(
        room_url=room_url,
        token=token,
        bot_name="Jane",
        params=DailyParams(
            audio_out_enabled=True,
            camera_out_enabled=False,
            vad_enabled=True,
            audio_out_mixer=mixer,
            vad_analyzer=SileroVADAnalyzer(),
            transcription_enabled=True,
            vad_audio_passthrough=True,
        ),
    )

    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        voice_id="cgSgspJ2msm6clMCkdW9",
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o",
        # base_url="https://api.openai.com/v10",
    )

    llm.register_function(
        function_name="get_flight_details",
        callback=get_flight_details,
    )

    system_prompt = """
You are Jane, a flight status assistant for VoiceCab, a service that helps customers check their flight details quickly and efficiently using AI-powered voice assistance.
Your goal is to assist users by retrieving their flight information, providing real-time updates, and offering personalized support regarding their travel plans.

# Conversation Stages to Follow:
Introduction: Start by saying "Thanks for calling VoiceCab, how can I help?"
Inquiry Handling: Ask for their flight details—“uhh, what flight are you looking for?”—and confirm any key info.
Flight Status Update: Provide updates in a casual, helpful way—“so uhh, your flight is on time… yeah, no delays so far.” If there’s a delay, break it gently—“Emm, so, looks like your flight’s been pushed back a bit…”

# Additional Notes:
Keep responses short and natural, adding small pauses or fillers (“uhhh,” “eeemm,” “ummm,” “sooo,” “like”) to make it feel more human but don't excessively use it
Start the conversation with a casual greeting—no sales pitch right away.
Avoid sounding robotic—flow naturally as if you’re actually talking on a call.
"""
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
    ]

    # Set up conversation context and management
    # The context_aggregator will automatically collect conversation context
    context = OpenAILLMContext(messages=messages, tools=tools)  # type: ignore
    context_aggregator = llm.create_context_aggregator(context)

    # This will send `user-*-speaking` and `bot-*-speaking` messages.
    rtvi_speaking = RTVISpeakingProcessor()

    # This will emit UserTranscript events.
    rtvi_user_transcription = RTVIUserTranscriptionProcessor()

    # This will emit BotTranscript events.
    rtvi_bot_transcription = RTVIBotTranscriptionProcessor()

    # This will send `metrics` messages.
    rtvi_metrics: RTVIMetricsProcessor = RTVIMetricsProcessor()

    # Handles RTVI messages from the client
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))

    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            rtvi_speaking,
            rtvi_user_transcription,
            context_aggregator.user(),
            llm,
            rtvi_bot_transcription,
            tts,
            rtvi_metrics,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.set_bot_ready()

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        await transport.capture_participant_transcription(participant["id"])
        await task.queue_frames([context_aggregator.user().get_context_frame()])
        await task.queue_frame(MixerEnableFrame(True))

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        logger.warning(f"Participant left: {participant}")
        await task.cancel()
        logger.warning("Task cancelled")

    runner = PipelineRunner()
    await runner.run(task)


async def run_in_background(room_url: str, token: str):
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    loop.create_task(run_bot(room_url, token, loop))
