import argparse, os, time, threading, asyncio, statistics
from datetime import datetime
import psutil
import pandas as pd

# Optional imports guarded
try:
    import requests
except Exception:
    requests = None

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

try:
    from aiocoap import Context, Message, POST
except Exception:
    Context = Message = POST = None

from tools.payload_gen import gen_payload

def now_ms():
    return time.perf_counter() * 1000.0

def simulate_delay(scenario: str):
    # emulate network conditions
    if scenario == "high_latency":
        time.sleep(0.150)
    elif scenario == "jittery":
        time.sleep(0.010)

def bench_http(payload, iterations, scenario, host, port):
    if requests is None:
        return None, "requests-not-installed"
    url = f"http://{host}:{port}/ingest"
    lat = []
    ok = 0
    for i in range(iterations):
        simulate_delay(scenario)
        data = {"seq": i, "payload": gen_payload(payload).decode("latin1")}
        t0 = now_ms()
        try:
            r = requests.post(url, json=data, timeout=2)
            if r.status_code == 200:
                ok += 1
            t1 = now_ms()
            lat.append(t1 - t0)
        except Exception:
            lat.append(2000.0)
    return {"lat": lat, "ok": ok, "sent": iterations}, None

def bench_mqtt(payload, iterations, scenario, host, port, topic, qos):
    if mqtt is None:
        return None, "mqtt-not-installed"
    recv = 0
    lat = []
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"bench-{int(time.time())}")
    ev = threading.Event()

    def on_message(c,u,msg):
        nonlocal recv
        t1 = now_ms()
        # We piggyback t0 in the payload length; simpler approach: measure roundtrip by subscriber loopback
        lat.append( t1 - float(msg.properties.UserProperty[0][1]) if (msg.properties and msg.properties.UserProperty) else 0.0 )
        recv += 1
        if recv >= iterations:
            ev.set()

    try:
        client.connect(host, port, keepalive=30)
    except Exception as e:
        return None, f"mqtt-connect-failed:{e}"
    client.on_message = on_message
    client.subscribe(topic, qos=qos)
    client.loop_start()

    for i in range(iterations):
        simulate_delay(scenario)
        props = mqtt.Properties(mqtt.PacketTypes.PUBLISH)
        props.UserProperty = [("t0", f"{now_ms()}")]
        payload_bytes = gen_payload(payload)
        client.publish(topic, payload_bytes, qos=qos, properties=props)

    ev.wait(timeout=5.0)
    client.loop_stop()
    client.disconnect()
    return {"lat": lat, "ok": recv, "sent": iterations}, None

async def _bench_coap_async(payload, iterations, scenario, host, port):
    context = await Context.create_client_context()
    uri = f"coap://{host}:{port}/telemetry"
    lat = []
    ok = 0
    for i in range(iterations):
        simulate_delay(scenario)
        data = gen_payload(payload)
        t0 = now_ms()
        try:
            req = Message(code=POST, uri=uri, payload=data)
            resp = await context.request(req).response
            ok += 1
            lat.append(now_ms() - t0)
        except Exception:
            lat.append(2000.0)
    await context.shutdown()
    return {"lat": lat, "ok": ok, "sent": iterations}

def bench_coap(payload, iterations, scenario, host, port):
    if Context is None:
        return None, "coap-not-installed"
    try:
        res = asyncio.run(_bench_coap_async(payload, iterations, scenario, host, port))
        return res, None
    except Exception as e:
        return None, f"coap-failed:{e}"

def summarize(protocol, scenario, payload, qos, res):
    lat = [x for x in res["lat"] if x>0]
    loss = max(0, 100.0 * (1 - (res["ok"]/max(1,res["sent"]))))
    p50 = (sorted(lat)[len(lat)//2]) if lat else None
    p95 = (sorted(lat)[int(len(lat)*0.95)-1]) if len(lat)>=1 else None
    mx  = max(lat) if lat else None
    thr = (res["ok"] / (sum(lat)/1000.0)) if lat and sum(lat)>0 else 0.0
    return {
        "protocol": protocol,
        "scenario": scenario,
        "payload_bytes": payload,
        "qos": qos,
        "iterations": len(lat),
        "latency_p50_ms": round(p50,2) if p50 else None,
        "latency_p95_ms": round(p95,2) if p95 else None,
        "latency_max_ms": round(mx,2) if mx else None,
        "throughput_msg_per_s": round(thr,2),
        "loss_percent": round(loss,2),
        "mean_payload_bytes": payload,
        "mean_overhead_bytes": None,
        "cpu_percent_client": psutil.Process().cpu_percent(interval=0.05),
        "cpu_percent_server": None,
        "timestamp": datetime.utcnow().isoformat()
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="results/metrics.csv")
    ap.add_argument("--protocols", nargs="*", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--iterations", type=int, default=50)
    args = ap.parse_args()

    if args.all or not args.protocols:
        protocols = ["HTTP","MQTT","COAP"]
    else:
        protocols = [p.upper() for p in args.protocols]

    payloads = [32, 1024, 10*1024]
    scenarios = ["normal","high_latency","jittery"]
    qos_list = [0,1,2]

    HOSTS = {
        "HTTP": (os.getenv("HTTP_HOST","127.0.0.1"), int(os.getenv("HTTP_PORT","5000"))),
        "MQTT": (os.getenv("MQTT_HOST","localhost"), int(os.getenv("MQTT_PORT","1883"))),
        "COAP": (os.getenv("COAP_HOST","127.0.0.1"), int(os.getenv("COAP_PORT","5683"))),
    }
    topic = os.getenv("MQTT_TOPIC","IOTS/LAB/telemetry")

    rows = []
    for proto in protocols:
        for scen in scenarios:
            for payload in payloads:
                qos_iter = qos_list if proto=="MQTT" else [None]
                for qos in qos_iter:
                    if proto=="HTTP":
                        res, err = bench_http(payload, args.iterations, scen, *HOSTS["HTTP"])
                    elif proto=="MQTT":
                        res, err = bench_mqtt(payload, args.iterations, scen, *HOSTS["MQTT"], topic, qos)
                    elif proto=="COAP":
                        res, err = bench_coap(payload, args.iterations, scen, *HOSTS["COAP"])
                    else:
                        res, err = None, "unknown-protocol"

                    if res is None:
                        print(f"[WARN] Skip {proto} scen={scen} payload={payload} qos={qos} reason={err}")
                        continue
                    rows.append(summarize(proto, scen, payload, qos, res))

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    import pandas as pd
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(args.output, index=False)
        print(f"[OK] wrote {args.output}")
    else:
        print("[WARN] no results produced")

if __name__ == "__main__":
    main()
