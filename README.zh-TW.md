<h1 align="center">Strata</h1>

[English](README.md) · **繁體中文** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](README.pt-BR.md)

<p align="center"><b>在你自己的電競桌機或筆電上，執行 1,250 億參數的 AI 模型</b><br>
NVIDIA 或 AMD 顯示卡 · Windows 或 Linux · 桌面程式 · 也能跑任何 GGUF 模型 · 免費開源</p>

<p align="center"><a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4"><img src="docs/media/pagoda-preview.webp" width="720" alt="Strata 的模型寫出來、在瀏覽器裡執行的像素寶塔庭園"></a><br>
<sub>像素寶塔庭園：一次提示就寫成，在 RTX 5070 上用 Strata 執行（IQ3_S，128K context）·
<a href="https://github.com/Niko1221/Strata/releases/download/v0.1.10/Pagoda.mp4">完整影片（49 秒）</a></sub></p>

Strata 讓 **[Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)** 在一般電腦上執行。這是一個通常
需要伺服器才跑得動的大型模型，能聊天、寫程式、看圖片，也能接上你的應用程式和程式碼代理。所有資料都留在你的電腦裡。

**它也能執行其他任何 GGUF 模型**（Gemma、Llama、Mistral，或你自己微調的模型），前面接一樣的網頁和 API，背後由
[llama.cpp](https://github.com/ggml-org/llama.cpp) 執行：請看[其他模型](#其他模型任何-gguf)。

> **這是一個 fork**，原專案是 [Niko1221/Strata](https://github.com/Niko1221/Strata)。它加上了桌面程式、給筆電和
> 8–12 GB 顯示卡用的設定、可以跑任何 GGUF 的通用模式，以及網頁上的工作進度條（[新增了什麼](#這個-fork-新增了什麼)）。
> 其他部分，以及下面所有量測數字，都來自原專案。

## 這個 fork 新增了什麼

| | 做什麼 | 狀態 |
| --- | --- | --- |
| **桌面程式**（`STRATA-GUI.bat`） | 用點的就能安裝、啟動、停止模型；顯示你的顯示卡和記憶體；英文或繁體中文介面 | 可用；在沒有 GPU 的電腦上測過 |
| **低 VRAM 設定**（`--low-vram on`） | 給 8–12 GB 的 NVIDIA 顯示卡（大部分電競筆電）：選出能把最多 VRAM 留給模型的設定 | 需手動開啟；**還沒在 8 GB 顯示卡上實測** |
| **通用模式**（任何 GGUF） | 用 llama.cpp 執行其他模型，前面接 Strata 的網頁、Monitor 和 API | 用模擬的 llama-server 測過；**還沒用真的模型測過** |
| **工作進度條** | Strata 在工作時，網頁標題列下方會出現一條細條：載入中、排隊中、讀取提示（顯示百分比）、正在回答 | 可用 |

「還沒實測」就是字面上的意思：如果你在這類電腦上跑過，歡迎[回報數字](docs/COMMUNITY_BENCHMARKS.md)。

## 速度有多快？

以下是原作者在兩台一般電競電腦上量的。一個 token 大約是 ¾ 個英文單字（中文大約一到兩個字）。

- **回答速度：** 短對話裡回覆出現的速度。每秒 60 個 token 已經比你閱讀還快。
- **讀取提示：** 讀進你送出內容的速度（這裡是 32K token 的文件、程式碼或對話紀錄）。

<table>
<tr><th>NVIDIA：RTX 5070（12 GB）、Ryzen 5 7600、64 GB 記憶體</th><th>AMD：RX 9070 XT（16 GB）、Ryzen 9 3900X、47 GB 記憶體</th></tr>
<tr><td>

| 大小 | 回答速度 | 讀取提示 |
| --- | ---: | ---: |
| **Q2_0** | 94 tokens/s | 2,650 tokens/s |
| **IQ2_XS** | 79 tokens/s | 2,090 tokens/s |
| **IQ3_XXS** | 62 tokens/s | 1,750 tokens/s |
| **IQ3_S** | 53 tokens/s | 1,620 tokens/s |
| **Coder** | 55 tokens/s | 2,180 tokens/s |

</td><td>

| 大小 | 回答速度 | 讀取提示 |
| --- | ---: | ---: |
| **Q2_0** | 60 tokens/s | 1,160 tokens/s |
| **IQ2_XS** | 52 tokens/s | 1,110 tokens/s |
| **Coder** | 44 tokens/s | 1,420 tokens/s |

</td></tr>
</table>

NVIDIA：Q2_0 用引擎 0.1.36，其他列用 0.1.26（4K 回答、32K 提示）。完整表格在
[DETAILS.md](docs/DETAILS.md#speed-measured)。VRAM 越多越快：RTX 3090（24 GB）預估每秒約 100–140 個 token。VRAM
越少越慢，在 8 GB 筆電上會慢多少還沒量過。長對話和其他顯示卡：[各模型速度](docs/MODELS.md#how-fast-is-each-size)、
[社群量測結果](docs/COMMUNITY_BENCHMARKS.md)。

## 需要什麼

| | |
| --- | --- |
| **顯示卡** | **NVIDIA** GeForce RTX 20、30、40 或 50 系列，或 **AMD** Radeon RX 7900 XT / XTX、RX 7800 XT / 7700 XT、RX 9060 XT、RX 9070 / 9070 XT、Radeon AI PRO R9700、RX 6800 / 6900 系列。上面的數字是在 **12 GB 以上 VRAM** 量的。**8–12 GB** 的 NVIDIA 顯示卡（筆電的 RTX 4060 / 4070 / 5060 等）也能跑，但比較慢：請用[低 VRAM 設定](#筆電與-812-gb-顯示卡)。 |
| **記憶體** | 32 GB 以上。記憶體決定能用[哪個模型](#該選哪個模型)。64 GB 每種大小都放得下。 |
| **硬碟** | 約 80 GB 可用空間。盡量用 SSD：第一次啟動會快很多。 |
| **系統** | Windows 10 / 11 或 Linux，以及 NVIDIA 或 AMD 的最新顯示卡驅動程式。 |

其他東西安裝程式都會自動裝好。兩三張顯示卡也可以一起分擔模型（[多 GPU](docs/MULTI_GPU.md)）。

以下是實驗性支援，由社群成員在自己的電腦上撰寫和測試：

- **較舊的顯示卡**（Tesla P40 / V100、GTX 10、Radeon VII / MI50、RX 6700 XT、RX 5500 XT）：[較舊的 GPU](docs/OLDER_GPUS.md)。
- **Intel Arc**，在 Linux 上從原始碼編譯：[Intel Arc](docs/INTEL_ARC.md)。
- **AMD Ryzen AI Max（Strix Halo）**，在 Linux 上從原始碼編譯：[Strix Halo](docs/STRIX_HALO.md)。
- **沒有 AVX2 的較舊處理器**：能跑，但很慢。[較舊的 CPU](docs/INSTALL.md#older-cpus-experimental)。

完整清單：[docs/INSTALL.md](docs/INSTALL.md#what-you-need)。

## 安裝

[下載 Strata](https://github.com/chanLik1208-dev/Strata/archive/refs/heads/main.zip) 並解壓縮（或用 `git clone`）。
接著從下面三種方式選一種，裝出來的東西都一樣。

### 1. 桌面程式（最簡單）

**Windows：** 雙擊 **`STRATA-GUI.bat`**。**Linux：** 執行 **`./strata-gui.sh`**（需要 Python 的 tkinter：
`sudo apt install python3-tk`）。

視窗會顯示你的顯示卡和記憶體，並推薦一個模型。按 **安裝／套用**，它就會下載模型（約 70 GB）、設定好並啟動。
進行中下方的進度條會跑，記錄區會顯示每個步驟。視窗也會顯示它實際執行的指令，讓你清楚知道它在做什麼。

介面語言會跟著系統（英文或繁體中文），也可以用下方的 **語言 Language** 選單切換。

### 2. 讓你的 AI 幫你裝

你有在用 AI 程式助理嗎（Claude Code、Cursor、Codex、GitHub Copilot 等）？把這段貼給它：

```text
Set up Strata on this PC for me: https://github.com/chanLik1208-dev/Strata - follow docs/AI_SETUP.md in that repository.
```

它會檢查你的顯示卡、記憶體和硬碟，選出適合的模型，安裝並啟動，再告訴你怎麼接上你的應用程式。AI 工具也可以透過
Strata 的 [MCP 伺服器](docs/MCP_SERVER.md)來安裝、啟動和停止 Strata。

### 3. 用命令列

**Windows：** 雙擊 **`START-HERE.bat`**。**Linux：** 在 Strata 資料夾裡執行 **`./setup.sh`**。

它會問你幾個問題（哪個模型和大小、多長的 context、要不要看圖片）。每題直接按 Enter 就是推薦的答案。

### 接下來會發生什麼

下載約 70 GB。如果中斷了，重新啟動就會從中斷的地方繼續。完成後瀏覽器會開啟 Strata 的網頁
`http://127.0.0.1:8080`。

> **模型啟動時，電腦可能會變慢或沒有回應 1–3 分鐘**（第一次最久）。Strata 會把 35–55 GB 載入記憶體，
> 並為顯示卡鎖定其中一部分。這是正常的，請等待，不要關掉視窗。

**下次使用**時，打開桌面程式按 **啟動**，或再執行一次 `START-HERE.bat`（`./setup.sh`）。它會直接啟動，不會重複下載。
`UPDATE.bat`（`./update.sh`）會更新 Strata 但不啟動。更新、Docker、多張顯示卡、檔案放在哪裡和所有選項：
[docs/INSTALL.md](docs/INSTALL.md)。

## 筆電與 8–12 GB 顯示卡

Strata 會把模型最常用的部分放在顯示卡上，其餘放在記憶體。8–12 GB 的顯示卡空間很少，每 MB 都很重要。
**`--low-vram on`** 會選出能把最多 VRAM 留給模型的設定：

| 設定 | 8 GB 顯示卡 | 10–12 GB 顯示卡 |
| --- | --- | --- |
| Context | 16K tokens | 32K tokens |
| KV 快取（模型對這段對話的記憶） | 4-bit：VRAM 減半 | 4-bit |
| 圖片 | 改由處理器讀取 | 改由處理器讀取 |
| 草稿詞表 | 英文和程式碼（少用約 215 MiB VRAM） | 不變 |
| 同時接著螢幕的顯示卡 | 保留 1,500 MiB 給桌面 | 相同 |

- 桌面程式偵測到這種顯示卡時會自動開啟。命令列：`START-HERE.bat --low-vram on`。
- 你自己設定的值優先（例如 `--context 32768`）。
- 英文草稿詞表只會讓中文、日文、韓文的回答稍微慢一點，回答內容本身不變。加上 `--draft-vocab cjk` 可以保留預設值。
- 還是需要 **32 GB 記憶體**。32 GB 的筆電請選 **Coder** 模型。
- 不加這個選項就什麼都不會變：安裝結果跟原專案完全一樣。

## 其他模型（任何 GGUF）

Strata 自己的引擎是專為 Qwen3.8-Flash-Next 寫的，不能跑其他模型。**通用模式**用 llama.cpp 的 `llama-server`
執行任何 GGUF 模型，前面再接上 Strata 的網頁：

- **聊天**、即時 **Monitor** 和**工作進度條**都跟 Strata 引擎一樣能用。
- **一樣的 API：** `/v1/chat/completions`（OpenAI）、`/v1/messages`（Anthropic）和 `/v1/responses` 都會轉給
  llama-server，由它套用模型自己的對話範本。工具呼叫和思考的格式依照該範本的定義。
- **模型比 VRAM 大也能跑。** llama-server 會把放不下的部分留在記憶體。MoE 模型（Gemma 4 26B-A4B、Qwen3 30B-A3B、
  gpt-oss）留在記憶體的是專家，對速度影響較小；一般的「dense」模型留的是整層，影響比較大。

**用桌面程式：** 打開 **通用模式：任何 GGUF 模型** 分頁。先按一次 **下載 llama-server**（NVIDIA 版約 550 MB），
再選擇 `.gguf` 檔，按 **啟動 GGUF 模型**。

**用命令列：**

```
python tools/get_llama_server.py
python serve/generic.py --model D:\models\my-model.gguf --ctx 32768 --low-vram
```

這不是 Strata 的引擎：沒有專家快取，也沒有草稿加速，所以 Qwen3.8-Flash-Next 還是用 Strata 自己的模式比較快。
所有選項：[docs/GENERIC.md](docs/GENERIC.md)。

## 該選哪個模型？

這一節是給 Strata 自己的模式。安裝程式會依你的記憶體推薦一個。同一個模型有好幾種大小，壓縮程度不同：越小越快，
越大稍微聰明一點。

| 你的記憶體 | 選 | 原因 |
| --- | --- | --- |
| **32 GB** | **Coder** | 32 GB 放得下，而且是為寫程式設計的（搭配 24 GB 顯示卡時 Q2_0 和 IQ2_XS 也能跑） |
| **48 GB** | **IQ2_XS**（或最快的 Q2_0） | 更大的放不下 |
| **64 GB** | **IQ2_XS**（推薦），或 IQ3_XXS / IQ3_S | 每種都放得下；IQ3_S 最好也最慢 |
| **96 GB 以上** | **IQ3_S**，或 Unsloth 的 UD-IQ4_XS（約 4-bit） | 最大的也放得下，其他程式照開 |

- **[Coder](docs/MODELS.md#coder)：** 移除一半專家的寫程式版本。依作者量測，SWE-bench Verified 分數達到完整模型的
  91%，32 GB 記憶體放得下。程式以外的能力較弱，包括中文和其他 CJK 文字（#438）。這些用途請選保留全部專家的
  Q2_0、IQ2_XS 或 IQ3_S。
- **[Swift 1.5](docs/MODELS.md#swift-15)：** 思考時間短很多的微調版。答案來得更快，品質差不多。
- **[Unsloth UD-IQ4_XS](docs/MODELS.md#unsloth-ud-iq4_xs)：** Unsloth 的約 4-bit 版本，品質介於 IQ3_S 和
  UD-Q4_K_XL 之間。下載 94 GB。記憶體少於約 80 GB 時，Strata 會在回答時從 SSD 讀一部分，所以會比較慢（NVMe SSD 有幫助）。
- **[Unsloth UD-Q4_K_XL](docs/MODELS.md#unsloth-ud-q4_k_xl-experimental)**（實驗性）：最接近完整模型。但 Strata
  回答時大部分要從 SSD 讀，在 64 GB 的電腦上每秒只有 7–8.5 個 token。
- **[OrcaRouter 的 Uncensored IQ3_XXS](docs/MODELS.md#orcarouter-uncensored-iq3_xxs)：** 需要手動設定，不在安裝程式的選單裡。

大小、下載量和哪些放得下：[docs/MODELS.md](docs/MODELS.md)。之後要加裝其他模型，用桌面程式的 **安裝／套用**，
或執行 `SETUP.bat`（Linux：`./setup.sh --setup`）。

## 使用方式

<p align="center"><img src="docs/media/runpagoda.png" width="900" alt="Strata 網頁的 Monitor 分頁，旁邊是程式碼代理"><br>
<sub>Strata 網頁的 <b>Monitor</b>（左），右邊是程式碼代理正在寫影片裡的寶塔庭園</sub></p>

- **在瀏覽器：** 開啟 `http://127.0.0.1:8080`。有 **Chat**（聊天）、模型和 GPU／CPU／記憶體的即時 **Monitor**，
  以及列出設定和網址的 **About**。標題列下方的細條顯示 Strata 正在做什麼：橘色是載入中或排隊中，藍色是正在讀你的
  提示（會顯示進度），綠色是正在回答。
- **你的應用程式和程式碼代理：** 新增一個「OpenAI 相容」的服務，base URL 填 **`http://127.0.0.1:8080/v1`**。
  API key 和模型名稱填什麼都可以。
  - 使用 Anthropic API 的程式：`http://127.0.0.1:8080/v1/messages`（Claude Code：
    `ANTHROPIC_BASE_URL=http://127.0.0.1:8080`）。
  - Codex CLI 和其他使用 OpenAI Responses API 的程式：`/v1/responses`
    （[設定方式](docs/DETAILS.md#the-responses-api-and-codex-cli)）。
- **思考：** 在聊天選單或你的程式的「reasoning effort」選 **off、low、medium 或 high**。off 最快，high 最適合難題。
- **圖片：** 安裝時「Images?」回答 yes，然後在聊天裡按 **Picture**，或在你的程式裡附上圖片。AMD 顯示卡在 Linux
  上用處理器讀圖片，在 Windows 上目前還不行。
- **從手機或其他電腦連線：** `START-HERE.bat --setup --host 0.0.0.0 --api-key <密鑰>`。一定要設定密鑰。
- **一次一個請求：** 預設一次只回答一個請求，其他的會排隊。要同時回答多個，設定 `"parallel": 2`
  （[BATCHING.md](docs/BATCHING.md)）。在 12 GB 顯示卡上這會讓每個回答變慢。
- **長提示：** 對話的第一則訊息會完整讀取，每 30,000 個 token 約 1 分鐘。之後的訊息幾秒內就會開始回答。
- **減少動態效果：** 如果系統設定了減少動態效果，網頁會改用淡入淡出，不會滑動。

更多：[對話存在哪裡](docs/INSTALL.md#where-things-are-stored)、[API 說明](docs/DETAILS.md#using-it)。

## 出問題了？

- **第一次啟動時電腦當住了。** 載入模型時這是正常的，請等待，不要關掉視窗。10 分鐘後還是沒反應？重新開機，關掉
  其他程式再試一次，或選比較小的大小。
- **下載或安裝到一半停了。** 重新啟動就會從停下的地方繼續。
- **非常慢、硬碟燈一直閃，或出現「the engine stopped unexpectedly」。** 可用記憶體不夠。關掉其他程式（瀏覽器很吃
  記憶體），或選比較小的大小（Q2_0 或 IQ2_XS）。
- **筆電上出現「no VRAM is left for the expert cache」。** 請用[低 VRAM 設定](#筆電與-812-gb-顯示卡)，並關掉其他
  使用顯示卡的程式。
- **顯示 port 8080 已被使用。** Strata 已經在執行了。找找它的視窗，或在桌面程式裡停止它。
- **通用模式顯示「llama-server stopped」。** 它的記錄檔是 Strata 資料夾裡的 `strata-generic-<模型>.log`。最常見的
  原因是模型放不下：試試小一點的 `--ctx` 或 `--low-vram`。

更多問題和解法：[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。這個 fork 新增的功能有問題，請在
[這裡開 issue](https://github.com/chanLik1208-dev/Strata/issues)；引擎本身的問題請到原專案的
[issues](https://github.com/Niko1221/Strata/issues)。請附上 Strata 資料夾裡的 `strata-<模型>.log`。發現安全性問題？
請私下回報：[SECURITY.md](SECURITY.md)。

## 它是怎麼運作的？

像這樣的模型通常要在有好幾百 GB 顯示記憶體的伺服器上執行，而你的顯示卡只有 8–24 GB。Strata 的做法是**讓整台電腦
一起分擔工作**。就像廚房：常用的東西放在流理台上，其他的收在儲藏室。

<p align="center"><img src="docs/media/how-it-works.svg" width="860" alt="模型的 24,576 個專家：最常用的在顯示卡上，全部都在記憶體裡，一張查找表在 SSD 上"></p>

- **這個模型是由 24,576 個小專家組成的團隊。** 每個字只需要其中 10 個。
- **你的顯示卡**放著最常用的幾千個專家。**你的記憶體**放著全部專家，**你的處理器**同時處理其餘的部分。
  **你的 SSD** 放著一張很大的查找表。

<p align="center"><img src="docs/media/guess-and-check.svg" width="860" alt="小幫手先猜接下來的字，大模型一次全部檢查，留下猜對的"></p>

- **先猜再檢查：** 一個小幫手先猜接下來的幾個字，大模型一次全部檢查。得到的答案完全一樣，但快 1.6–1.8 倍。
- **長文會分大段讀取**（一次最多 8,192 個 token），每秒超過 1,000 個 token。

更詳細的說明：[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)。每個部分和它的數字：
[技術細節](docs/DETAILS.md#how-it-works)和[論文](docs/paper/Strata-Paper.pdf)。

## 致謝與授權

Strata 的作者是 [Niko1221](https://github.com/Niko1221/Strata)；這個 fork 只加上了[上面列出的部分](#這個-fork-新增了什麼)。
模型是 Qwen 團隊的 [Qwen3.8-Flash-Next](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)，由
[ISTA-DASLab](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF)、UkisAI（Swift 1.5）和 Unsloth 壓縮。
Strata 使用了 [llama.cpp / ggml](https://github.com/ggml-org/llama.cpp) 的部分程式碼，通用模式則直接執行 llama.cpp
的 `llama-server`。網頁的動態效果依照 [Dynamization](https://github.com/chanLik1208-dev/Dynamization) 設計規範。
完整致謝：[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md#credits)。

Strata 以 [MIT 授權](LICENSE)開源。少數元件和每個模型都有各自的授權（[有哪些](docs/HOW_IT_WORKS.md#license)）。

## 支持 Strata

Strata 是免費開源的。如果它對你有幫助，可以支持原作者繼續開發：

<p align="center"><a href="https://buymeacoffee.com/strataengine"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50"></a></p>
