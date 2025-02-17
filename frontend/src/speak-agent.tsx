import { RTVIClient, RTVIEvent, RTVIMessage } from "@pipecat-ai/client-js"
import {
  RTVIClientProvider,
  RTVIClientAudio,
  useRTVIClient,
  useRTVIClientEvent,
  useRTVIClientTransportState,
} from "@pipecat-ai/client-react"
import { DailyTransport } from "@pipecat-ai/daily-transport"
import { Mic, MicOff, Loader2 } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

function Button({
  children,
  className,
  onClick,
  disabled,
}: {
  children: React.ReactNode
  size?: "sm" | "md" | "lg"
  variant?: "default" | "outline"
  className?: string
  onClick?: () => void
  disabled?: boolean
}) {
  return (
    <button
      className={`flex items-center justify-center rounded-full relative ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}

// Create the client instance
const client = new RTVIClient({
  params: {
    baseUrl: import.meta.env["VITE_APP_API_URL"] + "/call",
    requestData: {},
    endpoint: {
      connect: "/call/connect",
    },
  },
  transport: new DailyTransport(),
  enableMic: true,
})

export function FlightVoiceAgent() {
  return (
    <RTVIClientProvider client={client}>
      <VoiceBot />
      <RTVIClientAudio />
    </RTVIClientProvider>
  )
}

function VoiceBot() {
  const voiceClient = useRTVIClient()
  const transportState = useRTVIClientTransportState()

  const [appState, setAppState] = useState<
    "idle" | "ready" | "connecting" | "connected" | "active"
  >("idle")

  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef<boolean>(false)

  useRTVIClientEvent(
    RTVIEvent.Error,
    useCallback((message: RTVIMessage) => {
      const errorData = message.data as { error: string; fatal: boolean }
      if (errorData.fatal) {
        setError(errorData.error)
      }
    }, [])
  )

  useEffect(() => {
    console.log("Transport state:", transportState)
    switch (transportState) {
      case "initialized":
      case "disconnected":
        setAppState("ready")
        break
      case "authenticating":
      case "connecting":
        setAppState("connecting")
        break
      case "connected":
        setAppState("connected")
        break
      case "ready":
        setAppState("active")
        break
      default:
        setAppState("idle")
    }
  }, [transportState])

  const handleConnect = useCallback(() => {
    if (voiceClient) {
      voiceClient.initDevices()
      voiceClient.connect()
      mountedRef.current = true
    }
  }, [voiceClient])

  const handleDisconnect = useCallback(() => {
    if (voiceClient) {
      voiceClient.disconnect()
      setAppState("ready")
    }
  }, [voiceClient])

  if (error) {
    return (
        <div>an error occurred</div>
    )
  }

  const isConnecting = appState === "connecting"
  const isConnected = appState === "connected"
  const isActive = appState === "active"

  return (
    <div className="relative">
      <div className="absolute inset-0 opacity-25">
        {[...Array(50)].map((_, i) => (
          <div
            key={i}
            className="absolute w-5 h-px bg-emerald-400 rounded-full animate-twinkle"
            style={{
              top: `${Math.random() * 100}%`,
              left: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 2}s`,
            }}
          />
        ))}
      </div>

      <div className="relative z-10 p-2 flex flex-col items-center gap-6">
        {/* Microphone Button */}
        <div className="relative">
          <Button
            variant={isActive ? "default" : "outline"}
            className={`h-16 w-16 rounded-full relative  ${
              isActive
                ? "hover:bg-emerald-600 cursor-progress bg-red-500"
                : "border-emerald-500/50 hover:bg-emerald-500/10 cursor-pointer"
            }`}
            onClick={isActive ? handleDisconnect : handleConnect}
            disabled={isConnecting || isConnected}
          >
            {isConnecting || isConnected ? (
              <Loader2 className="h-6 w-6 animate-spin text-emerald-400" />
            ) : isActive ? (
              <MicOff className="h-6 w-6 " />
            ) : (
              <Mic className="h-6 w-6 text-emerald-400" />
            )}
          </Button>
        </div>

        <div className="text-center space-y-2">
          <h3 className="text-lg font-semibold text-white">
            {isConnecting
              ? "Connecting to AI Agent..."
              : isConnected
                ? "Preparing AI Agent..."
                : isActive
                  ? "Ready (Click to disconnect)"
                  : "Talk to Our AI Agent"}
          </h3>
          <p className="text-sm text-zinc-400">
            {isConnecting
              ? "Connecting..."
              : isConnected
                ? " Waiting for the AI agent to be ready."
                : isActive
                  ? "Start Talking naturally - Click the microphone to end the call."
                  : "Click the microphone to start a conversation"}
          </p>
        </div>

        {(isConnecting || isConnected || isActive) && (
          <div className="flex items-center gap-2 text-xs text-emerald-400">
            <div
              className={`h-2 w-2 rounded-full ${isActive ? "bg-emerald-400" : "bg-emerald-400/50 animate-pulse"}`}
            />
            {isActive
              ? "Agent Ready"
              : isConnected
                ? "Agent Preparing"
                : "Connecting"}
          </div>
        )}
      </div>
    </div>
  )
}
