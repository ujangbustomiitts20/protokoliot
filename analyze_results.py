import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv("results/metrics.csv")

# Ringkas p95 latency & throughput
summary = df.groupby(["protocol","scenario","payload_bytes"], as_index=False)[["latency_p95_ms","throughput_msg_per_s","loss_percent"]].mean()
summary.to_csv("results/summary.csv", index=False)

# Plot latency p95
plt.figure()
for proto in sorted(df['protocol'].dropna().unique()):
    sub = df[df['protocol']==proto]
    plt.plot(range(len(sub)), sub['latency_p95_ms'])
plt.title("Latency p95 per entry (urut input)")
plt.xlabel("entry")
plt.ylabel("latency p95 (ms)")
plt.savefig("results/plot_latency.png", bbox_inches="tight")
plt.close()

# Plot throughput
plt.figure()
for proto in sorted(df['protocol'].dropna().unique()):
    sub = df[df['protocol']==proto]
    plt.plot(range(len(sub)), sub['throughput_msg_per_s'])
plt.title("Throughput per entry (urut input)")
plt.xlabel("entry")
plt.ylabel("throughput (msg/s)")
plt.savefig("results/plot_throughput.png", bbox_inches="tight")
plt.close()

rec = '''# Rekomendasi Pemilihan Protokol

- **MQTT**: Telemetry berkala, perangkat banyak, jaringan tidak stabil; perlu QoS/retain/last-will; cocok untuk pub/sub.
- **HTTP**: Integrasi dengan web/API dan pipeline analitik; cocok untuk operasi idempotent atau konfigurasi; monitoring HTTP melimpah.
- **CoAP**: Perangkat sangat terbatas (constrained), jaringan UDP, kebutuhan header kecil; dukungan observe untuk push ringan.
'''
with open("results/recommendations.md","w") as f:
    f.write(rec)

print("Created: results/summary.csv, results/plot_latency.png, results/plot_throughput.png, results/recommendations.md")
