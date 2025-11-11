#!/usr/bin/env python3
"""
CoAP Server - Menerima data melalui CoAP protocol
Menggunakan aiocoap untuk resource /telemetry
"""

import asyncio
import aiocoap
import aiocoap.resource as resource
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('CoAP_Server')


class TelemetryResource(resource.Resource):
    """CoAP Resource untuk telemetri IoT"""
    
    def __init__(self):
        super().__init__()
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_bytes': 0,
            'start_time': time.time()
        }
    
    async def render_get(self, request):
        """
        Handle GET request - return statistics
        """
        uptime = time.time() - self.stats['start_time']
        stats_copy = self.stats.copy()
        stats_copy['uptime_seconds'] = uptime
        
        if uptime > 0:
            stats_copy['requests_per_second'] = stats_copy['total_requests'] / uptime
        
        payload = json.dumps(stats_copy, indent=2)
        
        logger.info("GET request - returning statistics")
        
        return aiocoap.Message(
            code=aiocoap.CONTENT,
            payload=payload.encode('utf-8')
        )
    
    async def render_post(self, request):
        """
        Handle POST request - receive telemetry data
        """
        try:
            # Get payload
            payload = request.payload
            payload_size = len(payload)
            
            # Update statistics
            self.stats['total_requests'] += 1
            self.stats['total_bytes'] += payload_size
            
            # Try to decode as JSON
            try:
                payload_str = payload.decode('utf-8')
                data = json.loads(payload_str)
                device_id = data.get('device_id', 'unknown')
                
                logger.info(f"POST request from {device_id} - {payload_size} bytes")
                logger.debug(f"Data: {json.dumps(data, indent=2)}")
                
                self.stats['successful_requests'] += 1
                
                # Return success response
                response_data = {
                    'status': 'success',
                    'message': 'Data received',
                    'device_id': device_id,
                    'timestamp': datetime.now().isoformat(),
                    'bytes_received': payload_size
                }
                
                return aiocoap.Message(
                    code=aiocoap.CHANGED,
                    payload=json.dumps(response_data).encode('utf-8')
                )
                
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Invalid payload format: {e}")
                self.stats['failed_requests'] += 1
                
                return aiocoap.Message(
                    code=aiocoap.BAD_REQUEST,
                    payload=b'Invalid payload format'
                )
        
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.stats['failed_requests'] += 1
            
            return aiocoap.Message(
                code=aiocoap.INTERNAL_SERVER_ERROR,
                payload=b'Internal server error'
            )


class StatsResource(resource.Resource):
    """Resource untuk statistik server"""
    
    def __init__(self, telemetry_resource):
        super().__init__()
        self.telemetry_resource = telemetry_resource
    
    async def render_get(self, request):
        """Return server statistics"""
        stats = self.telemetry_resource.stats
        uptime = time.time() - stats['start_time']
        
        stats_data = {
            'total_requests': stats['total_requests'],
            'successful_requests': stats['successful_requests'],
            'failed_requests': stats['failed_requests'],
            'total_bytes': stats['total_bytes'],
            'uptime_seconds': uptime,
            'requests_per_second': stats['total_requests'] / uptime if uptime > 0 else 0
        }
        
        payload = json.dumps(stats_data, indent=2)
        
        return aiocoap.Message(
            code=aiocoap.CONTENT,
            payload=payload.encode('utf-8')
        )


async def main():
    """Main function"""
    host = os.getenv('COAP_HOST', '0.0.0.0')
    port = int(os.getenv('COAP_PORT', 5683))
    
    # Create root resource
    root = resource.Site()
    
    # Add telemetry resource
    telemetry_resource = TelemetryResource()
    root.add_resource(['telemetry'], telemetry_resource)
    
    # Add stats resource
    stats_resource = StatsResource(telemetry_resource)
    root.add_resource(['stats'], stats_resource)
    
    # Bind to address
    bind_address = (host, port)
    
    logger.info(f"Starting CoAP server on {host}:{port}")
    logger.info(f"Resources:")
    logger.info(f"  coap://{host}:{port}/telemetry - POST telemetry data, GET statistics")
    logger.info(f"  coap://{host}:{port}/stats      - GET server statistics")
    
    # Create server context
    await aiocoap.Context.create_server_context(root, bind=bind_address)
    
    # Run forever
    logger.info("CoAP server running. Press Ctrl+C to stop...")
    await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
