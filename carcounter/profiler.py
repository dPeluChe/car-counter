import time

class Profiler:
    def __init__(self):
        self.stages = ["detection", "tracking", "counting", "visualization", "writing"]
        self.stats = {stage: [] for stage in self.stages}
        self.start_times = {}

    def start(self, stage):
        self.start_times[stage] = time.perf_counter()

    def end(self, stage):
        if stage in self.start_times:
            elapsed = time.perf_counter() - self.start_times[stage]
            self.stats[stage].append(elapsed)
            del self.start_times[stage]

    def get_averages(self):
        return {stage: sum(times) / len(times) if times else 0 for stage, times in self.stats.items()}
