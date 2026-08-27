# video-transcription-skill

一個可攜式的 Agent Skill，用於將公開影片或音訊網址、本機媒體檔案，轉換成保留原話與時間碼的逐字稿。Skill 的核心檔案是根目錄的 `SKILL.md`；`scripts/` 提供媒體下載、音訊抽取、自訂語音辨識命令與逐字稿格式化工具；`tests/` 提供離線測試。

## 功能定位

這個 skill 用於逐字轉錄，而不是摘要、翻譯、事實查核或內容分析。預設保留說話順序、重複、口語與有意義的語助詞；對真正聽不清楚的內容標記為 `[聽不清楚]`，不自行猜測。若使用者要求清稿、翻譯或繁簡轉換，應在保留原始辨識結果後另行處理。

## 執行需求

遠端網址需要網路連線；媒體準備需要 Python 3.9 以上與 `ffmpeg`；此外必須有可用的語音轉文字後端。可使用主機提供的原生語音能力、`manus-speech-to-text`、`whisper`、`faster-whisper`、`whisper.cpp`，或使用者指定的 CLI。`yt-dlp` 是可選的遠端媒體取得後備方案，不是硬性依賴。

## 安裝

將此資料夾放入 Agent 的 skill 目錄，並保留根目錄的 `SKILL.md`。例如，Claude Code 可使用：

```bash
mkdir -p ~/.claude/skills/video-transcription
cp -a . ~/.claude/skills/video-transcription/
```

Codex 可放在該版本使用的 Codex Skills 目錄，常見位置是 `~/.agents/skills/video-transcription/`。其他 Agent 則放入其 skill 目錄，或將 `SKILL.md` 明確加入指令上下文。

## 標準工作流程

1. 將輸入分類為本機檔案或 `http://`／`https://` 遠端網址。任意文字不會被當作網址。
2. 遠端網址使用 `scripts/fetch_media.py` 取得公開媒體；本機檔案直接使用原路徑。
3. 使用 `scripts/extract_audio.py` 將媒體轉成單聲道、16 kHz 的 WAV。
4. 選擇語音轉文字後端並保留未修改的原始回應。
5. 將 TXT、SRT、VTT 或 JSON 結果交給 `scripts/render_transcript.py`。
6. 在輸出目錄產生 `transcript.md` 與 `transcript.txt`，並保留 `raw_transcript.*`。
7. 比對原始回應與渲染結果，檢查專有名詞、時間碼、說話者標籤與聽不清楚片段。

## 遠端媒體下載

從公開影片頁面或直接媒體網址取得檔案：

```bash
python scripts/fetch_media.py \
  "https://example.com/video" \
  --output-dir work
```

成功時標準輸出只會印出一個絕對媒體路徑；診斷訊息會寫到標準錯誤。可用參數如下：

| 參數 | 必要性 | 說明 | 預設值 |
| --- | --- | --- | --- |
| `url` | 必要 | `http://` 或 `https://` 的直接媒體網址或公開頁面網址 | 無 |
| `--output-dir` | 必要 | 下載目錄 | 無 |
| `--timeout` | 選用 | 網路逾時秒數 | `30` |
| `--max-bytes` | 選用 | 遠端物件大小上限 | `524288000` bytes，約 500 MiB |
| `--no-yt-dlp` | 選用 | 停用 `yt-dlp` 後備下載 | 未啟用 |

腳本會先嘗試直接下載，再從 HTML／JSON 找公開嵌入的 MP4、WebM 等網址，最後在已安裝 `yt-dlp` 時嘗試後備方案。它不執行網頁 JavaScript，也不是登入、CAPTCHA、付費牆、私密貼文、DRM 或其他存取控制的繞過工具。

## 本機媒體與音訊抽取

本機檔案可以直接抽取音訊：

```bash
python scripts/extract_audio.py \
  "/path/to/input.mp4" \
  --output-dir work
```

預設輸出為 `audio.wav`，規格是單聲道、16 kHz、PCM WAV。主要參數如下：

| 參數 | 必要性 | 說明 | 預設值 |
| --- | --- | --- | --- |
| `input` | 必要 | 本機媒體檔案路徑 | 無 |
| `--output-dir` | 必要 | 音訊輸出目錄 | 無 |
| `--output-name` | 選用 | 輸出檔名 | `audio.wav` |

## 語音轉文字後端

優先使用 Agent 主機原生的語音或轉錄能力；其次使用已安裝的本機 CLI；再其次使用 `scripts/run_stt_command.py` 轉接使用者指定的命令；最後才考慮已存在且經使用者允許下載模型的 Whisper 相容後端。如果沒有任何後端，只能完成音訊抽取，不能宣稱轉錄成功。

自訂 CLI 必須在命令樣板中包含 `{audio}`，可選擇包含 `{output}`：

```bash
python scripts/run_stt_command.py \
  --audio work/audio.wav \
  --output work/raw_transcript.txt \
  --command 'your-stt-cli --input {audio}'
```

如果命令含有 `{output}`，後端應將結果寫入該路徑；若沒有，腳本會擷取標準輸出並寫入 `--output` 指定的檔案。命令會以非 shell 方式解析，`{audio}` 與 `{output}` 會替換成獨立參數，因此不應在命令列放入秘密資訊。可用 `--timeout` 設定逾時，預設為 3600 秒。

## 逐字稿渲染

將語音辨識後的原始結果轉成 Markdown 與純文字：

```bash
python scripts/render_transcript.py \
  work/raw_transcript.txt \
  --output-dir work/output \
  --source-url "https://example.com/video" \
  --language "zh-TW" \
  --title "影片逐字稿"
```

