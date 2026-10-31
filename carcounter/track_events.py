import csv


class TrackObservationLog:
    fields = ("frame", "source_frame", "track_id", "event", "class", "previous_class",
              "last_seen_source_frame", "missing_frames", "bbox")

    def __init__(self, path, start_frame=1):
        self.offset = start_frame - 1
        self.seen = {}
        self.visible = set()
        self.stream = open(path, "w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.stream, fieldnames=self.fields)
        self.writer.writeheader()

    def update(self, frame, tracked_boxes):
        current = {int(row[4]): row for row in tracked_boxes}
        for track_id in sorted(self.visible - current.keys()):
            previous = self.seen[track_id]
            self._write(frame, track_id, "observation_lost", previous)
        for track_id, row in sorted(current.items()):
            previous = self.seen.get(track_id)
            record = dict(frame=frame, cls=row[5], bbox=" ".join(str(int(v)) for v in row[:4]))
            if previous is None:
                self._write(frame, track_id, "first_observation", record)
            else:
                if track_id not in self.visible:
                    self._write(frame, track_id, "observed_again", record, previous)
                if previous["cls"] != record["cls"]:
                    self._write(frame, track_id, "class_changed", record, previous)
            self.seen[track_id] = record
        self.visible = set(current)

    def _write(self, frame, track_id, event, record, previous=None):
        last = previous or record
        self.writer.writerow(dict(
            frame=frame, source_frame=frame + self.offset, track_id=track_id,
            event=event, **{"class": record["cls"]},
            previous_class=previous["cls"] if previous else "",
            last_seen_source_frame=last["frame"] + self.offset,
            missing_frames=max(0, frame - last["frame"] - (event != "observation_lost")),
            bbox=record["bbox"],
        ))

    def close(self):
        self.stream.close()
