# Image Filename Renamer 2.0

## 簡介

本程式為批次圖片重新命名工具，提供圖形化介面（Tkinter）讓使用者為資料夾內的圖片設定多欄位檔名、固定前綴（Prefix）／後綴（Suffix）與分隔符號，並可即時預覽新檔名。支援直接批次重新命名（附帶復原上一步與還原最初原始檔名功能），也可匯出 `.bat` 批次檔執行。

由 Python 3.10+ 與 Pillow 開發。

* **Version:** 2.0
* **Author:** YouZih Chen

---

## 安裝與環境需求

### 必要套件

```bash
pip install pillow
```

### 選配套件（建議安裝以獲得完整格式與介面支援）

```bash
pip install sv-ttk pillow-heif rawpy
```

* `sv-ttk`：提供 Windows 11 原生風格（未安裝時會自動切換為內建 Gruvbox 主題）。
* `pillow-heif`：支援預覽 `.heic`、`.heif`、`.avif` 格式。
* `rawpy`：支援預覽相機 RAW 檔（若未安裝，程式會嘗試讀取內嵌 JPEG 縮圖或顯示佔位圖示）。

### 啟動程式

```bash
python image_rename.py
```

---

## 支援格式

* **標準格式：** `.jpg`、`.jpeg`、`.png`、`.bmp`、`.webp`、`.gif`、`.tif`、`.tiff`、`.ico`
* **相機 RAW：** `.dng`、`.cr2`、`.cr3`、`.nef`、`.arw`、`.orf`、`.rw2`、`.raf`、`.pef`、`.srw`
* **HEIF / AVIF：** `.heic`、`.heif`、`.avif`

---

## 主要功能

* **自訂檔名欄位與固定前／後綴（Prefix / Value / Suffix）：**
  * 可設定多個欄位名稱（例如：`TP,Layer,F,type`）與分隔符號（例如：`-` 或 `_`）。
  * 每個欄位皆提供三個輸入框：`Prefix`（固定前綴）、`Value`（每張圖片的變數值）、`Suffix`（固定後綴）。
  * 當該欄位的 `Value` 有輸入內容時，會組合成 `{Prefix}{Value}{Suffix}`；若 `Value` 留空，該欄位與其前後綴皆不會出現在檔名中。
  * `Prefix` 與 `Suffix` 會保留於整個資料夾設定中（切換圖片不會清空），且設定為跳過 `Tab` 焦點，讓鍵盤輸入流程更流暢。
* **保留輸入文字至下一張圖片：**
  * 切換至下一張尚未命名的圖片時，會自動保留上一張圖片在 `Value` 欄位中輸入的文字，方便連續微調編號或類型；若下一張已有儲存過的名稱，則會載入其原有設定。
* **即時預覽與安全防衝突：**
  * 輸入時即時顯示 `New Name:` 預覽，並自動過濾 Windows 檔名不合法字元與系統保留字（如 `CON`、`NUL` 等）。
  * 若多張圖片產生相同檔名，會自動在檔名後方加上 `(1)`、`(2)` 等編號以避免覆蓋。
* **直接重新命名、復原與還原原始檔名：**
  * `⚡ Rename Now`：採用兩階段暫存更名機制（先更名為暫存檔名再轉為目標檔名），安全處理批次更名與名稱互換。
  * `↺ Undo Rename`：復原上一次重新命名操作。
  * `⟲ Restore Original`：將已重新命名的檔案還原為最初的原始檔名（對應表會寫入 `rename_config.json`，即使重新開啟程式仍可還原）。
  * `🖹 Export .bat`：在目標資料夾產生 UTF-8 編碼的 `rename.bat` 批次檔。
* **批次輔助操作：**
  * `↓ Fill Down`：將目前（或指定）圖片的欄位值向下套用至所有尚未命名的圖片。
  * `✕ Clear Fields`：清除目前圖片的命名設定。
