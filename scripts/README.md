# Scripts

Run these commands from the repository root. Start with `--help`; use `--dry-run` to validate a command without loading models, opening audio devices, or connecting to a server.

## Prerequisites and limitations

- Install the project before running a script: `pip install -e .`.
- Live listen clients require `sounddevice`, a working microphone, and an output device. They also need a compatible speech server running at the requested address. `--dry-run` does not require audio hardware or a server.
- Benchmark scripts load the selected STT or TTS handler during a live run. Install the model-specific project extras and any required runtime (for example, CUDA, Apple MLX, or model weights) before benchmarking. `--dry-run` validates the requested benchmark plan without loading models.
- `synthetic_conversation_realtime_client.py` historically uses macOS `say` to synthesize prompt audio for live runs. Its `--dry-run` works cross-platform because it does not invoke `say`, require `HF_TOKEN`, write logs, or make network connections.
- On windows, activate the virtual environment first and use `py` instead of `python` if that is how Python is installed. Verify that microphone and speaker access is allowed for the terminal, and select `sounddevice` device indexes when the defaults are not the intended devices.

## `benchmark_stt.py`

Benchmark speech-to-text handlers against an audio file. A live run decodes the input and loads each selected model.

```bash
python scripts/benchmark_stt.py --help
python scripts/benchmark_stt.py --audio_file path/to/audio.wav --dry-run
python scripts/benchmark_stt.py --audio_file path/to/audio.wav --handlers faster-whisper --iterations 5 --output stt_benchmark_results.json
```

`--audio_file` remains required for `--dry-run`; it checks that the path exists but does not decode the file. Install dependencies for the selected handler before a live benchmark.

## `benchmark_tts.py`

Benchmark text-to-speech handlers and save latency results as JSON.

```bash
python scripts/benchmark_tts.py --help
python scripts/benchmark_tts.py --handlers kokoro --dry-run
python scripts/benchmark_tts.py --handlers kokoro qwen3 --text "Hello from the benchmark" --iterations 3 --output tts_benchmark_results.json
```

Use `--qwen3_mlx_quantizations bf16 4bit 6bit 8bit` to compare Qwen3 MLX variants where that backend is available. The dry-run validates handler names and requested quantizations without loading models.

## `listen_and_play.py`

Stream raw microphone audio to the legacy two-port TCP client and play received audio.

```bash
python scripts/listen_and_play.py --help
python scripts/listen_and_play.py --dry-run
python scripts/listen_and_play.py --host localhost --send_port 12345 --recv_port 12346
```

A live run requires `sounddevice`, a microphone, a speaker, and a server accepting the configured send and receive ports. Use `--send_rate`, `--recv_rate`, and `--list_play_chunk_size` to match the server audio format.

## `listen_and_play_realtime.py`

Talk to an OpenAI Realtime-compatible speech server through a microphone and speaker.

```bash
python scripts/listen_and_play_realtime.py --help
python scripts/listen_and_play_realtime.py --dry-run
python scripts/listen_and_play_realtime.py --host 127.0.0.1 --port 8765 --voice bm_fable
```

A live run requires `sounddevice`, input/output audio devices, and a running realtime server. Use `--input-device` and `--output-device` with device indexes when necessary; use `--base-url` or `--websocket-base-url` to override the default endpoint.

## `synthetic_conversation_realtime_client.py`

Run one or more scripted realtime conversations for capacity and soak testing. Live runs synthesize cached prompt WAVs, stream them to the server, and write per-client logs.

```bash
python scripts/synthetic_conversation_realtime_client.py --help
python scripts/synthetic_conversation_realtime_client.py --clients 2 --turns 3 --dry-run
python scripts/synthetic_conversation_realtime_client.py --host 127.0.0.1 --port 8765 --clients 2 --turns 60 --interval 10 --log-dir /tmp/synthetic_conversation
```

For live runs, provide `HF_TOKEN` and run on macos with `say` available on `PATH`. To target a hosted endpoint, use `--url wss://endpoint.example.com/v1/realtime`; to allocate through a load balancer, use `--lb-url https://lb.example.com`.
