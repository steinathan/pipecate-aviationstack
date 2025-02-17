import './App.css'
import {FlightVoiceAgent} from "./speak-agent.tsx";

function App() {

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-900">
        <FlightVoiceAgent/>
        <small className="absolute bottom-5 right-5 text-gray-500"><a className="underline" href="https://www.linkedin.com/in/navicstein/">Demo By Navicstein</a></small>
    </div>
  )
}

export default App
