import asyncio
import logging
import threading
import json
import time
import mss
import cv2
import numpy as np
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate, RTCConfiguration, RTCIceServer
from av import VideoFrame

logger = logging.getLogger("ScreenStreamer")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("streamer_debug.log")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(fh)

class ScreenTrack(VideoStreamTrack):
    """
    A video stream track that captures the screen using mss
    and converts BGRA frames to YUV420p for WebRTC encoding.
    
    THE PURPOSE: Acts as the video source for the WebRTC connection, grabbing screenshots at a capped 15 FPS and converting them into a format WebRTC can easily send into the browser.
    THE REPLACEMENT: Replaced the old logic in ScreenStreamer that ran a fast loop to capture JPEGs, encode them in base64, and send them directly over WebSockets, which used too much CPU and bandwidth.
    """
    def __init__(self, screen_lock):
        super().__init__()
        self.screen_lock = screen_lock
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # Primary monitor
        self._is_closed = False

    def stop(self):
        super().stop()
        self._is_closed = True
        logger.info("ScreenTrack stopped, releasing memory and capture resources.")

    async def recv(self):
        if self._is_closed:
            raise Exception("ScreenTrack is closed")
            
        # Read the time of the last frame
        pts, time_base = await self.next_timestamp()

        try:
            with self.screen_lock:
                sct_img = self.sct.grab(self.monitor)
                frame = np.array(sct_img)  # Raw BGRA frame
        except Exception as e:
            logger.error(f"Capture failed: {e}")
            # Fallback to an empty frame if capture fails
            frame = np.zeros((self.monitor['height'], self.monitor['width'], 4), dtype=np.uint8)

        # 4. OS Permission Check
        # Check if the captured frame is completely empty
        if not np.any(frame):
            logger.critical("WARNING: Captured frame is 100% black. Check OS Screen Recording Permissions.")

        # 3. Resolution Standardization (Crucial to prevent WebRTC H.264/VP8 crash)
        # Resize to standard even width/height
        frame = cv2.resize(frame, (1280, 720))

        # Crucial Color Fix: Convert BGRA to YUV420p
        frame_yuv = cv2.cvtColor(frame, cv2.COLOR_BGRA2YUV_I420)
        
        # Create VideoFrame
        video_frame = VideoFrame.from_ndarray(frame_yuv, format="yuv420p")
        video_frame.pts = pts
        video_frame.time_base = time_base

        # CPU Throttling (Cap at 15 FPS -> ~66ms per frame)
        await asyncio.sleep(1 / 15)

        return video_frame

