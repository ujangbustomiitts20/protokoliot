#!/usr/bin/env python3
"""
Payload Generator - Generate payload dengan ukuran tertentu
Support binary dan text payload, dengan base64 encoding untuk HTTP
"""

import json
import base64
import random
import string
from datetime import datetime


def generate_random_string(length):
    """Generate random string dengan panjang tertentu"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_random_bytes(length):
    """Generate random bytes dengan panjang tertentu"""
    return bytes([random.randint(0, 255) for _ in range(length)])


def generate_sensor_data(target_size_bytes, data_type='json'):
    """
    Generate data sensor dengan ukuran mendekati target
    
    Args:
        target_size_bytes: Target ukuran payload dalam bytes
        data_type: Tipe data ('json', 'binary', 'text')
        
    Returns:
        Payload dalam format yang diminta
    """
    if data_type == 'binary':
        # Generate binary data
        return generate_random_bytes(target_size_bytes)
    
    elif data_type == 'text':
        # Generate plain text
        return generate_random_string(target_size_bytes)
    
    else:  # JSON (default)
        # Base sensor data
        base_data = {
            "device_id": "sensor_001",
            "timestamp": datetime.now().isoformat(),
            "sensors": {
                "temperature": round(random.uniform(20.0, 30.0), 2),
                "humidity": round(random.uniform(40.0, 80.0), 2),
                "pressure": round(random.uniform(1000.0, 1020.0), 2),
                "light": random.randint(0, 1000),
                "motion": random.choice([True, False])
            },
            "location": {
                "latitude": round(random.uniform(-90.0, 90.0), 6),
                "longitude": round(random.uniform(-180.0, 180.0), 6),
                "altitude": round(random.uniform(0.0, 1000.0), 2)
            },
            "status": "active",
            "battery": random.randint(0, 100)
        }
        
        # Calculate current size
        base_json = json.dumps(base_data)
        current_size = len(base_json.encode('utf-8'))
        
        # Pad jika masih kurang
        if current_size < target_size_bytes:
            padding_size = target_size_bytes - current_size - 30  # Reserve for JSON overhead
            if padding_size > 0:
                base_data['padding'] = generate_random_string(padding_size)
        
        return base_data


def payload_to_base64(payload):
    """Convert payload ke base64 string (untuk HTTP binary)"""
    if isinstance(payload, bytes):
        return base64.b64encode(payload).decode('utf-8')
    elif isinstance(payload, str):
        return base64.b64encode(payload.encode('utf-8')).decode('utf-8')
    elif isinstance(payload, dict):
        json_str = json.dumps(payload)
        return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    else:
        raise ValueError("Unsupported payload type")


def get_payload_size(payload):
    """Hitung ukuran payload dalam bytes"""
    if isinstance(payload, bytes):
        return len(payload)
    elif isinstance(payload, str):
        return len(payload.encode('utf-8'))
    elif isinstance(payload, dict):
        return len(json.dumps(payload).encode('utf-8'))
    else:
        return 0


def main():
    """Test payload generator"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate test payload')
    parser.add_argument('--size', type=int, default=1024,
                       help='Target payload size in bytes')
    parser.add_argument('--type', choices=['json', 'binary', 'text'], default='json',
                       help='Payload type')
    parser.add_argument('--output', help='Output file (optional)')
    parser.add_argument('--base64', action='store_true',
                       help='Encode as base64')
    
    args = parser.parse_args()
    
    # Generate payload
    payload = generate_sensor_data(args.size, args.type)
    
    # Convert to base64 if requested
    if args.base64:
        output = payload_to_base64(payload)
    else:
        if isinstance(payload, dict):
            output = json.dumps(payload, indent=2)
        elif isinstance(payload, bytes):
            output = payload
        else:
            output = payload
    
    # Print or save
    if args.output:
        mode = 'wb' if isinstance(output, bytes) else 'w'
        with open(args.output, mode) as f:
            f.write(output)
        print(f"Payload saved to {args.output}")
    else:
        if isinstance(output, bytes):
            print(f"Binary payload ({len(output)} bytes)")
            print(f"First 100 bytes: {output[:100]}")
        else:
            print(output)
    
    # Show size
    actual_size = get_payload_size(payload)
    print(f"\nActual size: {actual_size} bytes (target: {args.size} bytes)")


if __name__ == "__main__":
    main()
