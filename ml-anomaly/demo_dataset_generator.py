import csv
import math
import random
from pathlib import Path

out_dir = Path("../sample-data")
out_dir.mkdir(exist_ok=True)

def generate(path: Path, fault: bool = False):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "latency_ms", "cpu_percent", "memory_percent", "packet_loss_percent"])
        for i in range(240):
            latency = 40 + math.sin(i / 12) * 5 + random.uniform(-2, 2)
            cpu = 25 + math.sin(i / 20) * 6 + random.uniform(-3, 3)
            mem = 50 + math.sin(i / 25) * 3 + random.uniform(-2, 2)
            loss = max(0, random.uniform(0, 0.4))

            if fault and i > 170:
                latency += random.uniform(80, 160)
                cpu += random.uniform(30, 55)
                mem += random.uniform(15, 35)
                loss += random.uniform(3, 12)

            writer.writerow([i, round(latency, 2), round(cpu, 2), round(mem, 2), round(loss, 2)])

generate(out_dir / "normal_telemetry.csv", fault=False)
generate(out_dir / "fault_telemetry.csv", fault=True)
print("Sample datasets generated.")