* **縮圖瀏覽與右鍵選單：**
  * 支援非同步縮圖載入、分頁切換（`‹` / `›`）與縮圖快取虛擬化。
  * 縮圖邊框顏色區分狀態：目前檢視中、已命名、未命名。
  * 右鍵點擊縮圖可執行：`Select This Image`、`Fill Down from Here`、`Clear Naming`、`Show in Explorer`。
* **主圖片檢視操作：**
  * 滑鼠滾輪縮放、按住左鍵拖曳移動、雙擊或點擊 `↺ Reset View` 重設檢視。
* **佈景主題與偏好設定（`⚙ Preferences`）：**
  * **主題（`🎨 Theme`）：** 預設為 **Windows 11 Light**（選單內顯示 `Light` / `Dark`），另提供 Gruvbox Dark / Light、Dracula、Nord、Catppuccin Mocha / Latte。
  * **縮圖大小（`🖼 Thumbnail Size`）：** 可切換 Small (64px)、Medium (80px)、Large (96px)。
  * **重設預設值（`↺ Reset to Defaults`）：** 恢復預設主題與縮圖大小。

---

## 使用步驟

1. **載入資料夾：** 點擊 `📂 Load Folder`，選擇包含圖片的資料夾（若該資料夾已有 `rename_config.json` 會自動載入設定與命名進度）。
2. **設定欄位與分隔符：**
   * 在 `Field Titles (comma-separated):` 輸入欄位名稱（例如 `TP,Layer,F,type`）。
   * 在 `Separator:` 輸入分隔字元（例如 `-`）。
   * 點擊 `✔ Set Fields` 產生欄位輸入列。
3. **（選填）設定固定前／後綴：**
   * 用滑鼠點擊各欄位左側的 `Prefix` 或右側的 `Suffix` 輸入框填入固定字詞（例如 `TP` 欄位前綴填 `TP`，`F` 欄位前綴填 `(`、後綴填 `)`）。
4. **輸入各圖片檔名：**
   * 在 `Value` 欄位輸入內容，於最後一欄按 `Enter`，或按 `Tab`（會優先聚焦至 `Next ▶`）切換下一張圖片。
   * 使用 `Next ▶`（左）與 `◀ Prev`（右）按鈕、快捷鍵或點擊縮圖切換圖片。
5. **執行重新命名：**
   * 點擊 `⚡ Rename Now` 確認預覽清單後立即更名；或點擊 `🖹 Export .bat` 產生 `rename.bat` 後雙擊執行。
   * 如需撤銷可點 `↺ Undo Rename`，如需一次還原回最初檔名可點 `⟲ Restore Original`。

---

## 快捷鍵一覽

| 快捷鍵 | 功能 |
| :--- | :--- |
| `Tab` | 在各 `Value` 輸入框間移動，最後一欄後先聚焦至 `Next ▶` |
| `Enter`（於欄位中） | 跳至下一欄 `Value`；於最後一欄則切換至下一張圖片 |
| `Ctrl + →` / `PageDown` | 下一張圖片（`Next ▶`） |
| `Ctrl + ←` / `PageUp` | 上一張圖片（`◀ Prev`） |
| `Ctrl + Enter` | 立即重新命名（`⚡ Rename Now`） |
| `Ctrl + Z` | 復原上次重新命名（`↺ Undo Rename`） |
| `Ctrl + D` | 向下填滿未命名圖片（`↓ Fill Down`） |
| `Delete`（非輸入框焦點時） | 清除目前圖片欄位（`✕ Clear Fields`） |
| `Ctrl + S` | 手動儲存設定（`rename_config.json`） |
| `Ctrl + T` | 切換目前主題系列的淺色／深色模式 |

---

## 設定檔說明（`rename_config.json`）

程式會在載入的資料夾內自動建立並更新 `rename_config.json`（500ms 防抖動自動儲存），記錄以下資訊：

* `field_titles`：欄位名稱列表
* `field_prefixes` / `field_suffixes`：各欄位的固定前綴與後綴
* `separator`：分隔符號
* `rename_map`：各圖片目前的欄位輸入內容
* `original_names`：已更名檔案對應的最初原始檔名（供 `⟲ Restore Original` 使用）

