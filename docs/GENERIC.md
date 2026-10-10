# Generic mode: any GGUF model

Strata's own engine runs Qwen3.8-Flash-Next and its versions, nothing else. The generic mode runs **any GGUF model**
(Gemma, Llama, Mistral, a fine-tune of your own) with llama.cpp's `llama-server`, behind Strata's web app:

- **Chat**, the **Monitor** (what is running, the prompt's progress, the last requests, GPU/CPU/RAM) and the
  **activity bar** under the header work as with Strata's engine.
- **The API paths go to llama-server unchanged:** `/v1/chat/completions`, `/v1/completions`, `/v1/messages`
  (Anthropic), `/v1/responses`, `/v1/models`, `/v1/embeddings`. llama-server renders the model's own chat template,
  so tools and thinking work as that template defines them.
- **A model larger than the VRAM still runs.** llama-server's `--fit` (on by default) keeps in RAM what does not fit
  the GPU. For a mixture-of-experts model (Gemma 4 26B-A4B, Qwen3 30B-A3B, gpt-oss) it keeps experts there, which costs
  little speed; for a dense model it keeps whole layers, which costs more.

It is not Strata's engine: no expert cache, no draft layer, no Strata-specific settings (About > Settings stays empty).
Nothing here is measured yet on an 8 GB laptop; please report what you see.

## Use it

**Window:** `STRATA-GUI.bat` (Linux: `./strata-gui.sh`), tab **通用模式**: press **下載 llama-server** once, pick the
`.gguf`, then **啟動 GGUF 模型**.

**Command line:**

```
python tools/get_llama_server.py                       (once: ~550 MB for NVIDIA, into engine-llama/)
python serve/generic.py --model D:\models\my-model.gguf --ctx 32768 --low-vram
```

| Option | Meaning |
| --- | --- |
| `--model FILE` | the GGUF (a split model: its first part) |
| `--mmproj FILE` | the vision projector, for a model that reads images |
| `--ctx N` | context in tokens (default: llama-server's, fitted to memory) |
| `--low-vram` | 8-bit KV cache: half the VRAM of the default f16 |
| `--port N`, `--host H --api-key K` | as for Strata (`--host` beyond this PC needs a key) |
| `-- ARGS` | passed to llama-server unchanged, e.g. `-- -ngl 20 --n-cpu-moe 30` |

`get_llama_server.py` takes a pinned llama.cpp build (`--tag latest` for the newest) and picks it by your card:
NVIDIA with driver 580+: CUDA 13.4; an older driver: CUDA 12.4 (Linux 12.8); no NVIDIA card: Vulkan. `--backend`
chooses one yourself. llama-server's log: `strata-generic-<model>.log` in the Strata folder.
