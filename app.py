import logging
import logging.handlers
import os
import os.path
import time
from datetime import datetime
from multiprocessing import Lock, Process, Value, Queue
from multiprocessing.managers import SharedMemoryManager
from pathlib import Path

import yaml
from rich.progress import Progress, TextColumn

import darkcyan.camera_process
import darkcyan_utils.SignalMonitor as SignalMonitor
from darkcyan.config import Config

LOG_FILENAME = f'logs/vision-{datetime.now().strftime("%d%b%y")}-{os.getpid()}.log'
os.makedirs(os.path.dirname(LOG_FILENAME), exist_ok=True)
handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILENAME, when="midnight", backupCount=3
)
formatter = logging.Formatter(
    "%(asctime)-15s %(levelname)-6s %(message)s", "%c"
)
handler.setFormatter(formatter)
log = logging.getLogger("darkcyan")
log.addHandler(handler)
log.setLevel(logging.DEBUG)

class DarkCyanSourceConfig:

    def __init__(self, source_name, source_path, keep_running) -> None:

        self.source_name = source_name
        self.source_path = source_path
        self.buffer_lock = Lock()
        self.source_fps = Value("f")
        self.inference_fps = Value("f")        
        self.keep_running = keep_running

def run():

    with open(        
        Config.get_value("config_file"), "r"
    ) as f:
        app_config = yaml.load(f, Loader=yaml.FullLoader)

    video_sources = {}
    keep_running = Value("b", True)

    for source in app_config["sources"]:
        print(f"{source}: {app_config['sources'][source]['name']}")
        vsc = DarkCyanSourceConfig(
            app_config["sources"][source]["name"],
            app_config["sources"][source]["cv2_connection_string"],
            keep_running,
        )
        video_sources[source] = {"vs": vsc}
    
    signal_monitor = SignalMonitor.SignalMonitor()

    smm = SharedMemoryManager()    
    smm.start()

    results_queue = Queue(5)
    
    for source in video_sources:
        process_config = video_sources[source]["vs"]
        infer_shared_memory = smm.SharedMemory(size=1280 * 960 * 3)
        status_shared_memory = smm.SharedMemory(size=100)

        status = f"Initialising {process_config.source_name}..."

        status_shared_memory.buf[: len(status)] = status.encode("utf-8")
        status_shared_memory.buf[99] = len(status)

        video_sources[source]["ishm"] = infer_shared_memory
        video_sources[source]["shm_status"] = status_shared_memory

        process = Process(
            target=darkcyan.camera_process.run,
            args=[
                process_config.source_name,
                process_config.source_path,
                process_config.buffer_lock,
                process_config.source_fps,
                process_config.inference_fps,
                infer_shared_memory,
                status_shared_memory,
                results_queue,
                process_config.keep_running,
            ],
        )
        video_sources[source]["process"] = process

    start_time = time.time()
    run_for = 60 * 60

    progress = Progress(TextColumn("[progress.descriptions]{task.description}"))

    with progress:


        for source in video_sources:

            process = video_sources[source]["process"]
            video_sources[source]["task"] = progress.add_task(
                f"[blue]{video_sources[source]['vs'].source_name}", start=False
            )
            log.info(f"Starting Process {video_sources[source]['vs'].source_name}")
            process.start()
            log.info(f"Started Process {video_sources[source]['vs'].source_name}")

        while (
            ((time.time() - start_time) < run_for)
            and not signal_monitor.exit_now
            and keep_running.value
        ):

            #time.sleep(0.1)
            for source in video_sources:
                vsc = video_sources[source]["vs"]
                str_len = video_sources[source]["shm_status"].buf[99]
                update_txt = f"[green] Camera [green]{vsc.source_name}. [green] Status [green]{bytes(video_sources[source]['shm_status'].buf[:str_len]).decode('utf-8')  }.  " \
                    f"[blue] Source FPS: [blue] {vsc.source_fps.value:.2f}, [blue] Infer FPS: [blue] {vsc.inference_fps.value:.2f}"
                progress.update(video_sources[source]["task"], description=update_txt)

            if(not results_queue.empty()):
                final_result_categories, final_result_boxes = results_queue.get(block=False)
                log.info(f"Result: {final_result_categories}, {final_result_boxes}")
            else:
                time.sleep(0.1)

        keep_running.value = False
        time.sleep(2)
        smm.shutdown()


if __name__ == "__main__":
    log.info("Starting Process")
    run()
