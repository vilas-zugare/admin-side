import asyncio
import websockets
import json

async def test_signaling():
    uri_host = "ws://localhost:8000/api/v1/ws/ws?role=host&room_id=test_user_id"
    uri_viewer = "ws://localhost:8000/api/v1/ws/ws?role=viewer&room_id=test_user_id"
    
    async with websockets.connect(uri_host) as host_ws, websockets.connect(uri_viewer) as viewer_ws:
        print("Both connected to room: test_user_id")
        
        # Viewer sends an offer
        offer = {"type": "offer", "sdp": "v=0\r\n..."}
        await viewer_ws.send(json.dumps(offer))
        print(f"Viewer sent: {offer}")
        
        # Host should receive the offer
        host_msg = await host_ws.recv()
        print(f"Host received: {host_msg}")
        
        # Host sends an answer
        answer = {"type": "answer", "sdp": "v=0\r\n..."}
        await host_ws.send(json.dumps(answer))
        print(f"Host sent: {answer}")
        
        # Viewer should receive the answer
        viewer_msg = await viewer_ws.recv()
        print(f"Viewer received: {viewer_msg}")

if __name__ == "__main__":
    asyncio.run(test_signaling())
