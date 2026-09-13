# Shin Chung Gas / 欣中天然氣帳單匯入

[![Open your Home Assistant instance and open a repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=yitsewu&repository=shin-chung-gas&category=integration)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

在 Home Assistant 查詢欣中天然氣帳單、用氣量與費用。填入用戶號碼及戶名即可使用，不需驗證碼。

非欣中天然氣官方整合，適用欣中天然氣用戶。

## 功能

- 帳單明細、用氣量、抄表讀值、費用、繳費狀態與歷史紀錄。
- 自動排程、立即查詢最新一期、補抓歷史與重建統計按鈕。
- 上次／下次查詢時間、查詢結果與統計狀態。
- 能源面板可用的「欣中天然氣 總用氣量」與費用統計，無須自建 helper 或 YAML。
- 支援多帳戶及自訂顯示名稱；查詢失敗保留已保存帳單。

## 安裝

需要 **Home Assistant 2026.9.1 以上**。

**HACS**

1. 先安裝 HACS，點頁首按鈕開啟儲存庫；也可在 HACS「自訂儲存庫」加入 `https://github.com/yitsewu/shin-chung-gas`，類型選「整合」。
2. 下載整合，重新啟動 Home Assistant。

**ZIP 安裝**

1. 從 [Releases](https://github.com/yitsewu/shin-chung-gas/releases) 下載 `scgas.zip`。
2. 將內容解壓至 HA 的 `/config/custom_components/scgas/`，確認 `manifest.json` 位於該目錄內，重新啟動 HA。

更新前先備份 HA。

## 設定

1. 前往「設定 → 裝置與服務 → 新增整合」，搜尋「欣中天然氣」。
2. 填入帳單上的六碼用戶號碼與戶名，可自訂顯示名稱。首次預設取得官網可提供的全部帳期。
3. 在整合選項調整查詢排程；預設每週一 09:00。
4. 等待「統計狀態」顯示完成，在能源面板的天然氣設定選擇「欣中天然氣 總用氣量」及對應的「欣中天然氣 總費用」。若有自訂顯示名稱，請選擇對應名稱的統計。

## 月度分攤

預設按帳單涵蓋月份平均分配。例如兩個月一期 **20 度、600 元 → 每月 10 度、300 元**；其他帳期依實際涵蓋月份分配。

這是**帳單分攤估算，不是每月實際抄表量**。整合選項可改為按實際天數分攤，也可按「重建統計」重新整理已保存的帳單。

需要碳排估算時，可自行設定碳排係數與來源；未設定時顯示未知。

## 問題回報

回報問題請到 [Issues](https://github.com/yitsewu/shin-chung-gas/issues)，勿附上用戶號碼、戶名或原始帳單。

## 授權

程式碼採用 [MIT License](LICENSE)。
