import asyncio
import websockets
import json

async def test():
    async with websockets.connect('ws://127.0.0.1:8000/ws') as ws:
        # Send what EnvClient sends
        msg = '{"type": "reset", "data": {"category": "refund"}}'
        await ws.send(msg)
        response_raw = await ws.recv()
        
        response = json.loads(response_raw)
        
        # Simulate what EnvClient.reset does.
        payload = response.get("data", {})
        obs_data = payload.get("observation", {})
        ticket_data = obs_data.get("ticket_info", {})
        
        print("payload (obs_data):", type(payload))
        print("ticket_data:", ticket_data)
        
        # Try creating TicketInfo manually
        from models import TicketInfo
        ti = TicketInfo(**ticket_data)
        print("TicketInfo created:", ti)

asyncio.run(test())
