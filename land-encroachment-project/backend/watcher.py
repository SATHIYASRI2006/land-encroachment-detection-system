import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app import process_plot_images   # we will create this next

DATA_FOLDER = "static/data"


class Handler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return

        if not event.src_path.endswith(".png"):
            return

        filename = os.path.basename(event.src_path)
        print("New file detected:", filename)

        try:
            plot_id = filename.split("_")[0]
            process_plot_images(plot_id)
        except Exception as e:
            print("Error:", e)


def start_watcher():
    observer = Observer()
    observer.schedule(Handler(), DATA_FOLDER, recursive=False)
    observer.start()

    print("REAL-TIME WATCHER STARTED")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()