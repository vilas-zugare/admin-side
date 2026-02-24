import asyncio
import websockets
import json

async def trigger():
    uri = "ws://localhost:8000/api/v1/ws/ws?role=viewer&room_id=0bfe9f83-1225-43d7-9cdd-92886846778c&token=ey..."
    print("Connecting viewer...")
    # Get a fresh token to connect
    import requests
    resp = requests.post("http://localhost:8000/api/v1/auth/login", json={"email":"admin@example.com", "password":"admin", "device_id":"TEST"})
    token = resp.json()["access_token"]
    uri = f"ws://localhost:8000/api/v1/ws/ws?role=viewer&room_id=0bfe9f83-1225-43d7-9cdd-92886846778c&token={token}"
    
    async with websockets.connect(uri) as ws:
        # Mock SDP Offer
        offer = {
            "type": "offer",
            "sdp": "v=0\r\no=- 4209148705051918451 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\n"
        }
        await ws.send(json.dumps(offer))
        print("Offer sent. Waiting for answer...")
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print("Received:", msg)

asyncio.run(trigger())
