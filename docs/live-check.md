# 欣中爬蟲排程與公開狀態

[回首頁](../README.md) · [HA 帳單匯入排程](usage.md#自動排程)

## 執行方式

- GitHub Actions 每 6 小時執行一次，排定台灣時間 02:41、08:41、14:41、20:41；GitHub 可能延遲，並非準點保證。
- 解析最新正式 Release 的 tag，使用該 tag 的真正 client、portal 及 normalizer，Python 3.14 執行。爬蟲只需 Python 標準函式庫，不安裝 HA。
- 官方頁面一次回傳可查帳單列表；程式選取最新一期，檢查成功狀態、身分接受、帳單正規化及有限數值的用氣／合計。零用量或零費用是有效數值，不以真假值判斷。
- 每次一輪表單檢查與 usage 查詢，不做 fees 二次查詢、不自動重試、不保存完整回應或帳單，也不連接 HA／Recorder。job 最長 5 分鐘。
- 公開輸出只有 `status`、固定 `code`、`attempts`、UTC `checked_at`、`version`。不列印例外內容、戶號、戶名、帳單值、URL query、HTML 或 Cookie，不上傳結果 artifact。

## 解讀徽章

`passing` 代表最近一次工作通過；`failing` 可能是網站連線、格式不相容、Secrets 缺漏、Release 取得失敗或 GitHub 執行環境問題。點徽章查看 run 時間與 Summary。缺少 probe summary 表示爬蟲檢查未完成，不代表官網已故障。

超過 12 小時沒有新結果應視為未知。徽章可能快取，不能把舊綠燈視為目前正常。GitHub 公開 repository 長期無活動可能停用 schedule；維護者應檢查 workflow 是否 active，不用無意義 commit 延長活動。

此為單一帳戶、GitHub 網路、最新正式發行版的結果，不涵蓋所有帳戶、家中網路、HA 排程或能源統計。HA 的自動帳單匯入另在使用者主機執行，預設每週一 09:00。

## 設定、手動驗證與停用

Repository → Settings → Secrets and variables → Actions 設定：

| Secret | 用途 |
| --- | --- |
| `SCGAS_MONITOR_CUSTOMER_ID` | owner 授權的六碼測試戶號，保留開頭零 |
| `SCGAS_MONITOR_CUSTOMER_NAME` | 同戶戶名 |

值僅注入查詢步驟。不要放入 repository、workflow 本文、命令列或公開 Issue。更換後於 Actions → 欣中實際查詢 → Run workflow，確認新 run 成功，且 Summary 的版本符合目前正式版。

Workflow 只接受主 repository `main` 的 schedule／手動觸發，沒有 PR 觸發，權限為 `contents: read`；checkout 不保留 Git credential，同組執行不互相中斷。不得將含 Secrets 的工作改成執行未審查 PR 內容。

停止監測可於 Actions 停用 workflow，並移除上述兩個 Secrets；同步更新首頁狀態說明。回復程式變更可 revert 對應 commit。停用雲端檢查不影響任何 HA 自動匯入排程。