---

## 注意事項

* 執行 `⚡ Rename Now` 會直接更改硬碟上的檔案名稱，雖然支援 `↺ Undo Rename` 與 `⟲ Restore Original`，建議處理重要檔案前仍先保留備份。
* `⟲ Restore Original` 依賴 `rename_config.json` 內的 `original_names` 紀錄，若在還原前刪除此設定檔將無法自動查回原始檔名。
* 若所有欄位 `Value` 皆留空，該圖片不會被重新命名。

---

## 使用範例

假設 `Photos` 資料夾內有以下照片：

* `DSC0001.jpg`
* `DSC0002.jpg`
* `DSC0003.jpg`

目標檔名為：`TP1-L1-坑面照.jpg`、`TP1-L1-(F1)-現象照.jpg`、`TP1-L1-標本照.jpg`

1. 點擊 `📂 Load Folder` 選擇 `Photos` 資料夾。
2. `Field Titles` 輸入 `TP,Layer,F,type`，`Separator` 輸入 `-`，點擊 `✔ Set Fields`。
3. 設定固定前／後綴：
   * `TP` 欄位的 `Prefix` 輸入 `TP`
   * `Layer` 欄位的 `Prefix` 輸入 `L`
   * `F` 欄位的 `Prefix` 輸入 `(`、`Suffix` 輸入 `)`
4. 逐張在 `Value` 欄位輸入：
   * `DSC0001.jpg`：`1`、`1`、（留空）、`坑面照` → 預覽為 `TP1-L1-坑面照.jpg`
   * `DSC0002.jpg`：切換過來時會保留上一張文字，只需將 `F` 填入 `F1`、`type` 改為 `現象照` → 預覽為 `TP1-L1-(F1)-現象照.jpg`
   * `DSC0003.jpg`：清空 `F`、`type` 改為 `標本照` → 預覽為 `TP1-L1-標本照.jpg`
5. 點擊 `⚡ Rename Now` 完成批次重新命名。

---

## 更新紀錄（v1.0 → v2.0）

相較於僅能匯出 `.bat` 的 v1.0，v2.0 進行了大幅重構與功能升級：

* **直接重新命名與安全復原機制：**
  * 新增 `⚡ Rename Now` 直接在程式內完成批次更名，並透過兩階段暫存檔名機制避免檔案覆蓋或名稱互換失敗。
  * 新增 `↺ Undo Rename`（復原上次更名）與 `⟲ Restore Original`（透過 `rename_config.json` 持久記錄最初原始檔名，重開程式後仍可還原），同時保留 `🖹 Export .bat`。
* **欄位前／後綴與更順暢的輸入流程：**
  * 新增各欄位固定 `Prefix` / `Suffix` 設定與即時 `New Name:` 預覽，並自動處理不合法字元、Windows 保留字與重複檔名編號。
  * 切換到下一張未命名圖片時自動保留上一張輸入文字，並新增 `↓ Fill Down` 與 `✕ Clear Fields`。
  * 調整導覽按鈕為左 `Next ▶`、右 `◀ Prev`，且 `Tab` 鍵會優先聚焦至 `Next ▶`。
* **多格式支援與非同步縮圖：**
  * 擴充支援相機 RAW（透過 `rawpy` 或內嵌 JPEG 預覽）與 HEIC/HEIF/AVIF（透過 `pillow-heif`）。
  * 縮圖改為背景執行緒非同步載入與快取虛擬化，並加入狀態邊框標示、縮圖右鍵選單與三段縮圖大小切換。
* **多樣化佈景主題與完整快捷鍵：**
  * 預設改為 Windows 11 Light（`sv-ttk`），選單支援 Light / Dark 與 Gruvbox、Dracula、Nord、Catppuccin 多款主題。
  * 新增全套鍵盤快捷鍵（`Ctrl+→ / ←`、`PageUp / PageDown`、`Ctrl+Enter`、`Ctrl+Z`、`Ctrl+D`、`Ctrl+S`、`Ctrl+T`、`Delete`）。
