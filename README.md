# 欣中天然氣 — Shin Chung Gas

Home Assistant 自訂整合，透過欣中天然氣官方氣費查詢取得帳單，用於帳期用量、費用及估算能源統計。版本 0.1.0，最低 Home Assistant 2026.9.1。

## 功能

- UI 設定六碼用戶號碼、戶名與裝置顯示名稱；每帳戶獨立 entry／device／歷史及排程，可重新驗證同一帳戶，不會把另一戶的帳單混入。
- 首次預設匯入所有官方可查帳期，可限制期數。最新一期查詢、歷史回填、重建統計按鈕；每日／每週／每月排程及開關。
- 最新帳期、使用度數、抄表度、抄表狀況、從量費、租金、追收、退還、基本費、違約金、合計、計費起迄、應收日期、繳費期限與 paid／unpaid 狀態。
- 最後嘗試、成功、失敗與下次查詢時間、查詢結果／錯誤码、已匯入與可查帳期數、統計狀態及最近 100 筆查詢歷程。
- 按日或按涵蓋月份等額分攤的用氣／費用歷史；月／年摘要標示 coverage。可選有來源的碳排係數，未設定則保持未知，不推定欣中官方碳排量。
- 查詢失敗保留最後成功帳單；官網可查範圍縮減不刪既存歷史。重新查詢更新舊帳單的銷帳及費用，不重複累加。

## 安裝

在 HACS 的「自訂儲存庫」新增 `https://github.com/yitsewu/shin-chung-gas`，類型選 Integration，下載後重新啟動 Home Assistant。在「設定 → 裝置與服務 → 新增整合」搜尋「欣中天然氣」，輸入本人帳單的用戶號碼與戶名。

亦可將 Release／本機 `dist/scgas.zip` 解壓至 HA 的 `/config/custom_components/scgas/`，確保 `manifest.json` 位於該目錄內，再重新啟動。

查詢直接使用欣中官方表單，不需要 CAPTCHA、OCR、外部 app 或額外 Python dependencies。Repository 已公開，可加入 HACS 自訂儲存庫；尚未收錄至 HACS 預設目錄。

## 能源儀表板

「天然氣用量」選擇 **顯示名稱 總用氣量**，費用選擇本整合的 **顯示名稱 總費用**。資料為外部長期統計，不是「本期用量」或「最新表讀值」感測器的 state history。後兩者刻意不設定累積 state class，避免整期用量集中計入抓取當天。

首次統計於背景建立，須等「統計狀態」顯示完成。修改分攤選項或點擊重建統計會從本機保存帳單重建，不連線欣中；只替換本 entry 擁有的三組 statistic IDs，不碰台水或其他來源。

**所有月／日／小時分攤皆為估算，不是實際逐日抄表。** 預設按涵蓋月份等額分攤；按日模式按計費期間天數分攤。官網計費起迄原值保留，分攤以含首尾日處理；此模型依已觀察連續帳期間隔推導，官方未提供逐日消耗。

費用以帳單合計分攤，包含基本費及原站已反映的調整；不再次把費用明細加到合計。碳排僅在使用者設定係數與來源時估算，不能當作安全告警或實際燃燒監測。

## Actions

- `scgas.get_history`：`config_entry_id`、可選 `limit`，回傳保存帳單與估算月份，不查官網。
- `scgas.get_query_history`：相同 entry 與可選 `limit`，讀取最近 100 筆查詢狀態。
- `scgas.query_month`：`config_entry_id`、`month`（應收日期所屬西元 `YYYY-MM`）。官方每次回傳整張歷史表，本整合只保存指定月份；沒有該月就回報錯誤。

通知可使用一般 HA automation，監看最新帳期或繳費狀態；整合不主動寄信或建立付款動作。期限未知時不得推算到期日，官網銷帳可能延遲。

## 邊界

僅使用「瓦斯費用暨度數明細資料」；另一模式費用相同但沒有度數，只有原始銷帳碼，這版不另查第二模式。歷史範圍受官方申請用氣日期與保留範圍限制。同月若出現多筆應收資料，回 `duplicate_month` 並保留舊資料；不默默覆蓋或猜測合併方式。

只存去識別帳單；戶號／戶名保留於 HA config entry，不進入感測器、診斷、查詢歷程或套件。Cookie／原始 HTML 僅於記憶體，HTTPS 不停用憑證驗證，不跟隨重新導向、不自動重試。官方 GET 會把查詢身分放在 URL，官方端可能留存；不要開啟第三方 HTTP 除錯紀錄。

本整合只讀帳單，沒有即時用量、漏氣偵測、自報度數、關閥或付款功能。移除 config entry 不會主動清除既存帳單 Store／外部統計；移除前保留 HA 備份。尚未部署至使用者的正式 HA。

## 開發與來源

排程、數據模型、entity、服務及外部統計改寫自 [taiwan-water](https://github.com/yitsewu/taiwan-water)，來源 commit `6a7810887148ddb0407550593ae7b42a0ae753f0`，MIT Copyright 2026 yitsewu（授權見 LICENSE）。欣中 transport／parser 來自 owner 的獨立爬蟲；本版新增欣中正規化、設定與測試，未包含台水 OCR 權重或 app。

```shell
pip install pytest tzdata ruff
ruff check custom_components tests scripts
pytest tests --ignore=tests/ha -q
python scripts/package.py
```

真正 HA／SQLite tests 依 `.github/requirements-ha.txt`，於 Linux Python 3.14 執行；Windows 單元測試使用小型 HA stub，不冒充實際 HA 驗收。CI 額外執行官方 Hassfest。