class ScreenStreamer(threading.Thread):
    def __init__(self, api_base_url, token, screen_lock):
        super().__init__()
        self.screen_lock = screen_lock
        self.daemon = True

        if api_base_url.startswith("https"):
            ws_url = api_base_url.replace("https", "wss")
        else:
            ws_url = api_base_url.replace("http", "ws")
            
        self.ws_url = f"{ws_url}/ws/ws?role=host&room_id=placeholder"  # room_id will be fixed below
        self.token = token
        self.running = False
        self.loop = None
        
        # We need the user's UUID for the room ID
        import base64
        try:
            # Decode JWT payload to get 'sub' (user_id)
            payload_b64 = self.token.split('.')[1]
            payload_padded = payload_b64 + '=' * (-len(payload_b64) % 4)
            payload_json = json.loads(base64.urlsafe_b64decode(payload_padded).decode('utf-8'))
            self.user_id = payload_json.get('sub')
        except Exception as e:
            logger.error(f"Failed to parse token for room_id: {e}")
            from config import Config
            self.user_id = Config.get_device_id()

        # THE PURPOSE: The desktop agent connects to the central signaling server strictly to receive the 'Offer' from the Admin and send back its 'Answer'.
        # THE REPLACEMENT: Replaced the old `/live` connection URL where the desktop sent non-stop image chunks.
        self.ws_url = f"{ws_url}/ws/ws?role=host&room_id={self.user_id}&token={self.token}"

    def run(self):
        self.running = True
        logger.info(f"WebRTC streamer thread started. Target: {self.ws_url}")
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        while self.running:
            try:
                self.loop.run_until_complete(self._connect_and_stream())
            except Exception as e:
                logger.error(f"Streamer loop error: {e}")
                time.sleep(5)  # Retry delay

    def stop(self):
        self.running = False
        logger.info("WebRTC streamer stopping...")
        # The 1-second timeout in asyncio.wait_for(ws.recv(), 1.0) will handle exiting cleanly
        # Calling loop.stop() here was throwing "RuntimeError: Event loop stopped before Future completed"

    async def _connect_and_stream(self):
        logger.info(f"Connecting to signaling server at {self.ws_url}")
        pc = None

        try:
            async with websockets.connect(self.ws_url) as ws:
                logger.info("Signaling WebSocket connected")
                
                while self.running:
                    try:
                        message_str = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        message = json.loads(message_str)
                        logger.debug(f"Received message type: {message.get('type')}")
                        
                        if message["type"] == "offer":
                            logger.info("Received WebRTC Offer. Initializing PeerConnection.")
                            if pc is not None:
                                for sender in pc.getSenders():
                                    if getattr(sender, "track", None):
                                        sender.track.stop()
                                await pc.close()
                            
                            # Create RTCPeerConnection with STUN and TURN configurations
                            iceServers = [
                                RTCIceServer(urls=["stun:stun.l.google.com:19302"])
                            ]
                            pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=iceServers))
                            
                            # Add Video Track
                            pc.addTrack(ScreenTrack(self.screen_lock))
                            
                            # Set ICE candidate handling
                            @pc.on("icecandidate")
                            async def on_icecandidate(event):
                                if event.candidate:
                                    # event.candidate in aiortc is an RTCIceCandidate object.
                                    # In aiortc, there is no .candidate string by default except by formatting
                                    # however sdp string representation is standard:
                                    from aiortc.sdp import candidate_to_sdp
                                    cand_str = candidate_to_sdp(event.candidate)
                                    await ws.send(json.dumps({
                                        "type": "ice_candidate",
                                        "candidate": cand_str,
                                        "sdpMid": event.candidate.sdpMid,
                                        "sdpMLineIndex": event.candidate.sdpMLineIndex
                                    }))

                            @pc.on("connectionstatechange")
                            async def on_connectionstatechange():
                                logger.info(f"WebRTC Connection State: {pc.connectionState}")
                                if pc.connectionState in ["failed", "closed", "disconnected"]:
                                    logger.warning("Connection closed/failed. Triggering full memory cleanup.")
                                    for sender in pc.getSenders():
                                        if getattr(sender, "track", None):
                                            sender.track.stop()
                                    await pc.close()

                            # Apply Offer
                            offer = RTCSessionDescription(sdp=message["sdp"], type=message["type"])
                            await pc.setRemoteDescription(offer)
                            
                            # Critical Fix for aiortc crashing on `None is not in list`
                            # if the browser omits direction in transceiver SDP.
                            for t in pc.getTransceivers():
                                if t._offerDirection is None:
                                    t._offerDirection = "sendrecv"
                            
                            # Create and Send Answer
                            answer = await pc.createAnswer()
                            await pc.setLocalDescription(answer)
                            await ws.send(json.dumps({
                                "type": pc.localDescription.type,
                                "sdp": pc.localDescription.sdp
                            }))
                            logger.info("Sent WebRTC Answer")
                            
                        elif message["type"] == "ice_candidate":
                            if pc and pc.remoteDescription:
                                from aiortc.sdp import candidate_from_sdp
                                candidate = candidate_from_sdp(message["candidate"])
                                candidate.sdpMid = message["sdpMid"]
                                candidate.sdpMLineIndex = message["sdpMLineIndex"]
                                await pc.addIceCandidate(candidate)
                                
                    except asyncio.TimeoutError:
                        pass # Loop back to check self.running

        except Exception as e:
            logger.exception("Signaling connection error:")
        finally:
            if pc:
                await pc.close()

def start_stream_service(api_base_url, token, screen_lock):
    streamer = ScreenStreamer(api_base_url, token, screen_lock)
    streamer.start()
    return streamer