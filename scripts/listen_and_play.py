import argparse
import socket
import sys
import threading
from dataclasses import dataclass, field
from queue import Empty, Queue


@dataclass
class ListenAndPlayArguments:
    send_rate: int = field(default=16000, metadata={"help": "In Hz. Default is 16000."})
    recv_rate: int = field(default=16000, metadata={"help": "In Hz. Default is 16000."})
    list_play_chunk_size: int = field(
        default=1024,
        metadata={"help": "The size of data chunks (in bytes). Default is 1024."},
    )
    host: str = field(
        default="localhost",
        metadata={
            "help": "The hostname or IP address for listening and playing. Default is 'localhost'."
        },
    )
    send_port: int = field(
        default=12345,
        metadata={"help": "The network port for sending data. Default is 12345."},
    )
    recv_port: int = field(
        default=12346,
        metadata={"help": "The network port for receiving data. Default is 12346."},
    )
    dry_run: bool = field(
        default=False,
        metadata={"help": "Print the resolved connection plan without connecting or opening audio devices."},
    )


def _print_dry_run(
    send_rate: int,
    recv_rate: int,
    list_play_chunk_size: int,
    host: str,
    send_port: int,
    recv_port: int,
) -> None:
    print("Dry run: TCP audio connection plan")
    print(f"  Host: {host}")
    print(f"  Send port: {send_port}")
    print(f"  Receive port: {recv_port}")
    print(f"  Audio: input {send_rate} Hz, output {recv_rate} Hz, chunk {list_play_chunk_size} samples")


def _connect_socket(label: str, host: str, port: int) -> socket.socket:
    try:
        connection = socket.create_connection((host, port), timeout=3.0)
    except OSError as exc:
        print(f"ERROR: unable to connect {label} socket to {host}:{port}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    connection.settimeout(None)
    return connection


def listen_and_play(
    send_rate=16000,
    recv_rate=16000,
    list_play_chunk_size=1024,
    host="localhost",
    send_port=12345,
    recv_port=12346,
    dry_run=False,
):
    if dry_run:
        _print_dry_run(
            send_rate,
            recv_rate,
            list_play_chunk_size,
            host,
            send_port,
            recv_port,
        )
        return

    send_socket = _connect_socket("send", host, send_port)
    try:
        recv_socket = _connect_socket("receive", host, recv_port)
    except SystemExit:
        send_socket.close()
        raise

    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        send_socket.close()
        recv_socket.close()
        print(f"ERROR: missing runtime dependency: {exc.name}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("Recording and streaming...")

    stop_event = threading.Event()
    recv_queue = Queue()
    send_queue = Queue()

    # Pre-generate a static dither buffer (±1 LSB, -96 dB) to keep the audio
    # sink active without calling numpy inside the real-time audio callback.
    dither_bytes = np.random.randint(
        -1, 2, size=list_play_chunk_size, dtype=np.int16
    ).tobytes()

    def callback_recv(outdata, frames, time, status):
        if not recv_queue.empty():
            data = recv_queue.get()
            outdata[: len(data)] = data
            outdata[len(data) :] = b"\x00" * (len(outdata) - len(data))
        else:
            outdata[:] = dither_bytes

    def callback_send(indata, frames, time, status):
        if recv_queue.empty():
            send_queue.put(bytes(indata))

    def send(stop_event, send_queue):
        while not stop_event.is_set():
            try:
                data = send_queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                send_socket.sendall(data)
            except OSError:
                stop_event.set()
                break

    def recv(stop_event, recv_queue):
        def receive_full_chunk(conn, chunk_size):
            data = b""
            while len(data) < chunk_size:
                try:
                    packet = conn.recv(chunk_size - len(data))
                except OSError:
                    return None
                if not packet:
                    return None
                data += packet
            return data

        while not stop_event.is_set():
            data = receive_full_chunk(recv_socket, list_play_chunk_size * 2)
            if data is None:
                stop_event.set()
                break
            recv_queue.put(data)

    send_stream = None
    recv_stream = None
    send_thread = None
    recv_thread = None
    try:
        send_stream = sd.RawInputStream(
            samplerate=send_rate,
            channels=1,
            dtype="int16",
            blocksize=list_play_chunk_size,
            callback=callback_send,
        )
        recv_stream = sd.RawOutputStream(
            samplerate=recv_rate,
            channels=1,
            dtype="int16",
            blocksize=list_play_chunk_size,
            callback=callback_recv,
        )
        send_stream.start()
        recv_stream.start()

        send_thread = threading.Thread(target=send, args=(stop_event, send_queue))
        recv_thread = threading.Thread(target=recv, args=(stop_event, recv_queue))
        send_thread.start()
        recv_thread.start()

        input("Press Enter to stop...")

    except KeyboardInterrupt:
        print("Finished streaming.")

    finally:
        stop_event.set()
        for connection in (send_socket, recv_socket):
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for thread in (send_thread, recv_thread):
            if thread is not None:
                thread.join()
        for stream in (send_stream, recv_stream):
            if stream is not None:
                stream.stop()
                stream.close()
        send_socket.close()
        recv_socket.close()
        print("Connection closed.")


def _parse_arguments() -> ListenAndPlayArguments:
    defaults = ListenAndPlayArguments()
    parser = argparse.ArgumentParser(description="Stream microphone audio to, and play audio from, a TCP server.")
    parser.add_argument("--send_rate", "--send-rate", dest="send_rate", type=int, default=defaults.send_rate)
    parser.add_argument("--recv_rate", "--recv-rate", dest="recv_rate", type=int, default=defaults.recv_rate)
    parser.add_argument(
        "--list_play_chunk_size",
        "--list-play-chunk-size",
        dest="list_play_chunk_size",
        type=int,
        default=defaults.list_play_chunk_size,
    )
    parser.add_argument("--host", default=defaults.host)
    parser.add_argument("--send_port", "--send-port", dest="send_port", type=int, default=defaults.send_port)
    parser.add_argument("--recv_port", "--recv-port", dest="recv_port", type=int, default=defaults.recv_port)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=defaults.dry_run,
        help="Print the resolved connection plan and exit without connecting or opening audio devices.",
    )
    return ListenAndPlayArguments(**vars(parser.parse_args()))


if __name__ == "__main__":
    listen_and_play(**vars(_parse_arguments()))
