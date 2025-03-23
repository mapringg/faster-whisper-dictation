#!/usr/bin/env python3
import argparse
import time
from datetime import datetime

import matplotlib.pyplot as plt
import psutil


def get_process_memory(pid):
    """Get memory usage of a process in MB"""
    try:
        process = psutil.Process(pid)
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # Convert bytes to MB
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def monitor_process(pid, duration=300, interval=1):
    """Monitor memory usage of a process for specified duration"""
    print(f"Monitoring process {pid} for {duration} seconds...")
    start_time = time.time()
    end_time = start_time + duration

    timestamps = []
    memory_usage = []

    while time.time() < end_time:
        current_time = time.time() - start_time
        memory = get_process_memory(pid)

        if memory is None:
            print(f"Process {pid} no longer exists")
            break

        timestamps.append(current_time)
        memory_usage.append(memory)

        print(f"Time: {current_time:.2f}s, Memory: {memory:.2f} MB")
        time.sleep(interval)

    return timestamps, memory_usage


def plot_memory_usage(timestamps, memory_usage, pid, output_file=None):
    """Plot memory usage over time"""
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, memory_usage)
    plt.title(f"Memory Usage for Process {pid}")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Memory Usage (MB)")
    plt.grid(True)

    if output_file:
        plt.savefig(output_file)
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def find_pid_by_name(process_name):
    """Find process ID by name"""
    for proc in psutil.process_iter(["pid", "name"]):
        if process_name.lower() in proc.info["name"].lower():
            return proc.info["pid"]
    return None


def main():
    parser = argparse.ArgumentParser(description="Monitor memory usage of a process")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pid", type=int, help="Process ID to monitor")
    group.add_argument("--name", type=str, help="Process name to monitor")
    parser.add_argument(
        "--duration", type=int, default=300, help="Duration to monitor in seconds"
    )
    parser.add_argument(
        "--interval", type=float, default=1, help="Sampling interval in seconds"
    )
    parser.add_argument("--output", type=str, help="Output file for the plot")

    args = parser.parse_args()

    if args.name:
        pid = find_pid_by_name(args.name)
        if pid is None:
            print(f"No process matching '{args.name}' found")
            return
    else:
        pid = args.pid

    try:
        timestamps, memory_usage = monitor_process(pid, args.duration, args.interval)

        if len(timestamps) > 1:
            output_file = (
                args.output
                or f"memory_usage_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            plot_memory_usage(timestamps, memory_usage, pid, output_file)

            # Calculate statistics
            min_mem = min(memory_usage)
            max_mem = max(memory_usage)
            avg_mem = sum(memory_usage) / len(memory_usage)

            print("\nMemory Usage Statistics:")
            print(f"Minimum: {min_mem:.2f} MB")
            print(f"Maximum: {max_mem:.2f} MB")
            print(f"Average: {avg_mem:.2f} MB")
            print(f"Growth: {max_mem - min_mem:.2f} MB")

            if max_mem > min_mem * 1.5:
                print(
                    "\nWARNING: Significant memory growth detected - possible memory leak!"
                )
        else:
            print("Not enough data points collected to analyze memory usage")

    except KeyboardInterrupt:
        print("\nMonitoring interrupted by user")


if __name__ == "__main__":
    main()