也可以用本機來源與備註：

```bash
python scripts/render_transcript.py \
  work/raw_transcript.json \
  --output-dir work/output \
  --source-file "/path/to/input.mp4" \
  --language "zh-TW" \
  --note "已人工複核專有名詞。"
```

可用參數如下：

| 參數 | 必要性 | 說明 | 預設值 |
| --- | --- | --- | --- |
| `input` | 必要 | 原始逐字稿檔案：TXT、SRT、VTT 或 JSON | 無 |
| `--output-dir` | 必要 | 輸出目錄 | 無 |
| `--source-url` | 選用 | 遠端來源網址 | 空字串 |
| `--source-file` | 選用 | 本機來源檔案 | 空字串 |
| `--language` | 選用 | 語言標籤 | `unknown` |
| `--title` | 選用 | Markdown 標題 | `Video Transcript` |
| `--note` | 選用 | 品質或人工複核備註 | 自動辨識提示 |

若同時指定 `--source-url` 與 `--source-file`，優先使用 `--source-url`。若沒有提供來源，會以原始逐字稿檔案路徑作為來源。

## 支援的媒體格式

媒體下載器會辨識常見副檔名與 `Content-Type: video/*`／`audio/*` 回應。內建副檔名白名單如下：

| 類別 | 支援格式 |
| --- | --- |
| 影片 | MP4、WebM、MOV、M4V、MKV、AVI |
| 音訊 | MP3、WAV、M4A、OGG、FLAC |

實際能否解碼仍取決於 `ffmpeg` 對該檔案內部編碼的支援。公開 YouTube、Threads、Instagram 等頁面屬於 best-effort 取得；頁面必須實際暴露可存取的媒體或可由已安裝的 `yt-dlp` 取得。

## 支援的逐字稿輸入格式

`render_transcript.py` 支援下列辨識後端輸出：

| 格式 | 支援方式 | 範例 |
| --- | --- | --- |
| TXT | 含時間碼或無時間碼的純文字 | `[00:00.0 - 00:02.5] Hello` |
| SRT | 標準序號、時間區間與字幕文字 | `00:00:00,000 --> 00:00:01,200` |
| VTT | `WEBVTT` 與標準時間區間 | `00:00:00.000 --> 00:00:01.200` |
| JSON | 常見 segments、utterances、results、transcript 容器，或單一文字物件 | `{"segments":[{"start":0,"end":1.5,"text":"..."}]}` |

JSON 時間欄位可使用 `start`／`end`、`start_time`／`end_time` 或 `startTime`／`endTime`；文字欄位可使用 `text`、`transcript` 或 `content`；說話者欄位可使用 `speaker` 或 `speaker_label`。時間值可為秒數或字串。JSON 陣列、巢狀容器與常見清單結構會被遞迴解析。

TXT 的時間碼格式可使用方括號包住起訖時間，例如 `[00:01.2–00:03.8] 內容`、`[00:01.2 --> 00:03.8] 內容` 或 `[00:00:01.200 - 00:00:03.800] 內容`。沒有時間碼時會保留為一段無時間碼文字，不會自行製造時間。

## 輸出契約

轉錄成功時，輸出目錄必須包含：

| 檔案 | 內容 |
| --- | --- |
| `transcript.md` | 來源資訊、語言、時間碼逐字稿、連續全文與品質備註 |
| `transcript.txt` | 適合複製或後續處理的純文字逐字稿 |
| `raw_transcript.*` | 後端提供檔案時的未修改原始回應 |

時間碼預設格式為短片使用 `[MM:SS.s–MM:SS.s]`，超過一小時使用 `[HH:MM:SS.s–HH:MM:SS.s]`。如果來源沒有時間碼，輸出會明確標示「時間碼：來源未提供」，不會假造時間。後端提供說話者標籤時會保留。

## 存取限制與失敗處理

遇到登入牆、CAPTCHA、付費牆、私密貼文、DRM 或需要使用者帳號的瀏覽器工作階段時，不會嘗試繞過。可改用使用者已授權的瀏覽器工作階段，或請使用者上傳媒體檔案／提供可直接存取的媒體網址。

無效網址、下載失敗、缺少 `ffmpeg` 或轉錄後端失敗時，流程會停止並保留已產生的部分檔案。網路操作最多重試兩次，之後改用替代取得方式或請使用者提供檔案。若遠端網址只回傳 HTML 且找不到公開媒體網址，不會根據標題、說明、留言或縮圖臆測逐字稿。

## 品質與語言規則

逐字稿預設保留原始語言與原始措辭，不會默默翻譯。若使用者要求繁體中文，而語音辨識結果為簡體中文，可在保留 raw 結果後只做字形轉換，並在文件中說明已進行字形正規化。疑似專有名詞或技術詞不會被靜默修正；必要時以「（辨識結果，疑似：……）」附註。逐字稿不應被改寫成摘要，也不應加入聽不到的內容。

## 測試

測試不需要網路或真實音訊，可直接執行：

```bash
python tests/test_skill.py
```

測試涵蓋含時間碼 TXT、SRT、JSON，以及自訂 STT 命令的標準輸出擷取。

## 檔案結構

```text
.
├── SKILL.md
├── README.md
├── scripts/
│   ├── extract_audio.py
│   ├── fetch_media.py
│   ├── install_skill.py
│   ├── render_transcript.py
│   └── run_stt_command.py
└── tests/
    └── test_skill.py
```

## 授權與來源

本 skill 以 MIT License 發布，作者歸屬為 Joker。`SKILL.md` 是 skill 的規範來源；README 是面向使用者的操作導覽。
