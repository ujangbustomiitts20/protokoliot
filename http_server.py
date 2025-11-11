#!/usr/bin/env python3
"""
HTTP Server - Menerima data melalui HTTP REST API
Menggunakan Flask untuk endpoint /ingest
"""

from flask import Flask, request, jsonify
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import time
from threading import Lock

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('HTTP_Server')

# Create Flask app
app = Flask(__name__)

# Statistics
stats = {
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'total_bytes': 0,
    'start_time': time.time(),
    'requests_per_second': 0.0
}
stats_lock = Lock()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': time.time() - stats['start_time']
    }), 200


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get server statistics"""
    with stats_lock:
        uptime = time.time() - stats['start_time']
        current_stats = stats.copy()
        current_stats['uptime_seconds'] = uptime
        
        if uptime > 0:
            current_stats['requests_per_second'] = current_stats['total_requests'] / uptime
        
        return jsonify(current_stats), 200


@app.route('/ingest', methods=['POST'])
def ingest_data():
    """
    Endpoint utama untuk menerima data IoT
    
    Expected JSON format:
    {
        "device_id": "sensor_001",
        "timestamp": "2025-01-01T12:00:00",
        "payload": {...}  // or string
    }
    """
    try:
        # Get request data
        if not request.is_json:
            logger.warning("Received non-JSON request")
            with stats_lock:
                stats['failed_requests'] += 1
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        
        # Validate required fields
        if not data or 'device_id' not in data:
            logger.warning("Missing required field: device_id")
            with stats_lock:
                stats['failed_requests'] += 1
            return jsonify({'error': 'device_id is required'}), 400
        
        # Get payload size
        payload_size = len(request.data)
        
        # Update statistics
        with stats_lock:
            stats['total_requests'] += 1
            stats['successful_requests'] += 1
            stats['total_bytes'] += payload_size
        
        # Log received data
        logger.info(f"Received data from {data.get('device_id')} - {payload_size} bytes")
        logger.debug(f"Data: {json.dumps(data, indent=2)}")
        
        # Return success response
        return jsonify({
            'status': 'success',
            'message': 'Data received',
            'device_id': data.get('device_id'),
            'timestamp': datetime.now().isoformat(),
            'bytes_received': payload_size
        }), 200
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        with stats_lock:
            stats['failed_requests'] += 1
        return jsonify({'error': 'Invalid JSON format'}), 400
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        with stats_lock:
            stats['failed_requests'] += 1
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/reset', methods=['POST'])
def reset_stats():
    """Reset server statistics"""
    with stats_lock:
        stats['total_requests'] = 0
        stats['successful_requests'] = 0
        stats['failed_requests'] = 0
        stats['total_bytes'] = 0
        stats['start_time'] = time.time()
        stats['requests_per_second'] = 0.0
    
    logger.info("Statistics reset")
    return jsonify({'status': 'success', 'message': 'Statistics reset'}), 200


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500


def main():
    """Main function"""
    host = os.getenv('HTTP_HOST', 'localhost')
    port = int(os.getenv('HTTP_PORT', 8080))
    
    logger.info(f"Starting HTTP server on {host}:{port}")
    logger.info(f"Endpoints:")
    logger.info(f"  POST   http://{host}:{port}/ingest  - Ingest IoT data")
    logger.info(f"  GET    http://{host}:{port}/health  - Health check")
    logger.info(f"  GET    http://{host}:{port}/stats   - Server statistics")
    logger.info(f"  POST   http://{host}:{port}/reset   - Reset statistics")
    
    # Run server
    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True
    )


if __name__ == "__main__":
    main()
